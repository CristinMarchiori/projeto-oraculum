import base64
import csv
import re
import os
import queue
import threading
import time
import traceback
from datetime import datetime
from typing import Any

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import webview
except ImportError:
    webview = None

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

try:
    from modbus_simple import (
        read_mw, read_mw_block, read_mw_block_auto,
        write_mw, write_mw_schneider,
    )
except Exception as e:
    print(f"[ERRO] Falha ao importar modbus_simple.py: {e}")
    read_mw = read_mw_block = read_mw_block_auto = None
    write_mw = write_mw_schneider = None

# ============================================================
# CONFIGURACOES PADRAO
# ============================================================
IP_PADRAO = "172.25.217.210"
PROTOCOLO_PADRAO = "SCHNEIDER"
FLAG_MONITOR_STATUS_PADRAO = "%MW3004"
TRIGGER_PADRAO = "MW3000:BOOL:0"
TIPO_TRIGGER_PADRAO = "NIVEL"
PRESSAO_LIDA_PADRAO = "MW413:UINT"
PRESSAO_PROGRAMADA_PADRAO = "MW3002:UINT"
INERCIA_PRESSAO_PADRAO = "MW515:UINT"
TEMPERATURA_PROGRAMADA_PADRAO = "MW409:UINT"
TEMPERATURA_LIDA_1_PADRAO = "MW410:UINT"
TEMPERATURA_LIDA_2_PADRAO = "MW411:UINT"
INDICE_PRESSAO_LIDA = 0
INDICE_PRESSAO_PROGRAMADA = 1
INDICE_INERCIA_PRESSAO = 2
# ALT29A - canais termicos opcionais, configurados pela interface
INDICE_TEMPERATURA_PROGRAMADA = 3
INDICE_TEMPERATURA_LIDA_1 = 4
INDICE_TEMPERATURA_LIDA_2 = 5
FATOR_ESCALA_TEMPERATURA_PROGRAMADA = 1.0
FATOR_ESCALA_TEMPERATURA_LIDA_1 = 1.0
FATOR_ESCALA_TEMPERATURA_LIDA_2 = 1.0

# Canais que NÃO devem ser plotados (mas continuam sendo lidos e salvos no CSV).
INDICES_NAO_PLOTAR = {INDICE_INERCIA_PRESSAO}
MARGEM_EIXO_X_S = 2.0   # respiro (em segundos) nas bordas esquerda/direita do eixo X (ALT14)
LIMIAR_VENTILACAO = 2   # ALT11 - MW413 abaixo deste valor = ventilando (antes 5)
DURACAO_MINIMA_VENTILACAO = 2.0   # ALT15 - descarta ventilações falsas/fantasma curtas (antes 0.2)
# ALT15 - Anti-glitch (debounce): nº de amostras consecutivas para confirmar transição de estado.
DEBOUNCE_AMOSTRAS_SOB_PRESSAO = 2   # confirma FIM do sob pressão (MW3002 = 0) - ignora 1 leitura isolada
DEBOUNCE_AMOSTRAS_VENTILACAO = 2    # confirma INÍCIO da ventilação (MW413 < limiar) - ignora glitch
DURACAO_MINIMA_SOB_PRESSAO = 1.0    # ALT15 - períodos sob pressão menores que isso são descartados
# ALT17 - Define o que "Tempo Sob Pressão" mede:
#   True  (ii/B2) = janela do COMANDO (MW3002 > 0), uniformiza o 1º período (imune à oscilação do MW413).
#   False (i)     = tempo em que a PRESSÃO REAL (MW413) ficou acima do limiar (lógica original).
# MW413 é usado apenas para CONFIRMAR que houve pressurização durante a janela.
MEDIR_SOB_PRESSAO_POR_MW3002 = False   # ALT18 - medir pela PRESSÃO REAL (MW413), tempo efetivo sob pressão (~6 s)
LIMIAR_PRESSAO_PROGRAMADA_ATIVA = 0   # ALT8: MW3002 > 0 = pressao programada ativa (limites so aqui)
MARGEM_Y_LIMITES_PERC = 0.05   # ALT9: 5% de folga acima do max. e abaixo do min.
INCLUIR_LIMITES_NO_AUTOSCALE_Y = True   # ALT9: liga/desliga a inclusao dos limites no autoscale Y
INTERVALO_AQUISICAO_FIXO = 0.1
ENDERECO_VETOR_FORM_M340 = 17000
QUANTIDADE_VETOR_FORM_M340 = 41
STRING_BYTE_SWAP = True
STATUS_AGUARDANDO_INICIO = 0
STATUS_EM_MONITORACAO = 1
STATUS_CONCLUIDO = 2
# Compatibilidade com as funções existentes de marcadores.
INDICE_CANAL_PRESSAO = INDICE_PRESSAO_LIDA
MAX_FALHAS_TRIGGER_CONSECUTIVAS = 10
MAX_FALHAS_CANAIS_CONSECUTIVAS = 10

# ALT28A - qualidade da Pressao Lida
VALOR_INVALIDO_PRESSAO_LIDA = 65535
MAX_LEITURAS_INVALIDAS_PRESSAO_CONSECUTIVAS = 3
MAX_RESULTADOS_SESSAO = 100  # ALT26 - limite do histórico mantido em memória

PALETA_GRAFICO = {
    "fundo_figura": "#F3F6FA", "fundo_eixos": "#FFFFFF",
    "grade_principal": "#D8DEE4", "grade_secundaria": "#EEF1F4",
    "texto": "#24292F", "borda": "#8C959F",
    "legenda_fundo": "#FFFFFF", "legenda_borda": "#D0D7DE",
}
CORES_CANAIS = ["#0057B8", "#F28E2B", "#59A14F", "#9C755F"]
COR_LIMITE_PRESSAO_PROGRAMADA = "#C1121F"
COR_FAIXA_PRESSAO_PROGRAMADA = "#C1121F"
ESPESSURA_LIMITE_PRESSAO_PROGRAMADA = 1.6
ESTILO_LIMITE_PRESSAO_PROGRAMADA = "--"
ALPHA_LIMITE_PRESSAO_PROGRAMADA = 0.85
ALPHA_FAIXA_PRESSAO_PROGRAMADA = 0.08
COR_MARCADOR_PRESSAO_FORA_LIMITE = "#FFFF00"
TAMANHO_MARCADOR_PRESSAO_FORA_LIMITE = 55

# --- Grade vertical (medição de tempo) ---
GRID_VERTICAL_ATIVO      = True       # liga/desliga a grade vertical
GRID_VERTICAL_INTERVALO  = 25         # segundos entre linhas verticais (0 = automático)
GRID_VERTICAL_COR        = "#B0B0B0"  # cinza claro
GRID_VERTICAL_ESTILO     = "--"       # tracejado
GRID_VERTICAL_ALPHA      = 0.5        # transparência
GRID_VERTICAL_LARGURA    = 0.8        # espessura da linha

# ============================================================
# VARIAVEIS GLOBAIS
# ============================================================
root: Any = None
fig: Any = None
ax: Any = None
canvas: Any = None
toolbar: Any = None
protocolo_var: Any = None
entry_ip: Any = None
entry_flag_monitor_status: Any = None
entry_offset_modbus: Any = None
status_var: Any = None
label_status: Any = None
label_vetor_status: Any = None
label_tempos_sob_pressao: Any = None
label_tempos_ventilacao: Any = None
canal_entries = []
trigger_enable_var: Any = None
trigger_tipo_var: Any = None
trigger_stop_zero_var: Any = None
entry_trigger: Any = None

btn_start: Any = None
btn_pause: Any = None
btn_stop: Any = None
btn_reset_zoom: Any = None
btn_testar_vetor: Any = None
btn_diagnostico_modbus: Any = None
ultima_comunicacao_ok = 0.0
ultimo_trigger_lido = 0
ultimo_monitor_status = STATUS_AGUARDANDO_INICIO
ultimo_arquivo_salvo = ""
# ALT26 - histórico somente da sessão atual, protegido entre backend e thread de salvamento.
historico_resultados = []
historico_resultados_lock = threading.Lock()

# ALT28A - estado do tratamento e rastreabilidade do valor bruto
ultima_pressao_lida_valida = None
leituras_invalidas_pressao_consecutivas = 0
total_leituras_invalidas_pressao = 0
falha_persistente_pressao = False
pressao_lida_bruta_por_timestamp = {}
pressao_lida_bruta_lock = threading.Lock()
modo_html_ativo = False
mensagem_html = "Pronto."
config_html = {
    "ip": "172.25.217.210",
    "protocolo": "SCHNEIDER",
    "porta": 502,
    "offset_modbus": 0,
    "trigger": "MW3000:BOOL:0",
    "flag_monitor_status": "%MW3004",
    "tipo_trigger": "NIVEL",
    "trigger_habilitado": True,
    "monitorar_pressao_zero": False,
    "tags": ["MW413:UINT", "MW3002:UINT", "MW515:UINT"],
"temperatura_programada_tag": TEMPERATURA_PROGRAMADA_PADRAO,
"temperatura_lida_1_tag": TEMPERATURA_LIDA_1_PADRAO,
"temperatura_lida_2_tag": TEMPERATURA_LIDA_2_PADRAO,
}

thread_aquisicao: Any = None
thread_salvamento: Any = None

rodando = False
pausado = False
fechando = False
buffers = []
tags_ativas = []
# Vetor com as durações (em segundos) de cada período de Tempo Sob Pressão do ciclo atual.
tempos_sob_pressao = []
# Vetor com as durações (em segundos) de cada ventilação do ciclo atual.
tempos_ventilacao = []
fila_salvamento = queue.Queue()
ultimo_vetor_m340 = []
ultimo_vetor_m340_descrito = []
limite_pressao_programada_min = None
limite_pressao_programada_max = None
linha_limite_pressao_prog_min = None
linha_limite_pressao_prog_max = None
faixa_limite_pressao_programada = None
marcadores_pressao_fora_limites = None
zoom_usuario_ativo = False
pan_usuario_ativo = False
pan_inicio = None

_FORM_ITEMS = [
    ("%MW17000-%MW17005", "0-5", "FORM[0].Formulacao", "Formulação", "STRING[12]", 0, 6),
    ("%MW17006-%MW17011", "6-11", "FORM[0].Material", "Material", "STRING[12]", 6, 6),
    ("%MW17012", "12", "FORM[0].Temperatura", "Temperatura", "UINT", 12, 1),
    ("%MW17013", "13", "FORM[0].Pressao", "Pressão programada", "UINT", 13, 1),
    ("%MW17014", "14", "FORM[0].NumeroDeVentilacoes", "Número de ventilações", "UINT", 14, 1),
    ("%MW17015", "15", "FORM[0].RecuperacaoDePressao", "Recuperação de pressão", "UINT", 15, 1),
    ("%MW17016", "16", "FORM[0].TempoSobPressao", "Tempo sob pressão", "UINT", 16, 1),
    ("%MW17017", "17", "FORM[0].TempoAbrindoParaVentilar", "Tempo abrindo para ventilar", "UINT", 17, 1),
    ("%MW17018", "18", "FORM[0].TempoAbertaVentilado", "Tempo aberta ventilado", "UINT", 18, 1),
    ("%MW17019", "19", "FORM[0].TempoFinalSobPressao", "Tempo final sob pressão", "UINT", 19, 1),
    ("%MW17020", "20", "FORM[0].TempoTotalDeCiclo", "Tempo total de ciclo", "UINT", 20, 1),
    ("%MW17021", "21", "FORM[0].ToleranciaDePressao", "Tolerância de pressão", "UINT", 21, 1),
    ("%MW17022", "22", "FORM[0].ToleranciaDeTemperatura", "Tolerância de temperatura", "UINT", 22, 1),
    ("%MW17023", "23", "FORM[0].ToleranciaDeAjusteTemperaturaZonas", "Tolerância de ajuste temperatura zonas", "UINT", 23, 1),
    ("%MW17024", "24", "FORM[0].TemperaturaAjustada", "Temperatura ajustada", "UINT", 24, 1),
    ("%MW17025", "25", "FORM[0].Peso", "Peso", "UINT", 25, 1),
    ("%MW17026", "26", "FORM[0].ToleranciaDePeso", "Tolerância de peso", "UINT", 26, 1),
    ("%MW17027", "27", "FORM[0].VelocidadePercentual1", "Velocidade percentual 1", "UINT", 27, 1),
    ("%MW17028", "28", "FORM[0].PesoParaTrocaVelocidade1", "Peso para troca velocidade 1", "UINT", 28, 1),
    ("%MW17029", "29", "FORM[0].VelocidadePercentual2", "Velocidade percentual 2", "UINT", 29, 1),
    ("%MW17030", "30", "FORM[0].PesoParaTrocaVelocidade2", "Peso para troca velocidade 2", "UINT", 30, 1),
    ("%MW17031", "31", "FORM[0].VelocidadePercentual3", "Velocidade percentual 3", "UINT", 31, 1),
    ("%MW17032", "32", "FORM[0].TempoDeEstabilizacao", "Tempo de estabilização", "UINT", 32, 1),
    ("%MW17033", "33", "FORM[0].DesmoldanteConcentrado", "Desmoldante concentrado", "UINT", 33, 1),
    ("%MW17034", "34", "FORM[0].Reserva[0]", "Reserva 0", "WORD", 34, 1),
    ("%MW17035", "35", "FORM[0].Reserva[1]", "Reserva 1", "WORD", 35, 1),
    ("%MW17036", "36", "FORM[0].Reserva[2]", "Reserva 2", "WORD", 36, 1),
    ("%MW17037", "37", "FORM[0].PosicaoAbrindoParaVentilar", "Posição abrindo para ventilar", "UINT", 37, 1),
    ("%MW17038", "38", "FORM[0].PesoProgramado2", "Peso programado 2", "UINT", 38, 1),
    ("%MW17039", "39", "FORM[0].FlagValoresAtualizados", "Flag valores atualizados", "UINT", 39, 1),
    ("%MW17040", "40", "FORM[0].PressaoEspecifica", "Pressão específica", "UINT", 40, 1),
]
MAPA_FORM_M340 = [
    {"endereco": a, "indice": i, "nome": n, "descricao": d, "tipo": t, "inicio": ini, "quantidade": q}
    for a, i, n, d, t, ini, q in _FORM_ITEMS
]

# ============================================================
# AUXILIARES E MODBUS
# ============================================================
def set_status(texto, cor=None):
    global mensagem_html
    mensagem_html = str(texto)
    if modo_html_ativo:
        return
    try:
        if status_var is not None:
            status_var.set(texto)
        if label_status is not None and cor is not None:
            label_status.configure(foreground=cor)
        if root is not None:
            root.update_idletasks()
    except Exception:
        pass

def set_vetor_status(texto, cor=None):
    try:
        if label_vetor_status is not None:
            label_vetor_status.configure(text=texto)
            if cor is not None: label_vetor_status.configure(foreground=cor)
        if root is not None: root.update_idletasks()
    except Exception: pass

def atualizar_label_tempos_sob_pressao():
    """Atualiza o painel da interface com o vetor de Tempo Sob Pressão (thread-safe)."""
    def _aplicar():
        try:
            if label_tempos_sob_pressao is None: return
            if not tempos_sob_pressao:
                label_tempos_sob_pressao.configure(text="Nenhum período detectado ainda.")
            else:
                itens = "  |  ".join(f"{i+1}: {v:.2f}s" for i, v in enumerate(tempos_sob_pressao))
                total = sum(tempos_sob_pressao)
                label_tempos_sob_pressao.configure(
                    text=f"{itens}     →  {len(tempos_sob_pressao)} período(s) | Total: {total:.2f}s")
        except Exception: pass
    try:
        if root is not None: root.after(0, _aplicar)
    except Exception: pass

def atualizar_label_tempos_ventilacao():
    """Atualiza o painel da interface com o vetor de Tempo de Alívio de Pressão (thread-safe)."""
    def _aplicar():
        try:
            if label_tempos_ventilacao is None: return
            if not tempos_ventilacao:
                label_tempos_ventilacao.configure(text="Nenhum alívio de pressão detectado ainda.")
            else:
                itens = "  |  ".join(f"{i+1}: {v:.2f}s" for i, v in enumerate(tempos_ventilacao))
                total = sum(tempos_ventilacao)
                label_tempos_ventilacao.configure(
                    text=f"{itens}     →  {len(tempos_ventilacao)} alívio(s) de pressão | Total: {total:.2f}s")
        except Exception: pass
    try:
        if root is not None: root.after(0, _aplicar)
    except Exception: pass

def obter_offset_modbus():
    if modo_html_ativo:
        try:
            return int(config_html.get("offset_modbus", 0))
        except (TypeError, ValueError):
            return 0
    try:
        texto = entry_offset_modbus.get().strip() if entry_offset_modbus else "0"
        return int(texto) if texto else 0
    except Exception:
        return 0

def aplicar_offset(register): return int(register) + obter_offset_modbus()

def parse_mw_address(endereco):
    texto = str(endereco).strip().upper().replace("%", "").replace(" ", "")
    if texto.startswith("MW"): texto = texto[2:]
    if not texto.isdigit(): raise ValueError(f"Endereço MW inválido: {endereco}")
    return int(texto)

def parse_schneider_tag(tag):
    if tag is None or not str(tag).strip(): return None
    partes = str(tag).strip().upper().split(":")
    return {"register": parse_mw_address(partes[0]),
            "tipo": partes[1].strip() if len(partes) >= 2 and partes[1].strip() else "INT",
            "bit": int(partes[2]) if len(partes) >= 3 and partes[2].strip() else None}


# ============================================================
# ALT29B - INTEGRACAO CONFIGURACAO -> TAGS -> AQUISICAO
# ============================================================

def obter_estado_configuracao_temperaturas():
    temperaturas = [
        str(config_html.get("temperatura_programada_tag", "") or "").strip(),
        str(config_html.get("temperatura_lida_1_tag", "") or "").strip(),
        str(config_html.get("temperatura_lida_2_tag", "") or "").strip(),
    ]
    preenchidas = sum(bool(tag) for tag in temperaturas)
    return temperaturas, preenchidas == 3, 0 < preenchidas < 3


def montar_tags_ativas_html():
    tags_salvas = list(config_html.get("tags") or [])
    padroes = [PRESSAO_LIDA_PADRAO, PRESSAO_PROGRAMADA_PADRAO, INERCIA_PRESSAO_PADRAO]
    tags_pressao = []
    for indice, padrao in enumerate(padroes):
        valor = tags_salvas[indice] if indice < len(tags_salvas) else padrao
        valor = str(valor or padrao).strip()
        parse_schneider_tag(valor)
        tags_pressao.append(valor)

    temperaturas, completa, parcial = obter_estado_configuracao_temperaturas()
    if parcial:
        mensagem = "Configuracao de temperatura incompleta. Aquisicao termica desabilitada."
        print(f"[AVISO ALT29B] {mensagem}")
        set_status(mensagem, "orange")
        return tags_pressao

    if completa:
        for tag in temperaturas:
            parse_schneider_tag(tag)
        return tags_pressao + temperaturas

    return tags_pressao


def imprimir_diagnostico_tags_alt29b(tags):
    print("[ALT29B] Tags ativas para aquisicao:")
    for indice, tag in enumerate(tags):
        print(f"[ALT29B] {indice} - {tag}")
    print(f"[ALT29B] Quantidade de canais: {len(tags)}")
    print(f"[ALT29B] Quantidade de buffers: {len(buffers)}")


def ler_tag_schneider(ip, tag):
    if read_mw is None: raise RuntimeError("Função read_mw não disponível.")
    info = parse_schneider_tag(tag)
    if info is None: return None
    return read_mw(ip, aplicar_offset(info["register"]), tipo=info["tipo"], bit=info["bit"])

def escrever_mw_schneider(ip, register, value):
    reg = aplicar_offset(register)
    if write_mw_schneider is not None: return write_mw_schneider(ip, reg, value)
    if write_mw is not None: return write_mw(ip, reg, value)
    raise RuntimeError("Função de escrita Modbus não disponível.")

def atualizar_flag_monitor_status(status):
    global ultimo_monitor_status
    ultimo_monitor_status = int(status)
    try:
        if modo_html_ativo:
            ip = str(config_html.get("ip", "")).strip()
            tag = str(config_html.get("flag_monitor_status", "")).strip()
        else:
            if not entry_ip or not entry_flag_monitor_status:
                return
            ip = entry_ip.get().strip()
            tag = entry_flag_monitor_status.get().strip()
        if ip and tag:
            escrever_mw_schneider(ip, parse_mw_address(tag), int(status))
    except Exception as e:
        print(f"[AVISO] Falha ao atualizar flag monitor status: {e}")

# ============================================================
# FORM[0]
# ============================================================
def decodificar_string_12(words):
    saida = []
    for w in words:
        w = int(w) & 0xFFFF
        alto, baixo = (w >> 8) & 0xFF, w & 0xFF
        saida.extend([baixo, alto] if STRING_BYTE_SWAP else [alto, baixo])
    return bytes(saida).decode("latin-1", errors="ignore").replace("\x00", "").strip()

def descrever_vetor_form_m340(valores):
    saida = []
    for item in MAPA_FORM_M340:
        fatia = valores[item["inicio"]:item["inicio"] + item["quantidade"]]
        valor = decodificar_string_12(fatia) if item["tipo"] == "STRING[12]" else (fatia[0] if item["quantidade"] == 1 and fatia else fatia)
        saida.append({**item, "valor": valor})
    return saida

def imprimir_vetor_form_m340_descrito(valores):
    descritos = descrever_vetor_form_m340(valores)
    print("\n" + "=" * 60 + "\nVETOR FORM[0] M340 - PARAMETROS LIDOS\n" + "=" * 60)
    for item in descritos: print(f"{item['indice']:>5} | {item['endereco']:<19} | {item['nome']:<45} | {item['valor']}")
    print("=" * 60 + "\n")
    return descritos

def obter_valor_form_m340(nome):
    return next((x["valor"] for x in ultimo_vetor_m340_descrito if x["nome"] == nome), None)

def calcular_limites_pressao_programada_form_m340():
    global limite_pressao_programada_min, limite_pressao_programada_max
    try:
        p = float(obter_valor_form_m340("FORM[0].Pressao"))
        tol = float(obter_valor_form_m340("FORM[0].ToleranciaDePressao"))
        limite_pressao_programada_min, limite_pressao_programada_max = p - tol, p + tol
        print(f"[INFO] Limites: min={limite_pressao_programada_min}, max={limite_pressao_programada_max}")
    except Exception as e:
        limite_pressao_programada_min = limite_pressao_programada_max = None
        print(f"[AVISO] Falha ao calcular limites: {e}")

def ler_vetor_parametros_m340(ip, inicio, quantidade):
    reg = aplicar_offset(inicio)
    if read_mw_block_auto is not None: return read_mw_block_auto(ip, reg, quantidade)
    if read_mw_block is not None: return read_mw_block(ip, reg, quantidade)
    raise RuntimeError("Funções de leitura em bloco não disponíveis.")

def ler_vetor_m340_automatico(ip):
    global ultimo_vetor_m340, ultimo_vetor_m340_descrito
    ultimo_vetor_m340 = list(ler_vetor_parametros_m340(ip, ENDERECO_VETOR_FORM_M340, QUANTIDADE_VETOR_FORM_M340))
    ultimo_vetor_m340_descrito = imprimir_vetor_form_m340_descrito(ultimo_vetor_m340)
    calcular_limites_pressao_programada_form_m340()
    set_vetor_status(f"Vetor M340 lido: {len(ultimo_vetor_m340)} registradores", "green")
    return ultimo_vetor_m340

def testar_leitura_vetor():
    try:
        valores = ler_vetor_m340_automatico(entry_ip.get().strip())
        messagebox.showinfo("Teste de leitura", f"Leitura OK.\n\n{len(valores)} registradores lidos.")
        atualizar_linhas_limite_pressao_programada()
    except Exception as e: messagebox.showerror("Erro", f"Falha na leitura do vetor:\n\n{e}")

def diagnostico_modbus_pontual():
    """
    ALT20A - Realiza uma fotografia pontual e somente leitura
    dos sinais utilizados pelo Oraculum.

    Esta função:
    - não inicia a monitoração;
    - não cria thread;
    - não escreve no CLP;
    - não altera buffers;
    - não altera configuração;
    - não altera a Alteração 19.
    """
    etapa = "configuração"

    try:
        ip = entry_ip.get().strip()

        if not ip:
            raise ValueError("Informe o IP do CLP.")

        trigger_configurado = entry_trigger.get().strip()

        if not trigger_configurado:
            trigger_configurado = TRIGGER_PADRAO

        linhas = [
            "DIAGNÓSTICO MODBUS",
            "",
            f"IP do CLP: {ip}",
            f"Offset Modbus: {obter_offset_modbus()}",
            "",
        ]

        # ====================================================
        # Trigger %MW3000
        # ====================================================
        etapa = "trigger"

        trigger_uint = int(
            ler_tag_schneider(
                ip,
                "MW3000:UINT",
            )
        ) & 0xFFFF

        trigger_int = (
            trigger_uint - 0x10000
            if trigger_uint >= 0x8000
            else trigger_uint
        )

        trigger_bit_0 = trigger_uint & 1

        trigger_configurado_lido = ler_tag_schneider(
            ip,
            trigger_configurado,
        )

        trigger_interpretado = (
            1
            if int(trigger_configurado_lido) != 0
            else 0
        )

        linhas.extend(
            [
                "Trigger %MW3000",
                f"UINT: {trigger_uint}",
                f"INT: {trigger_int}",
                f"Bit 0: {trigger_bit_0}",
                (
                    f"Interpretado por "
                    f"{trigger_configurado}: "
                    f"{trigger_interpretado}"
                ),
                "",
            ]
        )

        # ====================================================
        # Monitor Status %MW3004
        # ====================================================
        etapa = "monitor"

        monitor_uint = int(
            ler_tag_schneider(
                ip,
                "MW3004:UINT",
            )
        ) & 0xFFFF

        linhas.extend(
            [
                "Monitor %MW3004",
                f"UINT lido: {monitor_uint}",
                "",
            ]
        )

        # ====================================================
        # Canais utilizados pelo Oraculum
        # ====================================================
        etapa = "canais"

        pressao_lida_bruta = int(
            ler_tag_schneider(
                ip,
                PRESSAO_LIDA_PADRAO,
            )
        )

        pressao_programada_bruta = int(
            ler_tag_schneider(
                ip,
                PRESSAO_PROGRAMADA_PADRAO,
            )
        )

        inercia_pressao_bruta = int(
            ler_tag_schneider(
                ip,
                INERCIA_PRESSAO_PADRAO,
            )
        )

        linhas.extend(
            [
                "Canais",
                (
                    f"{PRESSAO_LIDA_PADRAO}: "
                    f"{pressao_lida_bruta}"
                ),
                (
                    f"{PRESSAO_PROGRAMADA_PADRAO}: "
                    f"{pressao_programada_bruta}"
                ),
                (
                    f"{INERCIA_PRESSAO_PADRAO}: "
                    f"{inercia_pressao_bruta}"
                ),
                "",
            ]
        )

        # ====================================================
        # Vetor FORM[0]
        # ====================================================
        etapa = "FORM[0]"

        valores_form = list(
            ler_vetor_parametros_m340(
                ip,
                ENDERECO_VETOR_FORM_M340,
                QUANTIDADE_VETOR_FORM_M340,
            )
        )

        quantidade_recebida = len(valores_form)

        form_completo = (
            quantidade_recebida
            == QUANTIDADE_VETOR_FORM_M340
        )

        linhas.extend(
            [
                "FORM[0]",
                f"Início: %MW{ENDERECO_VETOR_FORM_M340}",
                (
                    f"Recebido: "
                    f"{quantidade_recebida} / "
                    f"{QUANTIDADE_VETOR_FORM_M340}"
                ),
                (
                    f"Completo: "
                    f"{'sim' if form_completo else 'não'}"
                ),
            ]
        )

        resultado = "\n".join(linhas)

        print()
        print("=" * 60)
        print(resultado)
        print("=" * 60)
        print()

        messagebox.showinfo(
            "Diagnóstico Modbus",
            resultado,
        )

    except Exception as erro:
        mensagem = (
            "Falha no diagnóstico Modbus\n\n"
            f"Etapa: {etapa}\n"
            f"Erro: {erro}"
        )

        print()
        print("=" * 60)
        print(mensagem)
        print("=" * 60)
        print()

        messagebox.showerror(
            "Diagnóstico Modbus",
            mensagem,
        )
    """
    ALT20A - Realiza uma fotografia pontual e somente leitura
    dos sinais utilizados pelo Oraculum.

    Esta função:
    - não inicia a monitoração;
    - não cria thread;
    - não escreve no CLP;
    - não altera buffers;
    - não altera configuração;
    - não altera a Alteração 19.
    """
    etapa = "configuração"

    try:
        ip = entry_ip.get().strip()

        if not ip:
            raise ValueError("Informe o IP do CLP.")

        trigger_configurado = entry_trigger.get().strip()

        if not trigger_configurado:
            trigger_configurado = TRIGGER_PADRAO

        linhas = [
            "DIAGNÓSTICO MODBUS",
            "",
            f"IP do CLP: {ip}",
            f"Offset Modbus: {obter_offset_modbus()}",
            "",
        ]

        # ====================================================
        # Trigger %MW3000
        # ====================================================
        etapa = "trigger"

        trigger_uint = int(
            ler_tag_schneider(
                ip,
                "MW3000:UINT",
            )
        ) & 0xFFFF

        trigger_int = (
            trigger_uint - 0x10000
            if trigger_uint >= 0x8000
            else trigger_uint
        )

        trigger_bit_0 = trigger_uint & 1

        trigger_configurado_lido = ler_tag_schneider(
            ip,
            trigger_configurado,
        )

        trigger_interpretado = (
            1
            if int(trigger_configurado_lido) != 0
            else 0
        )

        linhas.extend(
            [
                "Trigger %MW3000",
                f"UINT: {trigger_uint}",
                f"INT: {trigger_int}",
                f"Bit 0: {trigger_bit_0}",
                (
                    f"Interpretado por "
                    f"{trigger_configurado}: "
                    f"{trigger_interpretado}"
                ),
                "",
            ]
        )

        # ====================================================
        # Monitor Status %MW3004
        # ====================================================
        etapa = "monitor"

        monitor_uint = int(
            ler_tag_schneider(
                ip,
                "MW3004:UINT",
            )
        ) & 0xFFFF

        linhas.extend(
            [
                "Monitor %MW3004",
                f"UINT lido: {monitor_uint}",
                "",
            ]
        )

        # ====================================================
        # Canais utilizados pelo Oraculum
        # ====================================================
        etapa = "canais"

        pressao_lida_bruta = int(
            ler_tag_schneider(
                ip,
                PRESSAO_LIDA_PADRAO,
            )
        )

        pressao_programada_bruta = int(
            ler_tag_schneider(
                ip,
                PRESSAO_PROGRAMADA_PADRAO,
            )
        )

        inercia_pressao_bruta = int(
            ler_tag_schneider(
                ip,
                INERCIA_PRESSAO_PADRAO,
            )
        )

        linhas.extend(
            [
                "Canais",
                (
                    f"{PRESSAO_LIDA_PADRAO}: "
                    f"{pressao_lida_bruta}"
                ),
                (
                    f"{PRESSAO_PROGRAMADA_PADRAO}: "
                    f"{pressao_programada_bruta}"
                ),
                (
                    f"{INERCIA_PRESSAO_PADRAO}: "
                    f"{inercia_pressao_bruta}"
                ),
                "",
            ]
        )

        # ====================================================
        # Vetor FORM[0]
        # ====================================================
        etapa = "FORM[0]"

        valores_form = list(
            ler_vetor_parametros_m340(
                ip,
                ENDERECO_VETOR_FORM_M340,
                QUANTIDADE_VETOR_FORM_M340,
            )
        )

        quantidade_recebida = len(valores_form)

        form_completo = (
            quantidade_recebida
            == QUANTIDADE_VETOR_FORM_M340
        )

        linhas.extend(
            [
                "FORM[0]",
                f"Início: %MW{ENDERECO_VETOR_FORM_M340}",
                (
                    f"Recebido: "
                    f"{quantidade_recebida} / "
                    f"{QUANTIDADE_VETOR_FORM_M340}"
                ),
                (
                    f"Completo: "
                    f"{'sim' if form_completo else 'não'}"
                ),
            ]
        )

        resultado = "\n".join(linhas)

        print()
        print("=" * 60)
        print(resultado)
        print("=" * 60)
        print()

        messagebox.showinfo(
            "Diagnóstico Modbus",
            resultado,
        )

    except Exception as erro:
        mensagem = (
            "Falha no diagnóstico Modbus\n\n"
            f"Etapa: {etapa}\n"
            f"Erro: {erro}"
        )

        print()
        print("=" * 60)
        print(mensagem)
        print("=" * 60)
        print()

        messagebox.showerror(
            "Diagnóstico Modbus",
            mensagem,
        )

# ============================================================
# GRAFICO E MARCADORES
# ============================================================
def cor_do_canal(i): return CORES_CANAIS[i % len(CORES_CANAIS)]

def aplicar_estilo_grafico(eixo=None, figura=None):
    eixo, figura = eixo or ax, figura or fig
    if eixo is None or figura is None: return
    figura.patch.set_facecolor(PALETA_GRAFICO["fundo_figura"])
    eixo.set_facecolor(PALETA_GRAFICO["fundo_eixos"])
    eixo.grid(True, which="major", color=PALETA_GRAFICO["grade_principal"], linewidth=0.8)
    eixo.grid(True, which="minor", color=PALETA_GRAFICO["grade_secundaria"], linewidth=0.5)
    eixo.minorticks_on(); eixo.set_xlabel("Tempo (s)"); eixo.set_ylabel("Pressão (kgf/cm²)")
    eixo.set_title("Oraculum - Osciloscópio Industrial")
    # Grade vertical para medição do tempo (eixo X). Mesma na tela e no PNG.
    if GRID_VERTICAL_ATIVO:
        if GRID_VERTICAL_INTERVALO > 0:
            eixo.xaxis.set_major_locator(MultipleLocator(GRID_VERTICAL_INTERVALO))
        eixo.grid(True, axis="x", which="major", linestyle=GRID_VERTICAL_ESTILO,
                  color=GRID_VERTICAL_COR, alpha=GRID_VERTICAL_ALPHA,
                  linewidth=GRID_VERTICAL_LARGURA)

def aplicar_estilo_legenda(eixo=None):
    eixo = eixo or ax
    if eixo is None: return
    leg = eixo.legend(loc="best")
    if leg:
        leg.get_frame().set_facecolor(PALETA_GRAFICO["legenda_fundo"])
        leg.get_frame().set_edgecolor(PALETA_GRAFICO["legenda_borda"])

def resetar_linhas_limite_pressao_programada():
    global linha_limite_pressao_prog_min, linha_limite_pressao_prog_max, faixa_limite_pressao_programada
    linha_limite_pressao_prog_min = linha_limite_pressao_prog_max = faixa_limite_pressao_programada = None

def obter_intervalos_pressao_programada_ativa(dados_buffers):
    """ALT8 - (x_ini, x_fim) em tempo relativo para cada trecho com MW3002 > LIMIAR_PRESSAO_PROGRAMADA_ATIVA."""
    intervalos = []
    try:
        if not dados_buffers or INDICE_PRESSAO_PROGRAMADA >= len(dados_buffers):
            return intervalos
        b = dados_buffers[INDICE_PRESSAO_PROGRAMADA]
        if not b:
            return intervalos
        t0 = b[0][0]; inicio = None; anterior = None
        for tempo, valor in b:
            try:
                ativo = float(valor) > LIMIAR_PRESSAO_PROGRAMADA_ATIVA
            except (TypeError, ValueError):
                ativo = False
            x = tempo - t0
            if ativo and inicio is None:
                inicio = x
            elif not ativo and inicio is not None:
                intervalos.append((inicio, anterior if anterior is not None else x)); inicio = None
            anterior = x
        if inicio is not None:
            intervalos.append((inicio, anterior))
    except Exception:
        return intervalos
    return intervalos

def desenhar_limites_pressao_programada(eixo, dados_buffers=None):
    """ALT8 - Desenha limites (min./max.) e faixa APENAS nos trechos com MW3002 > 0."""
    global linha_limite_pressao_prog_min, linha_limite_pressao_prog_max, faixa_limite_pressao_programada
    if eixo is None or limite_pressao_programada_min is None or limite_pressao_programada_max is None: return
    dados = buffers if dados_buffers is None else dados_buffers
    intervalos = obter_intervalos_pressao_programada_ativa(dados)
    if not intervalos: return
    primeiro = True
    for x_ini, x_fim in intervalos:
        label_min = "Limite pressao min." if primeiro else "_nolegend_"
        label_max = "Limite pressao max." if primeiro else "_nolegend_"
        linha_limite_pressao_prog_min = eixo.hlines(limite_pressao_programada_min, x_ini, x_fim, color=COR_LIMITE_PRESSAO_PROGRAMADA, linestyle=ESTILO_LIMITE_PRESSAO_PROGRAMADA, linewidth=ESPESSURA_LIMITE_PRESSAO_PROGRAMADA, alpha=ALPHA_LIMITE_PRESSAO_PROGRAMADA, label=label_min)
        linha_limite_pressao_prog_max = eixo.hlines(limite_pressao_programada_max, x_ini, x_fim, color=COR_LIMITE_PRESSAO_PROGRAMADA, linestyle=ESTILO_LIMITE_PRESSAO_PROGRAMADA, linewidth=ESPESSURA_LIMITE_PRESSAO_PROGRAMADA, alpha=ALPHA_LIMITE_PRESSAO_PROGRAMADA, label=label_max)
        faixa_limite_pressao_programada = eixo.fill_between([x_ini, x_fim], limite_pressao_programada_min, limite_pressao_programada_max, color=COR_FAIXA_PRESSAO_PROGRAMADA, alpha=ALPHA_FAIXA_PRESSAO_PROGRAMADA)
        primeiro = False

def calcular_pontos_pressao_fora_limites(
    dados_buffers,
    limite_minimo,
    limite_maximo,
):
    """
    Calcula os pontos de pressão fora dos limites programados.

    Regras:
    - CH1 contém a pressão real.
    - CH2 indica a fase ativa.
    - CH2 igual a zero representa ventilação ou intervalo.
    - O limite inferior só é analisado após a pressão entrar na faixa.
    - O limite inferior usa margem de 10 unidades.
    - O limite superior é analisado durante toda a fase ativa.
    """

    pontos_x = []
    pontos_y = []

    if limite_minimo is None or limite_maximo is None:
        return pontos_x, pontos_y

    if not dados_buffers or len(dados_buffers) < 2:
        return pontos_x, pontos_y

    if len(dados_buffers) <= INDICE_CANAL_PRESSAO:
        return pontos_x, pontos_y

    buffer_pressao = dados_buffers[INDICE_CANAL_PRESSAO]
    buffer_fase = dados_buffers[1]

    if not buffer_pressao or not buffer_fase:
        return pontos_x, pontos_y

    quantidade = min(
        len(buffer_pressao),
        len(buffer_fase),
    )

    if quantidade <= 0:
        return pontos_x, pontos_y

    tempo_inicial = buffer_pressao[0][0]

    fase_ativa_anterior = False
    faixa_atingida = False

    for i in range(quantidade):
        try:
            tempo_relativo = (
                float(buffer_pressao[i][0])
                - float(tempo_inicial)
            )

            pressao = float(buffer_pressao[i][1])
            fase = float(buffer_fase[i][1])

        except (TypeError, ValueError):
            continue

        fase_ativa = fase > 0

        # Início de uma nova fase ativa.
        if fase_ativa and not fase_ativa_anterior:
            faixa_atingida = False

        # CH2 igual a zero representa ventilação ou intervalo.
        if not fase_ativa:
            faixa_atingida = False
            fase_ativa_anterior = False
            continue

        # Registra quando a pressão entra na faixa programada.
        if limite_minimo <= pressao <= limite_maximo:
            faixa_atingida = True

        # O limite superior é analisado durante toda a fase ativa.
        # Não depende da pressão ter entrado anteriormente na faixa.
        acima_limite = (
            pressao > limite_maximo
        )

        # ALT13 - look-ahead: se o MW3002 zera na PROXIMA amostra, esta e a borda
        # de despressurizacao (Pressao Lida descendo p/ zero) -> nao e violacao inferior.
        despressurizando = False
        if i + 1 < quantidade:
            try:
                fase_proxima = float(buffer_fase[i + 1][1])
                despressurizando = fase_proxima <= LIMIAR_PRESSAO_PROGRAMADA_ATIVA
            except (TypeError, ValueError):
                despressurizando = False

        # O limite inferior somente é analisado depois que
        # a pressão entrou na faixa programada.
        # ALT13 - suprime o inferior na borda de despressurizacao (descida p/ zero).
        abaixo_limite = (
            faixa_atingida
            and pressao < limite_minimo
            and pressao >= limite_minimo - 20
            and not despressurizando
        )

        if abaixo_limite or acima_limite:
            pontos_x.append(tempo_relativo)
            pontos_y.append(pressao)

        fase_ativa_anterior = fase_ativa

    return pontos_x, pontos_y


def desenhar_marcadores_pressao_fora_limites(eixo, dados_buffers=None):
    global marcadores_pressao_fora_limites
    dados = buffers if dados_buffers is None else dados_buffers
    x, y = calcular_pontos_pressao_fora_limites(dados, limite_pressao_programada_min, limite_pressao_programada_max)
    if not x: return
    marcadores_pressao_fora_limites = eixo.scatter(x, y, color=COR_MARCADOR_PRESSAO_FORA_LIMITE, edgecolors="#B8860B", linewidths=0.8, s=TAMANHO_MARCADOR_PRESSAO_FORA_LIMITE, zorder=25, label="Pressão fora dos limites")

def atualizar_linhas_limite_pressao_programada():
    resetar_linhas_limite_pressao_programada()
    if ax is not None:
        desenhar_limites_pressao_programada(ax, buffers); aplicar_estilo_legenda(ax)
    if canvas is not None: canvas.draw_idle()

# ============================================================
# SALVAMENTO
# ============================================================
def obter_pasta_saida():
    p = os.path.join(os.getcwd(), "resultados_oraculum"); os.makedirs(p, exist_ok=True); return p

def salvar_parametros_form_m340_descritos(base, snapshot_form=None):
    # ALT24C - usa a fotografia do FORM[0] feita no encerramento do ciclo.
    dados_form = snapshot_form if snapshot_form is not None else ultimo_vetor_m340_descrito
    if not dados_form:
        return None
    caminho = base + "_parametros_form_m340.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Endereco", "Indice", "Nome", "Descricao", "Tipo", "Valor"])
        for x in dados_form:
            w.writerow([x["endereco"], x["indice"], x["nome"], x["descricao"], x["tipo"], x["valor"]])
    return caminho

def formatar_vetor_para_png(titulo, vetor, unidade_nome):
    """ALT16 - Formata um vetor de durações para o rodapé do PNG (linha única)."""
    if not vetor:
        return f"{titulo}: nenhum registrado."
    itens = " | ".join(f"{i+1}: {v:.2f}" for i, v in enumerate(vetor))
    total = sum(vetor)
    return f"{titulo} (s): {itens}   ->  {len(vetor)} {unidade_nome} | Total: {total:.2f}s"

def salvar_png_snapshot(caminho_png, snapshot_buffers, snapshot_tags):
    fs = Figure(figsize=(12, 7), dpi=150); axs = fs.add_subplot(111); aplicar_estilo_grafico(axs, fs)   # ALT16: altura 7 (era 6)
    for i, b in enumerate(snapshot_buffers):
        if not b: continue
        if i in INDICES_NAO_PLOTAR: continue  # Não plotar Inércia (MW515).
        t0 = b[0][0]; axs.plot([p[0]-t0 for p in b], [p[1] for p in b], color=cor_do_canal(i), linewidth=1.3, label=f"CH{i+1} - {snapshot_tags[i] if i < len(snapshot_tags) else f'CH{i+1}'}")
    desenhar_limites_pressao_programada(axs, snapshot_buffers)
    desenhar_marcadores_pressao_fora_limites(axs, snapshot_buffers)
    axs.relim(); axs.autoscale_view()
    x0, x1 = axs.get_xlim(); axs.set_xlim(x0 - MARGEM_EIXO_X_S, x1 + MARGEM_EIXO_X_S)   # ALT14
    ajustar_eixo_y_para_limites(axs)   # ALT9
    aplicar_estilo_legenda(axs)
    # ALT25 - rodapé com os vetores de Tempo Sob Pressão e Tempo de Alívio de Pressão.
    vetor_sp = obter_vetor_tempos_sob_pressao(snapshot_buffers)
    vetor_vt = obter_vetor_tempos_ventilacao(snapshot_buffers)
    texto_sp = formatar_vetor_para_png("Tempo Sob Pressão", vetor_sp, "período(s)")
    texto_vt = formatar_vetor_para_png("Tempo de Alívio de Pressão", vetor_vt, "alívio(s) de pressão")
    fs.text(0.01, 0.06, texto_sp, ha="left", va="center", fontsize=8, family="monospace", color="#0057B8")
    fs.text(0.01, 0.02, texto_vt, ha="left", va="center", fontsize=8, family="monospace", color="#F28E2B")
    fs.tight_layout(rect=[0, 0.08, 1, 1])   # ALT16: reserva a faixa inferior para o texto
    fs.savefig(caminho_png)


# ============================================================
# ALT27A - CONSULTA DETALHADA DE CICLO (SOMENTE LEITURA)
# ============================================================

def _alt27a_numero(valor, padrao=0.0):
    try:
        return float(str(valor).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return padrao


def _alt27a_validar_base(arquivo_base):
    nome = os.path.basename(str(arquivo_base or '').strip())
    if not nome or nome != str(arquivo_base or '').strip():
        raise ValueError('Arquivo-base inválido.')
    if not nome.startswith('ciclo_'):
        raise ValueError('O arquivo-base não pertence a um ciclo do Oraculum.')
    return nome


def _alt27a_ler_dicts(caminho):
    if not os.path.isfile(caminho):
        return []
    with open(caminho, 'r', newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f, delimiter=';'))


def _alt27a_ler_periodos(caminho, sob_pressao=False):
    itens = []
    for linha in _alt27a_ler_dicts(caminho):
        if not str(linha.get('Periodo', '')).strip().isdigit():
            continue
        item = {
            'numero': int(linha['Periodo']),
            'inicio_s': _alt27a_numero(linha.get('Inicio_s')),
            'fim_s': _alt27a_numero(linha.get('Fim_s')),
            'duracao_s': _alt27a_numero(linha.get('Duracao_s')),
        }
        if sob_pressao:
            item['pressao_inicio'] = _alt27a_numero(linha.get('Pressao_no_inicio'))
            item['limiar'] = _alt27a_numero(linha.get('Limiar'))
        itens.append(item)
    return itens


def _alt27a_ler_form(caminho):
    itens = []
    for linha in _alt27a_ler_dicts(caminho):
        itens.append({
            'endereco': linha.get('Endereco', ''),
            'indice': linha.get('Indice', ''),
            'nome': linha.get('Nome', ''),
            'descricao': linha.get('Descricao', ''),
            'tipo': linha.get('Tipo', ''),
            'valor': linha.get('Valor', ''),
        })
    return itens


def _alt27a_contar_amostras(caminho_csv):
    if not os.path.isfile(caminho_csv):
        return 0
    with open(caminho_csv, 'r', newline='', encoding='utf-8-sig') as f:
        leitor = csv.reader(f, delimiter=';')
        next(leitor, None)
        return sum(1 for linha in leitor if linha and any(str(v).strip() for v in linha))


def consultar_detalhes_ciclo(arquivo_base):
    """ALT27A - Consulta arquivos já salvos, sem acessar o CLP ou alterar o salvamento."""
    try:
        nome = _alt27a_validar_base(arquivo_base)
        base = os.path.join(obter_pasta_saida(), nome)
        caminhos = {
            'csv': base + '.csv',
            'png': base + '.png',
            'periodos': base + '_periodos_sob_pressao.csv',
            'tempos_sp': base + '_tempos_sob_pressao.csv',
            'alivios': base + '_tempos_ventilacao.csv',
            'form': base + '_parametros_form_m340.csv',
        }
        periodos = _alt27a_ler_periodos(
            caminhos['periodos'] if os.path.isfile(caminhos['periodos']) else caminhos['tempos_sp'],
            sob_pressao=True,
        )
        alivios = _alt27a_ler_periodos(caminhos['alivios'])
        parametros = _alt27a_ler_form(caminhos['form'])
        ausentes = [os.path.basename(v) for v in caminhos.values() if not os.path.isfile(v)]
        png_base64 = ''
        if os.path.isfile(caminhos['png']):
            with open(caminhos['png'], 'rb') as f:
                png_base64 = base64.b64encode(f.read()).decode('ascii')
        numero = 0
        data_hora = ''
        m = re.match(r'^(?:Maquina_[0-9A-Za-z_-]+_)?ciclo_(\d+)_(\d{8})_(\d{6})$', nome)
        if m:
            numero = int(m.group(1))
            try:
                data_hora = datetime.strptime(m.group(2) + m.group(3), '%Y%m%d%H%M%S').strftime('%d/%m/%Y %H:%M:%S')
            except ValueError:
                pass
        return {
            'sucesso': True,
            'mensagem': 'Detalhes carregados.' if not ausentes else 'Detalhes carregados com arquivos ausentes.',
            'arquivo_base': nome,
            'numero_ciclo': numero,
            'data_hora': data_hora,
            'quantidade_amostras': _alt27a_contar_amostras(caminhos['csv']),
            'tempo_total_sob_pressao_s': round(sum(x['duracao_s'] for x in periodos), 3),
            'quantidade_periodos_sob_pressao': len(periodos),
            'tempo_total_alivio_pressao_s': round(sum(x['duracao_s'] for x in alivios), 3),
            'quantidade_alivios_pressao': len(alivios),
            'periodos_sob_pressao': periodos,
            'periodos_alivio_pressao': alivios,
            'parametros_form': parametros,
            'png_base64': png_base64,
            'arquivos_ausentes': ausentes,
        }
    except Exception as e:
        return {'sucesso': False, 'mensagem': f'Falha ao consultar ciclo: {e}'}


def _copiar_historico_resultados():
    """ALT26 - entrega uma cópia segura, mais recente primeiro."""
    with historico_resultados_lock:
        return [dict(item) for item in reversed(historico_resultados)]


def _registrar_resultado_ciclo(resultado):
    """ALT26 - registra no máximo um resultado por número de ciclo e arquivo-base."""
    chave = (resultado.get("numero_ciclo"), resultado.get("arquivo_base"))
    with historico_resultados_lock:
        if any((r.get("numero_ciclo"), r.get("arquivo_base")) == chave for r in historico_resultados):
            print(f"[AVISO RESULTADO] Ciclo já existente no histórico: {chave}")
            return False
        historico_resultados.append(dict(resultado))
        if len(historico_resultados) > MAX_RESULTADOS_SESSAO:
            del historico_resultados[:-MAX_RESULTADOS_SESSAO]
    print(f"[INFO RESULTADO] Ciclo {resultado.get('numero_ciclo')} adicionado ao histórico: {resultado.get('status_geral')}")
    return True


def salvar_ciclo_automatico(snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form=None):
    """ALT24C/ALT26 - salva artefatos e consolida o resultado real da sessão."""
    global ultimo_arquivo_salvo
    instante = datetime.now()
    # === ALT32C: NOME DEFINITIVO COM MAQUINA ===
    maquina = _alt32b_extrair_maquina(snapshot_form) or _alt32a_fotografar_maquina() or {}
    maquina_id = _alt32a_id_seguro(maquina.get("id") or "nao_identificada")
    arquivo_base = (
        f"Maquina_{maquina_id}_"
        f"ciclo_{int(numero_ciclo):04d}_"
        f"{instante:%Y%m%d_%H%M%S}"
    )
    base = os.path.join(obter_pasta_saida(), arquivo_base)
    max_len = max((len(b) for b in snapshot_buffers), default=0)
    if max_len <= 0:
        print(f"[ERRO SALVAMENTO CSV] Ciclo {numero_ciclo} sem amostras no snapshot.")
        return False

    try:
        vetor_sp = obter_vetor_tempos_sob_pressao(snapshot_buffers)
    except Exception as e:
        vetor_sp = []
        print(f"[ERRO RESULTADO] Falha ao consolidar Tempo Sob Pressão: {type(e).__name__}: {e}")
    try:
        vetor_alivio = obter_vetor_tempos_ventilacao(snapshot_buffers)
    except Exception as e:
        vetor_alivio = []
        print(f"[ERRO RESULTADO] Falha ao consolidar Alívio de Pressão: {type(e).__name__}: {e}")

    estados = {"csv_salvo": False, "png_salvo": False, "form_salvo": False}
    erros = []
    caminho_csv = base + ".csv"
    try:
        t0 = next((b[0][0] for b in snapshot_buffers if b), time.time())
        with open(caminho_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["MAQUINA", "Amostra", "Tempo_s"] + [f"CH{i+1}_{t}" for i, t in enumerate(snapshot_tags)])
            for idx in range(max_len):
                tempo = next((b[idx][0] - t0 for b in snapshot_buffers if idx < len(b)), "")
                w.writerow([maquina_id, idx, tempo] + [b[idx][1] if idx < len(b) else "" for b in snapshot_buffers])
        estados["csv_salvo"] = True
        print(f"[INFO] CSV salvo com sucesso: {caminho_csv}")
    except Exception as e:
        erros.append(f"CSV: {type(e).__name__}: {e}")
        print(f"[ERRO SALVAMENTO CSV] {type(e).__name__}: {e}")
        traceback.print_exc()

    caminho_png = base + ".png"
    try:
        salvar_png_snapshot(caminho_png, snapshot_buffers, snapshot_tags)
        estados["png_salvo"] = True
        print(f"[INFO] PNG salvo com sucesso: {caminho_png}")
    except Exception as e:
        erros.append(f"PNG: {type(e).__name__}: {e}")
        print(f"[ERRO SALVAMENTO PNG] {type(e).__name__}: {e}")
        traceback.print_exc()

    tarefas = [
        ("FORM[0]", "form_salvo", lambda: salvar_parametros_form_m340_descritos(base, snapshot_form)),
        ("PERIODOS SOB PRESSAO", None, lambda: salvar_periodos_sob_pressao(base, snapshot_buffers)),
        ("TEMPOS SOB PRESSAO", None, lambda: salvar_tempos_sob_pressao(base, snapshot_buffers)),
        ("TEMPOS VENTILACAO", None, lambda: salvar_tempos_ventilacao(base, snapshot_buffers)),
    ]
    complementares_ok = True
    for nome, campo_estado, tarefa in tarefas:
        try:
            caminho = tarefa()
            tarefa_ok = caminho is not None
            if campo_estado:
                estados[campo_estado] = tarefa_ok
            if tarefa_ok:
                print(f"[INFO] {nome} salvo com sucesso: {caminho[0] if isinstance(caminho, tuple) else caminho}")
            else:
                complementares_ok = False
                erros.append(f"{nome}: dados não disponíveis")
        except Exception as e:
            complementares_ok = False
            erros.append(f"{nome}: {type(e).__name__}: {e}")
            print(f"[ERRO SALVAMENTO {nome}] {type(e).__name__}: {e}")
            traceback.print_exc()

    obrigatorios_ok = estados["csv_salvo"] and estados["png_salvo"]
    algum_salvo = any(estados.values())
    if obrigatorios_ok and estados["form_salvo"] and complementares_ok:
        status_geral = "Salvo com sucesso"
    elif algum_salvo:
        status_geral = "Salvo parcialmente"
    else:
        status_geral = "Erro de salvamento"

    mensagem_resultado = "Todos os artefatos foram salvos." if status_geral == "Salvo com sucesso" else "; ".join(erros) or status_geral
    resultado = {
        "numero_ciclo": int(numero_ciclo),
        "data_hora": instante.strftime("%d/%m/%Y %H:%M:%S"),
        "arquivo_base": arquivo_base,
        "status_geral": status_geral,
        "quantidade_amostras": int(max_len),
        "quantidade_periodos_sob_pressao": len(vetor_sp),
        "tempo_total_sob_pressao_s": round(sum(vetor_sp), 3),
        "quantidade_alivios_pressao": len(vetor_alivio),
        "tempo_total_alivio_pressao_s": round(sum(vetor_alivio), 3),
        **estados,
        "mensagem": mensagem_resultado,
    }
    try:
        _registrar_resultado_ciclo(resultado)
    except Exception as e:
        print(f"[ERRO RESULTADO] {type(e).__name__}: {e}")
        traceback.print_exc()

    if obrigatorios_ok:
        ultimo_arquivo_salvo = arquivo_base
    if status_geral == "Salvo com sucesso":
        set_status(f"Ciclo {numero_ciclo} salvo com sucesso.", "green")
    elif status_geral == "Salvo parcialmente":
        set_status(f"Ciclo {numero_ciclo} salvo parcialmente. Consulte Resultados.", "#ba6d00")
    else:
        set_status(f"Ciclo {numero_ciclo} com erro de salvamento. Consulte Resultados.", "red")
    return status_geral == "Salvo com sucesso"

def processar_fila_salvamento():
    # ALT24C - nenhuma exceção de processamento pode encerrar a thread de salvamento.
    while not fechando:
        try:
            item = fila_salvamento.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            if item is not None:
                salvar_ciclo_automatico(*item)
        except Exception as e:
            print(f"[ERRO FINALIZACAO/SALVAMENTO] {type(e).__name__}: {e}")
            traceback.print_exc()
        finally:
            fila_salvamento.task_done()

# ============================================================

# ============================================================
# ALT28A - TRATAMENTO DE MW413=65535
# ============================================================

def pressao_lida_valida(valor):
    try:
        return int(valor) != VALOR_INVALIDO_PRESSAO_LIDA
    except (TypeError, ValueError):
        return False


def resetar_qualidade_pressao_lida():
    global ultima_pressao_lida_valida
    global leituras_invalidas_pressao_consecutivas
    global total_leituras_invalidas_pressao
    global falha_persistente_pressao
    ultima_pressao_lida_valida = None
    leituras_invalidas_pressao_consecutivas = 0
    total_leituras_invalidas_pressao = 0
    falha_persistente_pressao = False


def tratar_pressao_lida(valor_bruto, timestamp):
    """Retorna (valor_tratado, deve_processar). Preserva o bruto por timestamp."""
    global ultima_pressao_lida_valida
    global leituras_invalidas_pressao_consecutivas
    global total_leituras_invalidas_pressao
    global falha_persistente_pressao

    with pressao_lida_bruta_lock:
        pressao_lida_bruta_por_timestamp[float(timestamp)] = valor_bruto

    if pressao_lida_valida(valor_bruto):
        if falha_persistente_pressao:
            print("[INFO PRESSAO] Leitura da Pressao Lida normalizada.")
        ultima_pressao_lida_valida = valor_bruto
        leituras_invalidas_pressao_consecutivas = 0
        falha_persistente_pressao = False
        return valor_bruto, True

    leituras_invalidas_pressao_consecutivas += 1
    total_leituras_invalidas_pressao += 1
    print(
        "[AVISO PRESSAO] Leitura invalida MW413=65535 ignorada. "
        f"Consecutivas: {leituras_invalidas_pressao_consecutivas}."
    )

    if leituras_invalidas_pressao_consecutivas > MAX_LEITURAS_INVALIDAS_PRESSAO_CONSECUTIVAS:
        if not falha_persistente_pressao:
            falha_persistente_pressao = True
            mensagem = (
                "Falha persistente na Pressao Lida: MW413 retornou 65535 "
                "em leituras consecutivas."
            )
            print(f"[ERRO PRESSAO] {mensagem}")
            set_status(mensagem, "red")

    if ultima_pressao_lida_valida is None:
        return None, False
    return ultima_pressao_lida_valida, True


def restaurar_pressao_bruta_no_csv(caminho_csv, snapshot_buffers):
    """ALT28A - restaura MW413 bruto no CSV depois de PNG/calculos usarem o tratado."""
    if not caminho_csv or not os.path.isfile(caminho_csv):
        return
    if not snapshot_buffers or not snapshot_buffers[INDICE_PRESSAO_LIDA]:
        return

    timestamps = [float(p[0]) for p in snapshot_buffers[INDICE_PRESSAO_LIDA]]
    with pressao_lida_bruta_lock:
        valores_brutos = [pressao_lida_bruta_por_timestamp.get(t) for t in timestamps]

    with open(caminho_csv, "r", newline="", encoding="utf-8-sig") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    if not linhas:
        return

    cabecalho = linhas[0]
    indice_pressao = next(
        (i for i, nome in enumerate(cabecalho) if nome.startswith("CH1_") or "MW413" in nome),
        None,
    )
    if indice_pressao is None:
        raise ValueError("Coluna da Pressao Lida nao encontrada no CSV principal.")

    alteracoes = 0
    for indice_linha, bruto in enumerate(valores_brutos, start=1):
        if bruto is None or indice_linha >= len(linhas):
            continue
        if indice_pressao < len(linhas[indice_linha]):
            linhas[indice_linha][indice_pressao] = str(bruto)
            if int(bruto) == VALOR_INVALIDO_PRESSAO_LIDA:
                alteracoes += 1

    with open(caminho_csv, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerows(linhas)

    if alteracoes:
        print(f"[ALT28A] {alteracoes} leitura(s) bruta(s) 65535 preservada(s) no CSV.")


def localizar_csv_principal_recente(numero_ciclo, inicio_execucao):
    pasta = obter_pasta_saida()
    padrao_principal = re.compile(
        rf"^(?:Maquina_[0-9A-Za-z_-]+_)?ciclo_{int(numero_ciclo):04d}_\d{{8}}_\d{{6}}\.csv$"
    )
    candidatos = []
    for nome in os.listdir(pasta):
        if not padrao_principal.match(nome):
            continue
        if any(nome.endswith(s) for s in (
            "_parametros_form_m340.csv", "_periodos_sob_pressao.csv",
            "_tempos_sob_pressao.csv", "_tempos_ventilacao.csv",
        )):
            continue
        caminho = os.path.join(pasta, nome)
        try:
            if os.path.getmtime(caminho) >= inicio_execucao - 2.0:
                candidatos.append(caminho)
        except OSError:
            pass
    return max(candidatos, key=os.path.getmtime) if candidatos else None


# AQUISICAO
# ============================================================
def atualizar_canais_por_protocolo(ip, protocolo, tags):
    if protocolo.upper() != "SCHNEIDER": raise RuntimeError("Protocolo não suportado.")
    return [ler_tag_schneider(ip, t) for t in tags]

def obter_limites_tempo_sob_pressao(pressao_programada, inercia_pressao):
    """ALT19 - Retorna a faixa válida da receita para o Tempo Sob Pressão.

    Prioriza os limites calculados a partir de FORM[0].Pressao e
    FORM[0].ToleranciaDePressao. Se o vetor ainda não estiver disponível,
    mantém compatibilidade usando MW3002 - MW515 como limite mínimo e não
    impõe limite máximo adicional.
    """
    if limite_pressao_programada_min is not None and limite_pressao_programada_max is not None:
        return float(limite_pressao_programada_min), float(limite_pressao_programada_max)
    try:
        minimo = float(pressao_programada) - float(inercia_pressao)
    except (TypeError, ValueError):
        return None, None
    return minimo, None


def calcular_condicao_tempo_sob_pressao(pressao_lida, pressao_programada, inercia_pressao):
    """ALT24B - Verifica somente a condição de início do Tempo Sob Pressão.

    O início exige MW3002 ativo e MW413 maior ou igual ao limite mínimo.
    Depois do início, MW413 não mantém nem encerra o período. O encerramento
    ocorre exclusivamente pela queda confirmada de MW3002 para zero.
    """
    try:
        pressao_lida = float(pressao_lida)
        pressao_programada = float(pressao_programada)
        inercia_pressao = float(inercia_pressao)
    except (TypeError, ValueError):
        return False, None, None, None, None
    if pressao_programada <= LIMIAR_PRESSAO_PROGRAMADA_ATIVA:
        return False, None, pressao_lida, pressao_programada, inercia_pressao
    limite_minimo, _ = obter_limites_tempo_sob_pressao(pressao_programada, inercia_pressao)
    if limite_minimo is None:
        return False, None, pressao_lida, pressao_programada, inercia_pressao
    inicio_valido = pressao_lida >= float(limite_minimo)
    return inicio_valido, float(limite_minimo), pressao_lida, pressao_programada, inercia_pressao


def calcular_periodos_sob_pressao(snapshot_buffers):
    """ALT24B - Reconstrói períodos pela máquina de estados híbrida."""
    periodos = []
    if not snapshot_buffers or len(snapshot_buffers) < 3:
        return periodos
    bl = snapshot_buffers[INDICE_PRESSAO_LIDA]
    bp = snapshot_buffers[INDICE_PRESSAO_PROGRAMADA]
    bi = snapshot_buffers[INDICE_INERCIA_PRESSAO]
    n = min(len(bl), len(bp), len(bi))
    if n <= 0:
        return periodos
    t0 = float(bl[0][0])
    ativo = False
    inicio = pressao_inicio = limiar_inicio = None
    contador_zero = 0
    primeiro_zero = None
    ultimo_t = 0.0

    def concluir(fim):
        nonlocal ativo, inicio, pressao_inicio, limiar_inicio, contador_zero, primeiro_zero
        if ativo and inicio is not None:
            duracao = max(0.0, float(fim) - float(inicio))
            if duracao >= DURACAO_MINIMA_SOB_PRESSAO:
                periodos.append({"numero":len(periodos)+1,"inicio_s":round(inicio,3),
                    "fim_s":round(float(fim),3),"duracao_s":round(duracao,3),
                    "pressao_inicio":pressao_inicio,"limiar":limiar_inicio})
        ativo=False; inicio=pressao_inicio=limiar_inicio=None
        contador_zero=0; primeiro_zero=None

    for i in range(n):
        try:
            t=float(bl[i][0])-t0
            pl=float(bl[i][1]); pp=float(bp[i][1]); ine=float(bi[i][1])
        except (TypeError,ValueError,IndexError):
            continue
        ultimo_t=t
        programada_ativa = pp > LIMIAR_PRESSAO_PROGRAMADA_ATIVA
        if not ativo:
            if programada_ativa:
                inicio_valido, limiar, _, _, _ = calcular_condicao_tempo_sob_pressao(pl,pp,ine)
                if inicio_valido:
                    ativo=True; inicio=t; pressao_inicio=pl; limiar_inicio=limiar
                    contador_zero=0; primeiro_zero=None
        elif programada_ativa:
            contador_zero=0; primeiro_zero=None
        else:
            contador_zero += 1
            if contador_zero == 1:
                primeiro_zero=t
            if contador_zero >= DEBOUNCE_AMOSTRAS_SOB_PRESSAO:
                concluir(primeiro_zero if primeiro_zero is not None else t)
    if ativo and inicio is not None:
        concluir(ultimo_t)
    return periodos


def salvar_periodos_sob_pressao(base, snapshot_buffers):
    """Salva a tabela de períodos de Tempo Sob Pressão em CSV."""
    periodos = calcular_periodos_sob_pressao(snapshot_buffers)
    caminho = base + "_periodos_sob_pressao.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Periodo", "Inicio_s", "Fim_s", "Duracao_s", "Pressao_no_inicio", "Limiar"])
        for p in periodos:
            w.writerow([p["numero"], p["inicio_s"], p["fim_s"], p["duracao_s"],
                        p["pressao_inicio"], p["limiar"]])
    print(f"[INFO] {len(periodos)} período(s) de Tempo Sob Pressão detectado(s). Salvo em: {caminho}")
    return caminho, periodos

def obter_vetor_tempos_sob_pressao(snapshot_buffers):
    """Retorna apenas o vetor de durações (s) de cada período de Tempo Sob Pressão."""
    return [p["duracao_s"] for p in calcular_periodos_sob_pressao(snapshot_buffers)]

def calcular_periodos_ventilacao(snapshot_buffers, limiar=LIMIAR_VENTILACAO):
    """
    Máquina de estados das ventilações, baseada na Pressão Lida (MW413).

    INÍCIO: MW413 < limiar   (borda ↓)
    FIM:    MW413 >= limiar   (borda ↑)

    - Descarta ventilações muito curtas (DURACAO_MINIMA_VENTILACAO), como a subida inicial.
    - Não conta a ventilação final (após o último pulso), pois só fecha em borda ↑.
    Retorna lista de dicionários: {numero, inicio_s, fim_s, duracao_s}
    """
    periodos = []
    if not snapshot_buffers or len(snapshot_buffers) < 1:
        return periodos
    buf_lida = snapshot_buffers[INDICE_PRESSAO_LIDA]
    if not buf_lida:
        return periodos
    t0 = buf_lida[0][0]
    ativo = False
    inicio_s = None
    houve_pressurizacao = False   # ALT10 - so conta ventilacao apos 1a pressurizacao (MW413 >= limiar)
    contador_ventilando = 0       # ALT15 - amostras consecutivas com MW413 < limiar (anti-glitch)
    t_primeiro_abaixo = None      # ALT15 - instante do 1º ponto abaixo do limiar
    for i in range(len(buf_lida)):
        try:
            t = float(buf_lida[i][0]) - float(t0)
            pressao_lida = float(buf_lida[i][1])
        except (TypeError, ValueError):
            continue
        em_ventilacao = pressao_lida < limiar
        # ALT10 - marca a primeira pressurizacao (MW413 subiu >= limiar).
        if pressao_lida >= limiar:
            houve_pressurizacao = True
        # ALT15 - conta amostras consecutivas abaixo do limiar (anti-glitch).
        if em_ventilacao:
            contador_ventilando += 1
            if contador_ventilando == 1:
                t_primeiro_abaixo = t
        else:
            contador_ventilando = 0
            t_primeiro_abaixo = None
        # INÍCIO — confirma só após DEBOUNCE amostras consecutivas abaixo do limiar (ALT15),
        # e somente após a 1ª pressurização (ALT10). Início marcado no 1º ponto abaixo.
        if (not ativo) and houve_pressurizacao and contador_ventilando >= DEBOUNCE_AMOSTRAS_VENTILACAO:
            ativo = True
            inicio_s = t_primeiro_abaixo
        # FIM — borda de subida (sai da ventilação).
        if ativo and not em_ventilacao:
            duracao = round(t - inicio_s, 3)
            if duracao >= DURACAO_MINIMA_VENTILACAO:  # descarta ventilações falsas curtas
                periodos.append({"numero": len(periodos) + 1,
                                 "inicio_s": round(inicio_s, 3),
                                 "fim_s": round(t, 3),
                                 "duracao_s": duracao})
            ativo = False
            inicio_s = None
    return periodos

def obter_vetor_tempos_ventilacao(snapshot_buffers):
    """Retorna apenas o vetor de durações (s) de cada ventilação."""
    return [p["duracao_s"] for p in calcular_periodos_ventilacao(snapshot_buffers)]

def salvar_tempos_ventilacao(base, snapshot_buffers):
    """Salva a tabela de ventilações + o vetor de durações em CSV."""
    periodos = calcular_periodos_ventilacao(snapshot_buffers)
    vetor = [p["duracao_s"] for p in periodos]
    caminho = base + "_tempos_ventilacao.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Periodo", "Inicio_s", "Fim_s", "Duracao_s"])
        for p in periodos:
            w.writerow([p["numero"], p["inicio_s"], p["fim_s"], p["duracao_s"]])
        w.writerow([]); w.writerow(["Vetor_TemposVentilacao_s", vetor])
    print(f"[INFO] Vetor de Alívio de Pressão ({len(vetor)} período(s)): {vetor}")
    return caminho, vetor

def calcular_jitter_aquisicao(snapshot_buffers):
    """
    ITEM 4 - Calcula a estatística de intervalo entre amostras (jitter) do ciclo.
    Retorna (min_ms, medio_ms, max_ms, incerteza_ms) ou None se não houver dados.
    A incerteza estimada de cada fronteira é ± metade do intervalo médio.
    """
    if not snapshot_buffers or not snapshot_buffers[0] or len(snapshot_buffers[0]) < 2:
        return None
    ts = [amostra[0] for amostra in snapshot_buffers[0]]
    intervalos = [(ts[i] - ts[i - 1]) * 1000.0 for i in range(1, len(ts)) if (ts[i] - ts[i - 1]) >= 0]
    if not intervalos:
        return None
    min_ms = min(intervalos)
    max_ms = max(intervalos)
    medio_ms = sum(intervalos) / len(intervalos)
    incerteza_ms = medio_ms / 2.0
    return round(min_ms, 1), round(medio_ms, 1), round(max_ms, 1), round(incerteza_ms, 1)

def salvar_tempos_sob_pressao(base, snapshot_buffers):
    """Salva a tabela de períodos + o vetor de durações + o jitter (ITEM 4) em CSV."""
    periodos = calcular_periodos_sob_pressao(snapshot_buffers)
    vetor = [p["duracao_s"] for p in periodos]
    jitter = calcular_jitter_aquisicao(snapshot_buffers)
    caminho = base + "_tempos_sob_pressao.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Periodo", "Inicio_s", "Fim_s", "Duracao_s", "Pressao_no_inicio", "Limiar"])
        for p in periodos:
            w.writerow([p["numero"], p["inicio_s"], p["fim_s"], p["duracao_s"],
                        p["pressao_inicio"], p["limiar"]])
        w.writerow([]); w.writerow(["Vetor_TemposSobPressao_s", vetor])
        # ITEM 4 - rodapé com o jitter de aquisição e a incerteza estimada da medição.
        w.writerow([])
        w.writerow(["Jitter_intervalo_min_ms", "Jitter_intervalo_medio_ms",
                    "Jitter_intervalo_max_ms", "Incerteza_estimada_ms"])
        if jitter is not None:
            w.writerow([jitter[0], jitter[1], jitter[2], jitter[3]])
        else:
            w.writerow(["", "", "", ""])
    print(f"[INFO] Vetor de Tempo Sob Pressão ({len(vetor)} período(s)): {vetor}")
    if jitter is not None:
        print(f"[INFO] Jitter aquisição: min={jitter[0]}ms | médio={jitter[1]}ms | "
              f"máx={jitter[2]}ms | incerteza≈±{jitter[3]}ms")
    return caminho, vetor

def limpar_buffers_ciclo():
    global buffers
    buffers = [[] for _ in tags_ativas]

def finalizar_ciclo_atual(numero, motivo):
    """ALT24C - cria snapshots estáveis antes de calcular e enfileirar o salvamento."""
    global tempos_sob_pressao, tempos_ventilacao
    snapshot = [list(b) for b in buffers]
    snapshot_tags = list(tags_ativas)
    snapshot_form = [dict(item) for item in ultimo_vetor_m340_descrito]
    if not any(snapshot):
        print(f"[AVISO FINALIZACAO] Ciclo {numero} sem dados. Motivo: {motivo}")
        return False

    try:
        tempos_sob_pressao = obter_vetor_tempos_sob_pressao(snapshot)
        tempos_ventilacao = obter_vetor_tempos_ventilacao(snapshot)
        atualizar_label_tempos_sob_pressao()
        atualizar_label_tempos_ventilacao()
    except Exception as e:
        print(f"[ERRO CALCULO TEMPO SOB PRESSAO] {type(e).__name__}: {e}")
        traceback.print_exc()
        # O snapshot continua preservado e será enfileirado para diagnóstico/salvamento parcial.

    fila_salvamento.put((snapshot, snapshot_tags, numero, snapshot_form))
    atualizar_flag_monitor_status(STATUS_CONCLUIDO)
    print(f"[INFO] Finalizando ciclo {numero}. Motivo: {motivo}. Snapshot enfileirado para salvamento.")
    return True


def finalizar_ciclo_seguro(numero, motivo):
    """ALT24C - impede que uma falha de finalização mate a thread de aquisição."""
    try:
        return finalizar_ciclo_atual(numero, motivo)
    except Exception as e:
        print(f"[ERRO FINALIZACAO] Ciclo {numero} | {type(e).__name__}: {e}")
        traceback.print_exc()
        set_status(f"Erro na finalização do ciclo {numero}. Consulte o terminal.", "red")
        return False

def leitor_com_trigger(ip, protocolo, tags, trigger_tag, trigger_habilitado, tipo_trigger, monitorar_pressao_zero):
    global rodando, pausado, buffers, zoom_usuario_ativo, tempos_sob_pressao, tempos_ventilacao, ultima_comunicacao_ok, ultimo_trigger_lido
    em_ciclo = False; numero = 0; falhas_t = falhas_c = 0
    condicao_tempo_anterior = False
    tempo_inicio_sob_pressao = None
    limite_inicio_tempo_sob_pressao = None
    confirmou_pressurizacao = False   # ALT17 - MW413 cruzou o limiar ao menos uma vez na janela
    tempos_sob_pressao = []
    ventilacao_anterior = False
    tempo_inicio_ventilacao = None
    tempos_ventilacao = []
    houve_pressurizacao = False   # ALT10 - True apos MW413 subir >= LIMIAR_VENTILACAO ao menos uma vez
    contador_prog_zero = 0        # ALT24B - confirma queda de MW3002
    t_primeiro_prog_zero = None   # ALT24B - timestamp do primeiro zero
    pressao_inicio_sob_pressao = None
    contador_ventilando = 0       # ALT15 - amostras consecutivas com MW413 < limiar (anti-glitch)
    t_primeiro_abaixo_v = None    # ALT15 - instante do 1º ponto abaixo do limiar (início ventilação)
    atualizar_flag_monitor_status(STATUS_AGUARDANDO_INICIO)
    while rodando and not fechando:
        if pausado: time.sleep(0.1); continue
        try:
            flag = 1 if not trigger_habilitado else (1 if int(ler_tag_schneider(ip, trigger_tag)) != 0 else 0)
            falhas_t = 0
            ultimo_trigger_lido = int(flag)
            ultima_comunicacao_ok = time.time()
        except Exception as e:
            falhas_t += 1; set_status(f"Falha leitura trigger ({falhas_t}): {e}", "red")
            if falhas_t >= MAX_FALHAS_TRIGGER_CONSECUTIVAS and em_ciclo:
                finalizar_ciclo_seguro(numero, "falhas no trigger")
                em_ciclo = False
                atualizar_flag_monitor_status(STATUS_AGUARDANDO_INICIO)
            time.sleep(0.3); continue
        if not em_ciclo and flag == 0:
            set_status("Aguardando próximo ciclo: %MW3000 = 1...", "blue"); time.sleep(INTERVALO_AQUISICAO_FIXO); continue
        if not em_ciclo and flag == 1:
            numero += 1; em_ciclo = True; zoom_usuario_ativo = False; limpar_buffers_ciclo(); resetar_qualidade_pressao_lida(); atualizar_flag_monitor_status(STATUS_EM_MONITORACAO); set_status(f"Ciclo {numero} iniciado", "green")
            condicao_tempo_anterior = False; tempo_inicio_sob_pressao = None; limite_inicio_tempo_sob_pressao = None; confirmou_pressurizacao = False; tempos_sob_pressao = []; atualizar_label_tempos_sob_pressao()
            ventilacao_anterior = False; tempo_inicio_ventilacao = None; tempos_ventilacao = []; houve_pressurizacao = False; atualizar_label_tempos_ventilacao()   # ALT10 reset flag
            contador_prog_zero = 0; t_primeiro_prog_zero = None; pressao_inicio_sob_pressao = None
            contador_ventilando = 0; t_primeiro_abaixo_v = None   # ALT15/ALT19 reset anti-glitch
        if em_ciclo and flag == 0:
            # ALT24C - finalização protegida e estado restabelecido mesmo em caso de erro.
            finalizar_ciclo_seguro(numero, "%MW3000 = 0")
            em_ciclo = False
            atualizar_flag_monitor_status(STATUS_AGUARDANDO_INICIO)
            if not modo_html_ativo and root is not None:
                root.after(0, update_graph)
            continue
        try:
            # ITEM 3 - timestamp no CENTRO da janela de leitura (remove viés da latência Modbus).
            t_antes = time.time()
            valores = atualizar_canais_por_protocolo(ip, protocolo, tags)
            t_depois = time.time()
            agora = (t_antes + t_depois) / 2.0
            falhas_c = 0
            ultima_comunicacao_ok = time.time()
            pressao_lida_bruta = valores[INDICE_PRESSAO_LIDA]
            pressao_lida_tratada, processar_pressao = tratar_pressao_lida(
                pressao_lida_bruta, agora
            )
            valores_tratados = list(valores)
            if processar_pressao:
                valores_tratados[INDICE_PRESSAO_LIDA] = pressao_lida_tratada
                for i, v in enumerate(valores_tratados):
                    buffers[i].append((agora, v))
            else:
                # Sem valor valido anterior: preserva alinhamento dos demais canais,
                # mas nao inclui 65535 no buffer tratado de Pressao Lida.
                for i, v in enumerate(valores_tratados):
                    if i != INDICE_PRESSAO_LIDA:
                        buffers[i].append((agora, v))
            if len(valores) < 3:
                raise RuntimeError("São necessários os canais de Pressão Lida, Pressão Programada e Inércia de Pressão.")
            pressao_lida = pressao_lida_tratada if processar_pressao else None
            pressao_programada = valores[INDICE_PRESSAO_PROGRAMADA]
            inercia_pressao = valores[INDICE_INERCIA_PRESSAO]
            tempo_atual = agora
            if not processar_pressao:
                time.sleep(INTERVALO_AQUISICAO_FIXO)
                continue
            (condicao_inicio_sp, limite_minimo_sp,
             pressao_lida, pressao_programada, inercia_pressao) = calcular_condicao_tempo_sob_pressao(
                pressao_lida, pressao_programada, inercia_pressao)
            try:
                programada_ativa_sp = float(pressao_programada) > LIMIAR_PRESSAO_PROGRAMADA_ATIVA
            except (TypeError, ValueError):
                programada_ativa_sp = False

            if tempo_inicio_sob_pressao is None:
                contador_prog_zero = 0
                t_primeiro_prog_zero = None
                if condicao_inicio_sp:
                    tempo_inicio_sob_pressao = tempo_atual
                    pressao_inicio_sob_pressao = float(pressao_lida)
                    limite_inicio_tempo_sob_pressao = limite_minimo_sp
                    confirmou_pressurizacao = True
                    print(f"[INFO] TempoSobPressao iniciado: Pressão lida={pressao_lida}, "
                          f"Pressão programada={pressao_programada}, Limite mínimo={limite_minimo_sp}, "
                          f"Timestamp={tempo_inicio_sob_pressao}")
            elif programada_ativa_sp:
                contador_prog_zero = 0
                t_primeiro_prog_zero = None
            else:
                contador_prog_zero += 1
                if contador_prog_zero == 1:
                    t_primeiro_prog_zero = tempo_atual
                if contador_prog_zero >= DEBOUNCE_AMOSTRAS_SOB_PRESSAO:
                    fim_sp = t_primeiro_prog_zero if t_primeiro_prog_zero is not None else tempo_atual
                    duracao = round(max(0.0, fim_sp-tempo_inicio_sob_pressao),3)
                    if duracao >= DURACAO_MINIMA_SOB_PRESSAO:
                        tempos_sob_pressao.append(duracao)
                        print(f"[INFO] TempoSobPressao encerrado: duração={duracao}s | vetor={tempos_sob_pressao}")
                        atualizar_label_tempos_sob_pressao()
                    tempo_inicio_sob_pressao=None
                    pressao_inicio_sob_pressao=None
                    limite_inicio_tempo_sob_pressao=None
                    confirmou_pressurizacao=False
                    contador_prog_zero=0
                    t_primeiro_prog_zero=None

            condicao_tempo_anterior = condicao_inicio_sp
            # ----- VENTILAÇÃO (baseada na Pressão Lida MW413 < LIMIAR_VENTILACAO) -----
            try:
                pl_v = float(pressao_lida)
            except (TypeError, ValueError):
                pl_v = None
            em_ventilacao_atual = (pl_v is not None) and (pl_v < LIMIAR_VENTILACAO)
            # ALT10 - marca que a pressao ja subiu ao menos uma vez neste ciclo
            if (pl_v is not None) and (pl_v >= LIMIAR_VENTILACAO):
                houve_pressurizacao = True
            # ALT15 - conta amostras consecutivas abaixo do limiar (anti-glitch).
            if em_ventilacao_atual:
                contador_ventilando += 1
                if contador_ventilando == 1:
                    t_primeiro_abaixo_v = tempo_atual
            else:
                contador_ventilando = 0
                t_primeiro_abaixo_v = None
            # INÍCIO da ventilação — só após DEBOUNCE amostras consecutivas (ALT15) e 1ª pressurização (ALT10).
            # Um MW413=0 isolado (glitch) não dispara ventilação fantasma. Início no 1º ponto abaixo.
            if tempo_inicio_ventilacao is None and houve_pressurizacao and contador_ventilando >= DEBOUNCE_AMOSTRAS_VENTILACAO:
                tempo_inicio_ventilacao = t_primeiro_abaixo_v
            # FIM da ventilação — pressão volta a subir (>= limiar).
            if tempo_inicio_ventilacao is not None and not em_ventilacao_atual:
                duracao_v = round(tempo_atual - tempo_inicio_ventilacao, 3)
                if duracao_v >= DURACAO_MINIMA_VENTILACAO:  # descarta ventilações falsas curtas
                    tempos_ventilacao.append(duracao_v)
                    print(f"[INFO] Ventilação encerrada: duração={duracao_v}s | vetor={tempos_ventilacao}")
                    atualizar_label_tempos_ventilacao()
                tempo_inicio_ventilacao = None
            ventilacao_anterior = em_ventilacao_atual
            condicao_tempo_anterior = condicao_inicio_sp
            if not modo_html_ativo:
                root.after(0, update_graph)
        except Exception as e:
            falhas_c += 1; set_status(f"Erro aquisição: {e}", "red")
            if falhas_c >= MAX_FALHAS_CANAIS_CONSECUTIVAS:
                finalizar_ciclo_seguro(numero, "falhas nos canais")
                em_ciclo = False
                atualizar_flag_monitor_status(STATUS_AGUARDANDO_INICIO)
        time.sleep(INTERVALO_AQUISICAO_FIXO)

# ============================================================
# UPDATE, ZOOM E INTERFACE
# ============================================================
def ajustar_eixo_y_para_limites(eixo):
    """
    ALT9 - Expande (nunca encolhe) o eixo Y para incluir os limites de pressao,
    com uma folga percentual. Chamar apenas quando o autoscale automatico estiver
    ativo (sem zoom/pan manual). Corrige o corte do topo apos a ALT8, pois relim()
    ignora hlines/fill_between (colecoes).
    """
    if not INCLUIR_LIMITES_NO_AUTOSCALE_Y: return
    if eixo is None: return
    if limite_pressao_programada_min is None or limite_pressao_programada_max is None: return
    amplitude = max(limite_pressao_programada_max - limite_pressao_programada_min, 1.0)
    folga = amplitude * MARGEM_Y_LIMITES_PERC
    alvo_max = limite_pressao_programada_max + folga
    alvo_min = limite_pressao_programada_min - folga
    y0, y1 = eixo.get_ylim()
    novo_y0 = min(y0, alvo_min)   # so expande para baixo
    novo_y1 = max(y1, alvo_max)   # so expande para cima
    eixo.set_ylim(novo_y0, novo_y1)

def update_graph():
    if ax is None or canvas is None: return
    xlim, ylim = ax.get_xlim(), ax.get_ylim(); ax.clear(); aplicar_estilo_grafico(ax, fig); tem = False
    for i,b in enumerate(buffers):
        if not b: continue
        if i in INDICES_NAO_PLOTAR: continue  # Não plotar Inércia (MW515).
        t0=b[0][0]; ax.plot([p[0]-t0 for p in b], [p[1] for p in b], color=cor_do_canal(i), linewidth=1.3, label=f"CH{i+1} - {tags_ativas[i]}"); tem=True
    desenhar_limites_pressao_programada(ax, buffers); desenhar_marcadores_pressao_fora_limites(ax)
    if tem:
        aplicar_estilo_legenda(ax)
        if zoom_usuario_ativo: ax.set_xlim(xlim); ax.set_ylim(ylim)
        else:
            ax.relim(); ax.autoscale_view()
            x0, x1 = ax.get_xlim(); ax.set_xlim(x0 - MARGEM_EIXO_X_S, x1 + MARGEM_EIXO_X_S)   # ALT14
            ajustar_eixo_y_para_limites(ax)   # ALT9
    canvas.draw_idle()

def on_scroll_zoom(event):
    global zoom_usuario_ativo
    if event.inaxes != ax or event.xdata is None: return
    zoom_usuario_ativo=True; f=1/1.2 if event.button=="up" else 1.2
    xl,yl=ax.get_xlim(),ax.get_ylim(); x,y=event.xdata,event.ydata
    nw,nh=(xl[1]-xl[0])*f,(yl[1]-yl[0])*f
    rx,ry=(xl[1]-x)/(xl[1]-xl[0]),(yl[1]-y)/(yl[1]-yl[0])
    ax.set_xlim(x-nw*(1-rx),x+nw*rx); ax.set_ylim(y-nh*(1-ry),y+nh*ry); canvas.draw_idle()

def on_mouse_press(event):
    global pan_usuario_ativo, pan_inicio, zoom_usuario_ativo
    if event.inaxes==ax and event.button==3:
        pan_usuario_ativo=True; zoom_usuario_ativo=True; pan_inicio=(event.xdata,event.ydata,ax.get_xlim(),ax.get_ylim())

def on_mouse_release(event):
    global pan_usuario_ativo, pan_inicio
    pan_usuario_ativo=False; pan_inicio=None

def on_mouse_move(event):
    if not pan_usuario_ativo or pan_inicio is None or event.inaxes!=ax or event.xdata is None: return
    x,y,xl,yl=pan_inicio; dx,dy=event.xdata-x,event.ydata-y
    ax.set_xlim(xl[0]-dx,xl[1]-dx); ax.set_ylim(yl[0]-dy,yl[1]-dy); canvas.draw_idle()

def resetar_zoom():
    global zoom_usuario_ativo
    zoom_usuario_ativo=False; ax.relim(); ax.autoscale_view(); canvas.draw_idle()

def coletar_tags_ativas(): return [e.get().strip() for e in canal_entries if e.get().strip()]
def atualizar_botoes_estado_rodando(): btn_start.config(state="disabled"); btn_pause.config(state="normal"); btn_stop.config(state="normal")
def atualizar_botoes_estado_parado(): btn_start.config(state="normal"); btn_pause.config(state="disabled"); btn_stop.config(state="disabled")

def start():
    global rodando, pausado, thread_aquisicao, buffers, tags_ativas, zoom_usuario_ativo
    if rodando: return
    try:
        ip=entry_ip.get().strip(); tags_ativas=coletar_tags_ativas()
        if not ip or not tags_ativas: raise ValueError("Informe IP e pelo menos um canal.")
        buffers=[[] for _ in tags_ativas]; zoom_usuario_ativo=False
        try: ler_vetor_m340_automatico(ip)
        except Exception as e: set_vetor_status(f"Falha ao ler vetor: {e}", "red")
        ax.clear(); aplicar_estilo_grafico(ax,fig); atualizar_linhas_limite_pressao_programada()
        rodando=True; pausado=False; atualizar_botoes_estado_rodando()
        thread_aquisicao=threading.Thread(target=leitor_com_trigger,args=(ip,protocolo_var.get(),tags_ativas,entry_trigger.get(),bool(trigger_enable_var.get()),trigger_tipo_var.get(),bool(trigger_stop_zero_var.get())),daemon=True); thread_aquisicao.start()
    except Exception as e: messagebox.showerror("Erro", str(e))

def pause():
    global pausado
    pausado=not pausado; btn_pause.config(text="Continuar" if pausado else "Pausar")

def parar_aquisicao():
    global rodando, pausado
    rodando=False; pausado=False; atualizar_flag_monitor_status(STATUS_CONCLUIDO); atualizar_botoes_estado_parado()

def on_close():
    global fechando, rodando
    fechando=True; rodando=False; root.destroy()

def criar_interface():
    global root,fig,ax,canvas,toolbar,protocolo_var,btn_diagnostico_modbus,entry_ip,entry_flag_monitor_status,entry_offset_modbus,status_var,label_status,label_vetor_status,label_tempos_sob_pressao,label_tempos_ventilacao,canal_entries,trigger_enable_var,trigger_tipo_var,trigger_stop_zero_var,entry_trigger,btn_start,btn_pause,btn_stop,btn_reset_zoom,btn_testar_vetor
    root=tk.Tk(); root.title("Oraculum - Osciloscópio Industrial"); root.geometry("1200x760"); root.protocol("WM_DELETE_WINDOW",on_close)
    fc=ttk.LabelFrame(root,text="Configuração"); fc.pack(fill="x",padx=8,pady=4)
    ttk.Label(fc,text="IP CLP:").grid(row=0,column=0); entry_ip=ttk.Entry(fc,width=20); entry_ip.grid(row=0,column=1); entry_ip.insert(0,IP_PADRAO)
    protocolo_var=tk.StringVar(value=PROTOCOLO_PADRAO); ttk.Combobox(fc,textvariable=protocolo_var,values=["SCHNEIDER"],state="readonly",width=16).grid(row=0,column=3)
    ttk.Label(fc,text="Flag Monitor Status:").grid(row=0,column=4); entry_flag_monitor_status=ttk.Entry(fc,width=16); entry_flag_monitor_status.grid(row=0,column=5); entry_flag_monitor_status.insert(0,FLAG_MONITOR_STATUS_PADRAO)
    ttk.Label(fc,text="Offset Modbus:").grid(row=0,column=6); entry_offset_modbus=ttk.Entry(fc,width=8); entry_offset_modbus.grid(row=0,column=7); entry_offset_modbus.insert(0,"0")
    trigger_enable_var=tk.BooleanVar(value=True); ttk.Checkbutton(fc,text="Usar START / Trigger",variable=trigger_enable_var).grid(row=1,column=0,columnspan=2)
    ttk.Label(fc,text="Trigger:").grid(row=1,column=2); entry_trigger=ttk.Entry(fc,width=20); entry_trigger.grid(row=1,column=3); entry_trigger.insert(0,TRIGGER_PADRAO)
    trigger_tipo_var=tk.StringVar(value=TIPO_TRIGGER_PADRAO); ttk.Combobox(fc,textvariable=trigger_tipo_var,values=["NIVEL","BORDA","SUBIDA","DESCIDA"],state="readonly",width=12).grid(row=1,column=5)
    trigger_stop_zero_var=tk.BooleanVar(value=True); ttk.Checkbutton(fc,text="Monitorar pressão zero, sem finalizar por zero",variable=trigger_stop_zero_var).grid(row=1,column=6,columnspan=2)
    fch=ttk.LabelFrame(root,text="Dados para Tempo Sob Pressão"); fch.pack(fill="x",padx=8,pady=4); canal_entries=[]
    nomes_canais=["Pressão Lida:","Pressão Programada:","Inércia de Pressão:"]
    tags_padrao=[PRESSAO_LIDA_PADRAO,PRESSAO_PROGRAMADA_PADRAO,INERCIA_PRESSAO_PADRAO]
    for i in range(3):
        ttk.Label(fch,text=nomes_canais[i]).grid(row=0,column=i*2,padx=6,pady=8,sticky="w"); e=ttk.Entry(fch,width=24); e.grid(row=0,column=i*2+1,padx=6,pady=8,sticky="w"); e.insert(0,tags_padrao[i]); canal_entries.append(e)
    fb=ttk.Frame(root); fb.pack(fill="x",padx=8,pady=4)
    btn_start=ttk.Button(fb,text="START",command=start,width=16); btn_start.pack(side="left",padx=6)
    btn_pause=ttk.Button(fb,text="Pausar",command=pause,width=16,state="disabled"); btn_pause.pack(side="left",padx=6)
    btn_stop=ttk.Button(fb,text="Parar",command=parar_aquisicao,width=16,state="disabled"); btn_stop.pack(side="left",padx=6)
    btn_reset_zoom=ttk.Button(fb,text="Reset Zoom",command=resetar_zoom,width=16); btn_reset_zoom.pack(side="left",padx=6)
    btn_testar_vetor=ttk.Button(fb,text="Testar leitura vetor",command=testar_leitura_vetor,width=20); btn_testar_vetor.pack(side="left",padx=6)
    btn_diagnostico_modbus=ttk.Button(fb,text="Diagnóstico Modbus",command=diagnostico_modbus_pontual,width=20,)
    status_var=tk.StringVar(value="Pronto."); label_status=ttk.Label(fb,textvariable=status_var,foreground="blue"); label_status.pack(side="left",padx=20)
    label_vetor_status=ttk.Label(root,text="Vetor M340 ainda não lido.",foreground="gray"); label_vetor_status.pack(anchor="w",padx=8)
    fv=ttk.LabelFrame(root,text="Tempo Sob Pressão (s)"); fv.pack(fill="x",padx=8,pady=4)
    label_tempos_sob_pressao=ttk.Label(fv,text="Nenhum período detectado ainda.",foreground="#0057B8",font=("Consolas",10)); label_tempos_sob_pressao.pack(anchor="w",padx=8,pady=4)
    fvent=ttk.LabelFrame(root,text="Tempo de Alívio de Pressão (s)"); fvent.pack(fill="x",padx=8,pady=4)
    label_tempos_ventilacao=ttk.Label(fvent,text="Nenhum alívio de pressão detectado ainda.",foreground="#F28E2B",font=("Consolas",10)); label_tempos_ventilacao.pack(anchor="w",padx=8,pady=4)
    fg=ttk.Frame(root); fg.pack(fill="both",expand=True,padx=8,pady=4); fig=Figure(figsize=(12,6),dpi=100); ax=fig.add_subplot(111); aplicar_estilo_grafico(ax,fig)
    canvas=FigureCanvasTkAgg(fig,master=fg); canvas.get_tk_widget().pack(fill="both",expand=True); toolbar=NavigationToolbar2Tk(canvas,fg); toolbar.update()
    canvas.mpl_connect("scroll_event",on_scroll_zoom); canvas.mpl_connect("button_press_event",on_mouse_press); canvas.mpl_connect("button_release_event",on_mouse_release); canvas.mpl_connect("motion_notify_event",on_mouse_move); canvas.draw_idle()


# ============================================================
# ALT27C - SOMENTE CSV PRINCIPAL + PNG / SEM FORM[0] NO HISTORICO
# ============================================================

_alt27c_salvar_ciclo_original = salvar_ciclo_automatico


def _alt27c_base_mais_recente(numero_ciclo, inicio_execucao):
    pasta = obter_pasta_saida()
    padrao_principal = re.compile(
        rf"^(?:Maquina_[0-9A-Za-z_-]+_)?ciclo_{int(numero_ciclo):04d}_\d{{8}}_\d{{6}}\.csv$"
    )
    candidatos = []
    for nome in os.listdir(pasta):
        if not padrao_principal.match(nome):
            continue
        if any(nome.endswith(s) for s in (
            "_parametros_form_m340.csv",
            "_periodos_sob_pressao.csv",
            "_tempos_sob_pressao.csv",
            "_tempos_ventilacao.csv",
        )):
            continue
        caminho = os.path.join(pasta, nome)
        try:
            if os.path.getmtime(caminho) >= inicio_execucao - 2.0:
                candidatos.append(caminho[:-4])
        except OSError:
            pass
    return max(candidatos, key=os.path.getmtime) if candidatos else None


def _alt27c_remover_auxiliares(base):
    if not base:
        return
    for sufixo in (
        "_parametros_form_m340.csv",
        "_periodos_sob_pressao.csv",
        "_tempos_sob_pressao.csv",
        "_tempos_ventilacao.csv",
    ):
        caminho = base + sufixo
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
                print(f"[ALT27C] Arquivo auxiliar removido: {os.path.basename(caminho)}")
        except OSError as e:
            print(f"[AVISO ALT27C] Falha ao remover {caminho}: {e}")


def _alt27c_atualizar_historico(numero_ciclo, base):
    arquivo_base = os.path.basename(base) if base else ""
    with historico_resultados_lock:
        for item in reversed(historico_resultados):
            if int(item.get("numero_ciclo", -1)) != int(numero_ciclo):
                continue
            if arquivo_base and item.get("arquivo_base") not in (None, "", arquivo_base):
                continue
            item.pop("form_salvo", None)
            item.pop("arquivo_form", None)
            item.pop("erro_form", None)
            csv_ok = bool(item.get("csv_salvo"))
            png_ok = bool(item.get("png_salvo"))
            item["status_geral"] = (
                "Salvo com sucesso" if csv_ok and png_ok
                else "Salvo parcialmente" if csv_ok or png_ok
                else "Erro de salvamento"
            )
            if csv_ok and png_ok:
                item["mensagem"] = "CSV e PNG foram salvos."
            elif csv_ok or png_ok:
                item["mensagem"] = "Somente um dos arquivos oficiais foi salvo."
            else:
                item["mensagem"] = "CSV e PNG não foram salvos."
            break


def salvar_ciclo_automatico(snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form=None):
    """ALT27C: preserva o salvamento validado e mantém somente CSV principal e PNG."""
    inicio = time.time()
    resultado = _alt27c_salvar_ciclo_original(
        snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form
    )
    base = _alt27c_base_mais_recente(numero_ciclo, inicio)
    _alt27c_remover_auxiliares(base)
    _alt27c_atualizar_historico(numero_ciclo, base)
    return resultado


def _alt27c_buffers_do_csv(caminho):
    buffers_csv = [[], [], []]
    if not os.path.isfile(caminho):
        return buffers_csv, 0
    with open(caminho, "r", newline="", encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f, delimiter=";")
        campos = leitor.fieldnames or []
        campo_tempo = next((c for c in campos if c == "Tempo_s"), None)
        canais = [c for c in campos if c.startswith("CH")][:3]
        if not campo_tempo or len(canais) < 3:
            raise ValueError("CSV principal sem Tempo_s ou sem os três canais esperados.")
        quantidade = 0
        for linha in leitor:
            try:
                t = float(str(linha[campo_tempo]).replace(",", "."))
                valores = [float(str(linha[c]).replace(",", ".")) for c in canais]
            except (TypeError, ValueError, KeyError):
                continue
            for i, valor in enumerate(valores):
                buffers_csv[i].append((t, valor))
            quantidade += 1
    return buffers_csv, quantidade


def consultar_detalhes_ciclo(arquivo_base):
    """ALT27C: consulta somente o CSV principal e o PNG; períodos são reconstruídos em memória."""
    try:
        nome = _alt27a_validar_base(arquivo_base)
        base = os.path.join(obter_pasta_saida(), nome)
        caminho_csv = base + ".csv"
        caminho_png = base + ".png"
        buffers_csv, quantidade = _alt27c_buffers_do_csv(caminho_csv)
        periodos = calcular_periodos_sob_pressao(buffers_csv) if quantidade else []
        alivios = calcular_periodos_ventilacao(buffers_csv) if quantidade else []
        png_base64 = ""
        if os.path.isfile(caminho_png):
            with open(caminho_png, "rb") as f:
                png_base64 = base64.b64encode(f.read()).decode("ascii")
        ausentes = [
            os.path.basename(caminho)
            for caminho in (caminho_csv, caminho_png)
            if not os.path.isfile(caminho)
        ]
        numero = 0
        data_hora = ""
        correspondencia = re.match(r"^(?:Maquina_[0-9A-Za-z_-]+_)?ciclo_(\d+)_(\d{8})_(\d{6})$", nome)
        if correspondencia:
            numero = int(correspondencia.group(1))
            try:
                data_hora = datetime.strptime(
                    correspondencia.group(2) + correspondencia.group(3),
                    "%Y%m%d%H%M%S",
                ).strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                pass
        return {
            "sucesso": True,
            "mensagem": "Detalhes carregados." if not ausentes else "Detalhes carregados com arquivo oficial ausente.",
            "arquivo_base": nome,
            "numero_ciclo": numero,
            "data_hora": data_hora,
            "quantidade_amostras": quantidade,
            "tempo_total_sob_pressao_s": round(sum(float(p.get("duracao_s", 0)) for p in periodos), 3),
            "quantidade_periodos_sob_pressao": len(periodos),
            "tempo_total_alivio_pressao_s": round(sum(float(p.get("duracao_s", 0)) for p in alivios), 3),
            "quantidade_alivios_pressao": len(alivios),
            "periodos_sob_pressao": periodos,
            "periodos_alivio_pressao": alivios,
            "png_base64": png_base64,
            "arquivos_ausentes": ausentes,
        }
    except Exception as e:
        return {"sucesso": False, "mensagem": f"Falha ao consultar ciclo: {e}"}




# ALT28A - envolve o salvamento existente: graficos/calculos usam tratado; CSV recupera bruto.
_alt28a_salvar_ciclo_anterior = salvar_ciclo_automatico


def salvar_ciclo_automatico(snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form=None):
    inicio_execucao = time.time()
    resultado = _alt28a_salvar_ciclo_anterior(
        snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form
    )
    caminho_csv = localizar_csv_principal_recente(numero_ciclo, inicio_execucao)
    restaurar_pressao_bruta_no_csv(caminho_csv, snapshot_buffers)
    return resultado



# ============================================================
# ALT29A - TEMPERATURAS, PNG E HISTORICO TERMICO
# ============================================================

def _alt29a_temperaturas_ativas(dados=None):
    dados = buffers if dados is None else dados
    return bool(dados and len(dados) >= 6 and all(dados[i] for i in (3, 4, 5)))


def _alt29a_valores(buffer, fator=1.0):
    saida=[]
    for _, valor in buffer or []:
        try: saida.append(float(valor)*float(fator))
        except (TypeError, ValueError): pass
    return saida


def calcular_resumo_temperaturas(snapshot_buffers):
    vazio={'disponivel':False,'programada_final':None,'lida_1_final':None,'lida_2_final':None,
           'lida_1_minima':None,'lida_1_maxima':None,'lida_2_minima':None,'lida_2_maxima':None,
           'desvio_final_1':None,'desvio_final_2':None}
    if not _alt29a_temperaturas_ativas(snapshot_buffers): return vazio
    p=_alt29a_valores(snapshot_buffers[3],FATOR_ESCALA_TEMPERATURA_PROGRAMADA)
    t1=_alt29a_valores(snapshot_buffers[4],FATOR_ESCALA_TEMPERATURA_LIDA_1)
    t2=_alt29a_valores(snapshot_buffers[5],FATOR_ESCALA_TEMPERATURA_LIDA_2)
    if not (p and t1 and t2): return vazio
    return {'disponivel':True,'programada_final':p[-1],'lida_1_final':t1[-1],'lida_2_final':t2[-1],
            'lida_1_minima':min(t1),'lida_1_maxima':max(t1),'lida_2_minima':min(t2),'lida_2_maxima':max(t2),
            'desvio_final_1':t1[-1]-p[-1],'desvio_final_2':t2[-1]-p[-1]}


def _alt29a_resumo_do_csv(caminho):
    if not os.path.isfile(caminho): return calcular_resumo_temperaturas([])
    dados=[[],[],[],[],[],[]]
    with open(caminho,'r',newline='',encoding='utf-8-sig') as f:
        leitor=csv.DictReader(f,delimiter=';'); campos=leitor.fieldnames or []
        canais=[c for c in campos if c.startswith('CH')]
        if len(canais)<6: return calcular_resumo_temperaturas([])
        for linha in leitor:
            try: t=float(str(linha.get('Tempo_s','')).replace(',','.'))
            except ValueError: continue
            for i,campo in enumerate(canais[:6]):
                try: dados[i].append((t,float(str(linha[campo]).replace(',','.'))))
                except (ValueError,TypeError,KeyError): pass
    return calcular_resumo_temperaturas(dados)


_alt29a_png_anterior = salvar_png_snapshot

def salvar_png_snapshot(caminho_png, snapshot_buffers, snapshot_tags):
    if not _alt29a_temperaturas_ativas(snapshot_buffers):
        return _alt29a_png_anterior(caminho_png,snapshot_buffers,snapshot_tags)
    fs=Figure(figsize=(12,10),dpi=150)
    axp=fs.add_subplot(211); axt=fs.add_subplot(212)
    aplicar_estilo_grafico(axp,fs); axp.set_title('Pressao do ciclo'); axp.set_ylabel('Pressao')
    for i in (INDICE_PRESSAO_LIDA,INDICE_PRESSAO_PROGRAMADA):
        b=snapshot_buffers[i]
        if b:
            t0=b[0][0]; axp.plot([x[0]-t0 for x in b],[x[1] for x in b],color=cor_do_canal(i),linewidth=1.3,label=snapshot_tags[i])
    desenhar_limites_pressao_programada(axp,snapshot_buffers)
    desenhar_marcadores_pressao_fora_limites(axp,snapshot_buffers)
    axp.relim(); axp.autoscale_view(); ajustar_eixo_y_para_limites(axp); aplicar_estilo_legenda(axp)
    aplicar_estilo_grafico(axt,fs); axt.set_title('Temperaturas da prensa'); axt.set_ylabel('Temperatura (°C)')
    cores=['#7B61D1','#138A5B','#E07822']; estilos=['--','-','-']; fatores=[FATOR_ESCALA_TEMPERATURA_PROGRAMADA,FATOR_ESCALA_TEMPERATURA_LIDA_1,FATOR_ESCALA_TEMPERATURA_LIDA_2]
    for j,i in enumerate((3,4,5)):
        b=snapshot_buffers[i]; t0=b[0][0]
        axt.plot([x[0]-t0 for x in b],[float(x[1])*fatores[j] for x in b],color=cores[j],linestyle=estilos[j],linewidth=1.5,label=snapshot_tags[i])
    aplicar_estilo_legenda(axt)
    sp=obter_vetor_tempos_sob_pressao(snapshot_buffers); vt=obter_vetor_tempos_ventilacao(snapshot_buffers)
    fs.text(.01,.045,formatar_vetor_para_png('Tempo Sob Pressao',sp,'periodo(s)'),fontsize=8,family='monospace',color='#0057B8')
    fs.text(.01,.015,formatar_vetor_para_png('Tempo de Alivio de Pressao',vt,'alivio(s)'),fontsize=8,family='monospace',color='#F28E2B')
    fs.tight_layout(rect=[0,.07,1,1]); fs.savefig(caminho_png)


_alt29a_salvar_anterior = salvar_ciclo_automatico

def salvar_ciclo_automatico(snapshot_buffers,snapshot_tags,numero_ciclo,snapshot_form=None):
    resultado=_alt29a_salvar_anterior(snapshot_buffers,snapshot_tags,numero_ciclo,snapshot_form)
    resumo=calcular_resumo_temperaturas(snapshot_buffers)
    with historico_resultados_lock:
        for item in reversed(historico_resultados):
            if int(item.get('numero_ciclo',-1))==int(numero_ciclo):
                item['resumo_temperatura']=dict(resumo)
                item['dados_temperatura_disponiveis']=bool(resumo['disponivel'])
                if resumo['disponivel']:
                    item.update({'temperatura_programada_final':resumo['programada_final'],'temperatura_lida_1_final':resumo['lida_1_final'],'temperatura_lida_2_final':resumo['lida_2_final']})
                break
    return resultado


_alt29a_detalhes_anterior = consultar_detalhes_ciclo

def consultar_detalhes_ciclo(arquivo_base):
    resposta=_alt29a_detalhes_anterior(arquivo_base)
    if resposta.get('sucesso'):
        resposta['resumo_temperatura']=_alt29a_resumo_do_csv(os.path.join(obter_pasta_saida(),arquivo_base+'.csv'))
    return resposta



# ============================================================
# ALT30A - CONSOLIDACAO CSV/PNG E LIMITES TERMICOS
# ============================================================

COR_LIMITE_TEMPERATURA = "#C1121F"
ESTILO_LIMITE_TEMPERATURA = "--"
ESPESSURA_LIMITE_TEMPERATURA = 1.4
COR_MARCADOR_TEMP_1 = "#FFFF00"
BORDA_MARCADOR_TEMP_1 = "#176B3A"
COR_MARCADOR_TEMP_2 = "#FFFF00"
BORDA_MARCADOR_TEMP_2 = "#B45F06"
TAMANHO_MARCADOR_TEMPERATURA = 32

_alt30a_tolerancia_snapshot = None


def _alt30a_numero_ou_none(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _alt30a_tolerancia_do_form(snapshot_form=None):
    fonte = snapshot_form if snapshot_form is not None else ultimo_vetor_m340_descrito
    for item in fonte or []:
        if item.get("nome") == "FORM[0].ToleranciaDeTemperatura":
            return _alt30a_numero_ou_none(item.get("valor"))
    return None


def calcular_limites_termicos(snapshot_buffers, tolerancia=None):
    tolerancia = _alt30a_numero_ou_none(tolerancia)
    vazio = {
        "disponivel": False,
        "tolerancia": tolerancia,
        "tempos": [],
        "limites_minimos": [],
        "limites_maximos": [],
        "pontos_lida_1": [],
        "pontos_lida_2": [],
    }
    if tolerancia is None:
        return vazio
    if not snapshot_buffers or len(snapshot_buffers) < 6:
        return vazio
    bp, b1, b2 = snapshot_buffers[3], snapshot_buffers[4], snapshot_buffers[5]
    n = min(len(bp), len(b1), len(b2))
    if n <= 0:
        return vazio

    t0 = float(bp[0][0])
    tempos, mins, maxs, fora1, fora2 = [], [], [], [], []
    for i in range(n):
        try:
            tempo = float(bp[i][0]) - t0
            programada = float(bp[i][1]) * FATOR_ESCALA_TEMPERATURA_PROGRAMADA
            lida1 = float(b1[i][1]) * FATOR_ESCALA_TEMPERATURA_LIDA_1
            lida2 = float(b2[i][1]) * FATOR_ESCALA_TEMPERATURA_LIDA_2
        except (TypeError, ValueError, IndexError):
            continue
        minimo = programada - tolerancia
        maximo = programada + tolerancia
        tempos.append(tempo)
        mins.append(minimo)
        maxs.append(maximo)
        if lida1 < minimo or lida1 > maximo:
            fora1.append({"tempo_s": tempo, "valor": lida1})
        if lida2 < minimo or lida2 > maximo:
            fora2.append({"tempo_s": tempo, "valor": lida2})

    return {
        "disponivel": bool(tempos),
        "tolerancia": tolerancia,
        "tempos": tempos,
        "limites_minimos": mins,
        "limites_maximos": maxs,
        "pontos_lida_1": fora1,
        "pontos_lida_2": fora2,
    }


def _alt30a_enriquecer_resumo(snapshot_buffers, tolerancia=None):
    resumo = calcular_resumo_temperaturas(snapshot_buffers)
    limites = calcular_limites_termicos(snapshot_buffers, tolerancia)
    resumo = dict(resumo)
    resumo.update({
        "tolerancia_temperatura": limites.get("tolerancia"),
        "limite_minimo_final": limites["limites_minimos"][-1] if limites["limites_minimos"] else None,
        "limite_maximo_final": limites["limites_maximos"][-1] if limites["limites_maximos"] else None,
        "amostras_lida_1_fora_limites": len(limites["pontos_lida_1"]),
        "amostras_lida_2_fora_limites": len(limites["pontos_lida_2"]),
        "limites_disponiveis": bool(limites["disponivel"]),
    })
    return resumo


def _alt30a_localizar_base_recente(numero_ciclo, inicio_execucao):
    pasta = obter_pasta_saida()
    padrao_principal = re.compile(
        rf"^(?:Maquina_[0-9A-Za-z_-]+_)?ciclo_{int(numero_ciclo):04d}_\d{{8}}_\d{{6}}\.csv$"
    )
    candidatos = []
    for nome in os.listdir(pasta):
        if not padrao_principal.match(nome):
            continue
        if any(nome.endswith(s) for s in (
            "_parametros_form_m340.csv",
            "_periodos_sob_pressao.csv",
            "_tempos_sob_pressao.csv",
            "_tempos_ventilacao.csv",
        )):
            continue
        caminho = os.path.join(pasta, nome)
        try:
            if os.path.getmtime(caminho) >= inicio_execucao - 3.0:
                candidatos.append(caminho[:-4])
        except OSError:
            pass
    return max(candidatos, key=os.path.getmtime) if candidatos else None


def _alt30a_remover_auxiliares_novos(base):
    removidos = []
    if not base:
        return removidos
    for sufixo in (
        "_parametros_form_m340.csv",
        "_periodos_sob_pressao.csv",
        "_tempos_sob_pressao.csv",
        "_tempos_ventilacao.csv",
    ):
        caminho = base + sufixo
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
                removidos.append(os.path.basename(caminho))
        except OSError as exc:
            print(f"[AVISO ALT30A] Falha ao remover {caminho}: {exc}")
    if removidos:
        print("[ALT30A] Arquivos auxiliares removidos: " + ", ".join(removidos))
    return removidos


_alt30a_png_anterior = salvar_png_snapshot


def salvar_png_snapshot(caminho_png, snapshot_buffers, snapshot_tags):
    """ALT30A - preserva o PNG atual e acrescenta limites/marcadores térmicos."""
    if not _alt29a_temperaturas_ativas(snapshot_buffers):
        return _alt30a_png_anterior(caminho_png, snapshot_buffers, snapshot_tags)

    fs = Figure(figsize=(12, 10), dpi=150)
    axp = fs.add_subplot(211)
    axt = fs.add_subplot(212)

    aplicar_estilo_grafico(axp, fs)
    axp.set_title("Pressao do ciclo")
    axp.set_ylabel("Pressao")
    for i in (INDICE_PRESSAO_LIDA, INDICE_PRESSAO_PROGRAMADA):
        b = snapshot_buffers[i]
        if not b:
            continue
        t0 = b[0][0]
        axp.plot(
            [x[0] - t0 for x in b], [x[1] for x in b],
            color=cor_do_canal(i), linewidth=1.3,
            label=snapshot_tags[i] if i < len(snapshot_tags) else f"CH{i+1}",
        )
    desenhar_limites_pressao_programada(axp, snapshot_buffers)
    desenhar_marcadores_pressao_fora_limites(axp, snapshot_buffers)
    axp.relim(); axp.autoscale_view()
    ajustar_eixo_y_para_limites(axp)
    aplicar_estilo_legenda(axp)

    aplicar_estilo_grafico(axt, fs)
    axt.set_title("Temperaturas da prensa")
    axt.set_ylabel("Temperatura (°C)")
    cores = ["#7B61D1", "#138A5B", "#E07822"]
    estilos = ["--", "-", "-"]
    fatores = [
        FATOR_ESCALA_TEMPERATURA_PROGRAMADA,
        FATOR_ESCALA_TEMPERATURA_LIDA_1,
        FATOR_ESCALA_TEMPERATURA_LIDA_2,
    ]
    for j, i in enumerate((3, 4, 5)):
        b = snapshot_buffers[i]
        if not b:
            continue
        t0 = b[0][0]
        axt.plot(
            [x[0] - t0 for x in b],
            [float(x[1]) * fatores[j] for x in b],
            color=cores[j], linestyle=estilos[j], linewidth=1.5,
            label=snapshot_tags[i] if i < len(snapshot_tags) else f"CH{i+1}",
        )

    limites = calcular_limites_termicos(snapshot_buffers, _alt30a_tolerancia_snapshot)
    if limites["disponivel"]:
        axt.plot(
            limites["tempos"], limites["limites_minimos"],
            color=COR_LIMITE_TEMPERATURA,
            linestyle=ESTILO_LIMITE_TEMPERATURA,
            linewidth=ESPESSURA_LIMITE_TEMPERATURA,
            label="Limite temperatura min.",
        )
        axt.plot(
            limites["tempos"], limites["limites_maximos"],
            color=COR_LIMITE_TEMPERATURA,
            linestyle=ESTILO_LIMITE_TEMPERATURA,
            linewidth=ESPESSURA_LIMITE_TEMPERATURA,
            label="Limite temperatura max.",
        )
        if limites["pontos_lida_1"]:
            axt.scatter(
                [p["tempo_s"] for p in limites["pontos_lida_1"]],
                [p["valor"] for p in limites["pontos_lida_1"]],
                color=COR_MARCADOR_TEMP_1, edgecolors=BORDA_MARCADOR_TEMP_1,
                linewidths=0.7, s=TAMANHO_MARCADOR_TEMPERATURA,
                zorder=25, label="Lida 1 fora dos limites",
            )
        if limites["pontos_lida_2"]:
            axt.scatter(
                [p["tempo_s"] for p in limites["pontos_lida_2"]],
                [p["valor"] for p in limites["pontos_lida_2"]],
                color=COR_MARCADOR_TEMP_2, edgecolors=BORDA_MARCADOR_TEMP_2,
                linewidths=0.7, s=TAMANHO_MARCADOR_TEMPERATURA,
                zorder=25, label="Lida 2 fora dos limites",
            )
    else:
        print("[AVISO TEMPERATURA] Tolerancia de temperatura indisponivel. Limites termicos nao calculados.")

    axt.relim(); axt.autoscale_view()
    aplicar_estilo_legenda(axt)
    sp = obter_vetor_tempos_sob_pressao(snapshot_buffers)
    vt = obter_vetor_tempos_ventilacao(snapshot_buffers)
    fs.text(.01, .045, formatar_vetor_para_png("Tempo Sob Pressao", sp, "periodo(s)"), fontsize=8, family="monospace", color="#0057B8")
    fs.text(.01, .015, formatar_vetor_para_png("Tempo de Alivio de Pressao", vt, "alivio(s)"), fontsize=8, family="monospace", color="#F28E2B")
    fs.tight_layout(rect=[0, .07, 1, 1])
    fs.savefig(caminho_png)


_alt30a_salvar_anterior = salvar_ciclo_automatico


def salvar_ciclo_automatico(snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form=None):
    """ALT30A - usa snapshot FORM, mantém CSV/PNG e remove auxiliares do novo ciclo."""
    global _alt30a_tolerancia_snapshot
    inicio_execucao = time.time()
    _alt30a_tolerancia_snapshot = _alt30a_tolerancia_do_form(snapshot_form)
    try:
        resultado = _alt30a_salvar_anterior(
            snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form
        )
        base = _alt30a_localizar_base_recente(numero_ciclo, inicio_execucao)
        _alt30a_remover_auxiliares_novos(base)
        resumo = _alt30a_enriquecer_resumo(
            snapshot_buffers, _alt30a_tolerancia_snapshot
        )
        arquivo_base = os.path.basename(base) if base else ""
        with historico_resultados_lock:
            for item in reversed(historico_resultados):
                if int(item.get("numero_ciclo", -1)) != int(numero_ciclo):
                    continue
                if arquivo_base and item.get("arquivo_base") not in (None, "", arquivo_base):
                    continue
                item["resumo_temperatura"] = dict(resumo)
                item["dados_temperatura_disponiveis"] = bool(resumo.get("disponivel"))
                item.pop("form_salvo", None)
                item.pop("arquivo_form", None)
                item.pop("erro_form", None)
                csv_ok = bool(item.get("csv_salvo"))
                png_ok = bool(item.get("png_salvo"))
                item["status_geral"] = (
                    "Salvo com sucesso" if csv_ok and png_ok
                    else "Salvo parcialmente" if csv_ok or png_ok
                    else "Erro de salvamento"
                )
                break
        return resultado
    finally:
        _alt30a_tolerancia_snapshot = None



# ============================================================
# ALT30B - ARTEFATOS OFICIAIS, PADROES TERMICOS E HISTORICO
# ============================================================

# As funcoes de calculo permanecem. Somente a gravacao dos CSVs auxiliares
# e neutralizada antes de qualquer ciclo ser executado.
def _alt30b_form_sem_arquivo(base, snapshot_form=None):
    return "__ALT30B_NAO_GERADO__"


def _alt30b_periodos_sem_arquivo(base, snapshot_buffers):
    return "__ALT30B_NAO_GERADO__", calcular_periodos_sob_pressao(snapshot_buffers)


def _alt30b_tempos_pressao_sem_arquivo(base, snapshot_buffers):
    periodos = calcular_periodos_sob_pressao(snapshot_buffers)
    return "__ALT30B_NAO_GERADO__", [p["duracao_s"] for p in periodos]


def _alt30b_ventilacao_sem_arquivo(base, snapshot_buffers):
    periodos = calcular_periodos_ventilacao(snapshot_buffers)
    return "__ALT30B_NAO_GERADO__", [p["duracao_s"] for p in periodos]


# Substituicao global: o salvamento original continua calculando e registrando
# o ciclo, mas nao cria os quatro arquivos auxiliares.
salvar_parametros_form_m340_descritos = _alt30b_form_sem_arquivo
salvar_periodos_sob_pressao = _alt30b_periodos_sem_arquivo
salvar_tempos_sob_pressao = _alt30b_tempos_pressao_sem_arquivo
salvar_tempos_ventilacao = _alt30b_ventilacao_sem_arquivo


_alt30b_salvar_anterior = salvar_ciclo_automatico


def salvar_ciclo_automatico(snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form=None):
    resultado = _alt30b_salvar_anterior(
        snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form
    )
    # O historico oficial considera somente CSV principal e PNG.
    with historico_resultados_lock:
        for item in reversed(historico_resultados):
            if int(item.get("numero_ciclo", -1)) != int(numero_ciclo):
                continue
            item.pop("form_salvo", None)
            item.pop("arquivo_form", None)
            item.pop("erro_form", None)
            csv_ok = bool(item.get("csv_salvo"))
            png_ok = bool(item.get("png_salvo"))
            item["status_geral"] = (
                "Salvo com sucesso" if csv_ok and png_ok
                else "Salvo parcialmente" if csv_ok or png_ok
                else "Erro de salvamento"
            )
            item["mensagem"] = (
                "CSV e PNG foram salvos." if csv_ok and png_ok
                else "Somente um dos arquivos oficiais foi salvo." if csv_ok or png_ok
                else "CSV e PNG nao foram salvos."
            )
            break
    return resultado


class OraculumHtmlApi:

    def obter_detalhes_ciclo(self, arquivo_base):
        return consultar_detalhes_ciclo(arquivo_base)
    """Ponte HTML independente dos widgets Tkinter (ALT23B)."""

    @staticmethod
    def resposta(sucesso, mensagem, **dados):
        return {"sucesso": bool(sucesso), "mensagem": str(mensagem), **dados}

    def obter_configuracao(self):
        return {**config_html, "tags": list(config_html["tags"])}

    def salvar_configuracao(self, configuracao):
        global mensagem_html
        if rodando:
            return self.resposta(False, "Pare a monitoração antes de alterar a configuração.")
        try:
            cfg = configuracao or {}
            ip = str(cfg.get("ip", "")).strip()
            tags = [str(x).strip() for x in cfg.get("tags", [])]
            if not ip:
                raise ValueError("Informe o IP do CLP.")
            if len(tags) != 3 or not all(tags):
                raise ValueError("Informe os três sinais de pressão.")
            # Valida os endereços antes de aceitar a configuração.
            parse_schneider_tag(str(cfg.get("trigger", TRIGGER_PADRAO)).strip() or TRIGGER_PADRAO)
            parse_mw_address(str(cfg.get("flag_monitor_status", FLAG_MONITOR_STATUS_PADRAO)).strip())
            for tag in tags:
                parse_schneider_tag(tag)
            config_html.update({
                "ip": ip,
                "protocolo": str(cfg.get("protocolo", PROTOCOLO_PADRAO)).strip() or PROTOCOLO_PADRAO,
                "porta": 502,
                "offset_modbus": int(cfg.get("offset_modbus", 0)),
                "trigger": str(cfg.get("trigger", TRIGGER_PADRAO)).strip() or TRIGGER_PADRAO,
                "flag_monitor_status": str(cfg.get("flag_monitor_status", FLAG_MONITOR_STATUS_PADRAO)).strip() or FLAG_MONITOR_STATUS_PADRAO,
                "tipo_trigger": str(cfg.get("tipo_trigger", TIPO_TRIGGER_PADRAO)).strip() or TIPO_TRIGGER_PADRAO,
                "trigger_habilitado": bool(cfg.get("trigger_habilitado", True)),
                "monitorar_pressao_zero": bool(cfg.get("monitorar_pressao_zero", False)),
                "tags": tags,
            })
            mensagem_html = "Configuração atualizada."
            return self.resposta(True, mensagem_html, configuracao=self.obter_configuracao())
        except Exception as erro:
            mensagem_html = f"Configuração inválida: {erro}"
            return self.resposta(False, mensagem_html)

    def iniciar(self):
        global rodando, pausado, thread_aquisicao, buffers, tags_ativas, zoom_usuario_ativo, mensagem_html
        if rodando:
            return self.resposta(True, "A monitoração já está em execução.")
        try:
            ip = config_html["ip"]
            tags_ativas = list(config_html["tags"])
            if not ip or not tags_ativas:
                raise ValueError("Informe IP e os sinais de pressão.")
            buffers = [[] for _ in tags_ativas]
            zoom_usuario_ativo = False
            try:
                ler_vetor_m340_automatico(ip)
            except Exception as erro:
                print(f"[ALT23B][AVISO] Falha ao ler FORM[0] no início: {erro}")
            rodando = True
            pausado = False
            mensagem_html = "Monitoração iniciada."
            thread_aquisicao = threading.Thread(
                target=leitor_com_trigger,
                args=(
                    ip,
                    config_html["protocolo"],
                    tags_ativas,
                    config_html["trigger"],
                    bool(config_html["trigger_habilitado"]),
                    config_html["tipo_trigger"],
                    bool(config_html["monitorar_pressao_zero"]),
                ),
                daemon=True,
            )
            thread_aquisicao.start()
            return self.resposta(True, mensagem_html)
        except Exception as erro:
            rodando = False
            mensagem_html = f"Falha ao iniciar: {erro}"
            print(f"[ALT23B][ERRO] {mensagem_html}")
            return self.resposta(False, mensagem_html)

    def pausar(self):
        global pausado, mensagem_html
        if not rodando:
            return self.resposta(False, "A monitoração está parada.")
        pausado = not pausado
        mensagem_html = "Monitoração pausada." if pausado else "Monitoração retomada."
        return self.resposta(True, mensagem_html)

    def parar(self):
        global rodando, pausado, mensagem_html
        rodando = False
        pausado = False
        atualizar_flag_monitor_status(STATUS_CONCLUIDO)
        mensagem_html = "Monitoração parada."
        return self.resposta(True, mensagem_html)

    def obter_diagnostico(self):
        """Lê diretamente os cinco registradores do contrato da interface."""
        global ultima_comunicacao_ok, ultimo_trigger_lido, ultimo_monitor_status
        ip = config_html["ip"]
        sinais = {
            "pressao_lida": "MW413:UINT",
            "pressao_programada": "MW3002:UINT",
            "inercia": "MW515:UINT",
            "trigger": "MW3000:UINT",
            "monitor": "MW3004:UINT",
        }
        valores, erros = {}, {}
        for nome, tag in sinais.items():
            try:
                valores[nome] = ler_tag_schneider(ip, tag)
            except Exception as erro:
                erros[nome] = str(erro)
                print(f"[ALT23B][ERRO] Falha na leitura {tag}: {erro}")
        conectado = not erros and len(valores) == len(sinais)
        if conectado:
            ultima_comunicacao_ok = time.time()
            ultimo_trigger_lido = int(valores["trigger"])
            ultimo_monitor_status = int(valores["monitor"])
        return {
            "online": True, "conectado": conectado, "ip": ip, "porta": 502,
            "pressao_lida": valores.get("pressao_lida"),
            "pressao_programada": valores.get("pressao_programada"),
            "inercia": valores.get("inercia"),
            "trigger": valores.get("trigger"), "monitor": valores.get("monitor"),
            "erros": erros,
            "atualizado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }

    def testar_comunicacao(self):
        diagnostico = self.obter_diagnostico()
        if diagnostico["conectado"]:
            return self.resposta(True, "Comunicação OK. Os cinco registradores foram lidos.", diagnostico=diagnostico)
        detalhes = "; ".join(f"{nome}: {erro}" for nome, erro in diagnostico["erros"].items()) or "nenhum valor retornado"
        return self.resposta(False, f"Falha na comunicação Modbus: {detalhes}", diagnostico=diagnostico)

    def testar_form(self):
        global ultima_comunicacao_ok
        try:
            valores = ler_vetor_m340_automatico(config_html["ip"])
            ultima_comunicacao_ok = time.time()
            return self.resposta(True, f"FORM[0] lido: {len(valores)} / {QUANTIDADE_VETOR_FORM_M340} registros.")
        except Exception as erro:
            print(f"[ALT23B][ERRO] Falha ao ler FORM[0]: {erro}")
            return self.resposta(False, f"Falha ao ler FORM[0]: {erro}")

    def obter_estado(self):
        b0 = list(buffers[0])[-2000:] if len(buffers) > 0 else []
        b1 = list(buffers[1])[-2000:] if len(buffers) > 1 else []
        b2 = list(buffers[2])[-2000:] if len(buffers) > 2 else []
        t0 = b0[0][0] if b0 else 0.0
        conectado = ultima_comunicacao_ok > 0 and time.time() - ultima_comunicacao_ok < 2.0
        return {
            "rodando": bool(rodando), "pausado": bool(pausado), "conectado": bool(conectado),
            "ciclo_ativo": bool(rodando and ultimo_trigger_lido), "trigger": int(ultimo_trigger_lido),
            "monitor_status": int(ultimo_monitor_status), "pressao_lida": b0[-1][1] if b0 else 0,
            "pressao_programada": b1[-1][1] if b1 else 0, "inercia_pressao": b2[-1][1] if b2 else 0,
            "form_quantidade": len(ultimo_vetor_m340), "amostras": len(b0),
            "tempos_sob_pressao": list(tempos_sob_pressao), "tempos_ventilacao": list(tempos_ventilacao),
            "limite_minimo": limite_pressao_programada_min, "limite_maximo": limite_pressao_programada_max,
            "serie_tempo": [round(x[0] - t0, 3) for x in b0],
            "serie_pressao_lida": [x[1] for x in b0], "serie_pressao_programada": [x[1] for x in b1],
            "mensagem": mensagem_html, "ultimo_arquivo": ultimo_arquivo_salvo,
            "resultados": _copiar_historico_resultados(),
        }




# ALT29A - amplia o estado HTML sem alterar a aquisicao existente.
_alt29a_obter_estado_original = OraculumHtmlApi.obter_estado

def _alt29a_obter_estado(self, *args, **kwargs):
    estado=_alt29a_obter_estado_original(self,*args,**kwargs)
    ativo=_alt29a_temperaturas_ativas()
    estado['temperaturas_configuradas']=ativo
    nomes=('temperatura_programada','temperatura_lida_1','temperatura_lida_2')
    fatores=(FATOR_ESCALA_TEMPERATURA_PROGRAMADA,FATOR_ESCALA_TEMPERATURA_LIDA_1,FATOR_ESCALA_TEMPERATURA_LIDA_2)
    for j,nome in enumerate(nomes,3):
        b=buffers[j] if ativo and len(buffers)>j else []
        valores=[float(x[1])*fatores[j-3] for x in b] if b else []
        estado[nome]=valores[-1] if valores else None
        estado['serie_'+nome]=valores
    return estado

OraculumHtmlApi.obter_estado=_alt29a_obter_estado




# ALT29B - corrige salvamento, leitura e uso das tags termicas na API HTML.
_alt29b_obter_configuracao_original = OraculumHtmlApi.obter_configuracao
_alt29b_salvar_configuracao_original = OraculumHtmlApi.salvar_configuracao
_alt29b_iniciar_original = OraculumHtmlApi.iniciar


def _alt29b_obter_configuracao(self, *args, **kwargs):
    resposta = _alt29b_obter_configuracao_original(self, *args, **kwargs)
    if isinstance(resposta, dict) and isinstance(resposta.get("configuracao"), dict):
        configuracao = dict(resposta["configuracao"])
        resposta = dict(resposta)
        resposta["configuracao"] = configuracao
    elif isinstance(resposta, dict):
        configuracao = dict(resposta)
        resposta = configuracao
    else:
        configuracao = dict(config_html)
        resposta = configuracao

    configuracao["tags"] = list(config_html.get("tags", []))[:3]
    configuracao["temperatura_programada_tag"] = str(config_html.get("temperatura_programada_tag", "") or "")
    configuracao["temperatura_lida_1_tag"] = str(config_html.get("temperatura_lida_1_tag", "") or "")
    configuracao["temperatura_lida_2_tag"] = str(config_html.get("temperatura_lida_2_tag", "") or "")
    return resposta


def _alt29b_salvar_configuracao(self, dados):
    dados = dict(dados or {})
    tags_pressao = list(dados.get("tags") or [])[:3]
    if len(tags_pressao) != 3 or not all(str(tag or "").strip() for tag in tags_pressao):
        return {"sucesso": False, "mensagem": "Informe os tres sinais de pressao."}

    temperaturas = [
        str(dados.get("temperatura_programada_tag", "") or "").strip(),
        str(dados.get("temperatura_lida_1_tag", "") or "").strip(),
        str(dados.get("temperatura_lida_2_tag", "") or "").strip(),
    ]

    try:
        for tag in tags_pressao:
            parse_schneider_tag(str(tag).strip())
        for tag in temperaturas:
            if tag:
                parse_schneider_tag(tag)
    except Exception as exc:
        return {"sucesso": False, "mensagem": f"Tag invalida: {exc}"}

    dados_base = dict(dados)
    dados_base["tags"] = [str(tag).strip() for tag in tags_pressao]
    dados_base.pop("temperatura_programada_tag", None)
    dados_base.pop("temperatura_lida_1_tag", None)
    dados_base.pop("temperatura_lida_2_tag", None)

    resposta = _alt29b_salvar_configuracao_original(self, dados_base)
    sucesso = not isinstance(resposta, dict) or resposta.get("sucesso", True)
    if not sucesso:
        return resposta

    config_html["tags"] = list(dados_base["tags"])
    config_html["temperatura_programada_tag"] = temperaturas[0]
    config_html["temperatura_lida_1_tag"] = temperaturas[1]
    config_html["temperatura_lida_2_tag"] = temperaturas[2]

    parcial = 0 < sum(bool(tag) for tag in temperaturas) < 3
    mensagem = "Configuracao salva."
    if parcial:
        mensagem = "Configuracao salva. Configuracao de temperatura incompleta; aquisicao termica desabilitada."

    return {
        "sucesso": True,
        "mensagem": mensagem,
        "configuracao": _alt29b_obter_configuracao(self),
    }


def _alt29b_iniciar(self, *args, **kwargs):
    global tags_ativas, buffers
    if rodando:
        return {"sucesso": False, "mensagem": "A monitoracao ja esta em execucao."}

    tags_ativas = montar_tags_ativas_html()
    buffers = [[] for _ in tags_ativas]
    imprimir_diagnostico_tags_alt29b(tags_ativas)

    # A implementacao original deve usar config_html['tags']; durante a chamada,
    # disponibilizamos a lista efetiva e depois restauramos a fonte de pressao.
    tags_pressao = list(config_html.get("tags", []))[:3]
    config_html["tags"] = list(tags_ativas)
    try:
        resposta = _alt29b_iniciar_original(self, *args, **kwargs)
    finally:
        config_html["tags"] = tags_pressao
    return resposta


OraculumHtmlApi.obter_configuracao = _alt29b_obter_configuracao
OraculumHtmlApi.salvar_configuracao = _alt29b_salvar_configuracao
OraculumHtmlApi.iniciar = _alt29b_iniciar




# ALT30A - expõe limites térmicos calculados pelo backend ao HTML.
_alt30a_obter_estado_anterior = OraculumHtmlApi.obter_estado
_alt30a_detalhes_anterior = OraculumHtmlApi.obter_detalhes_ciclo


def _alt30a_obter_estado(self, *args, **kwargs):
    estado = _alt30a_obter_estado_anterior(self, *args, **kwargs)
    tolerancia = _alt30a_tolerancia_do_form()
    limites = calcular_limites_termicos(buffers, tolerancia)
    estado["tolerancia_temperatura"] = tolerancia
    estado["limite_temperatura_minimo"] = limites["limites_minimos"][-1] if limites["limites_minimos"] else None
    estado["limite_temperatura_maximo"] = limites["limites_maximos"][-1] if limites["limites_maximos"] else None
    estado["serie_limite_temperatura_minimo"] = list(limites["limites_minimos"])
    estado["serie_limite_temperatura_maximo"] = list(limites["limites_maximos"])
    estado["pontos_temperatura_lida_1_fora_limites"] = list(limites["pontos_lida_1"])
    estado["pontos_temperatura_lida_2_fora_limites"] = list(limites["pontos_lida_2"])
    return estado


def _alt30a_obter_detalhes(self, arquivo_base):
    resposta = _alt30a_detalhes_anterior(self, arquivo_base)
    if resposta.get("sucesso"):
        with historico_resultados_lock:
            item = next(
                (dict(x) for x in reversed(historico_resultados)
                 if x.get("arquivo_base") == arquivo_base),
                None,
            )
        if item and item.get("resumo_temperatura"):
            resposta["resumo_temperatura"] = dict(item["resumo_temperatura"])
    return resposta


OraculumHtmlApi.obter_estado = _alt30a_obter_estado
OraculumHtmlApi.obter_detalhes_ciclo = _alt30a_obter_detalhes




# ALT30B - garante os padroes termicos no retorno da configuracao.
_alt30b_obter_configuracao_anterior = OraculumHtmlApi.obter_configuracao


def _alt30b_obter_configuracao(self, *args, **kwargs):
    resposta = _alt30b_obter_configuracao_anterior(self, *args, **kwargs)
    if isinstance(resposta, dict) and isinstance(resposta.get("configuracao"), dict):
        configuracao = resposta["configuracao"]
    elif isinstance(resposta, dict):
        configuracao = resposta
    else:
        configuracao = config_html
    configuracao["temperatura_programada_tag"] = str(
        configuracao.get("temperatura_programada_tag") or TEMPERATURA_PROGRAMADA_PADRAO
    )
    configuracao["temperatura_lida_1_tag"] = str(
        configuracao.get("temperatura_lida_1_tag") or TEMPERATURA_LIDA_1_PADRAO
    )
    configuracao["temperatura_lida_2_tag"] = str(
        configuracao.get("temperatura_lida_2_tag") or TEMPERATURA_LIDA_2_PADRAO
    )
    return resposta


OraculumHtmlApi.obter_configuracao = _alt30b_obter_configuracao




# === ALT31A: SELECAO SEGURA DE MAQUINA ===
# Cadastro oficial. O HTML envia apenas o identificador; IP e protocolo sao
# sempre resolvidos e validados pelo backend.
MAQUINAS_DISPONIVEIS = {
    "10552": {"id": "10552", "nome": "Maquina 10552", "ip": "172.25.217.210", "protocolo": "SCHNEIDER", "porta": 502},
    "1041": {"id": "1041", "nome": "Maquina 1041", "ip": "172.25.217.92", "protocolo": "SCHNEIDER", "porta": 502},
    "14441": {"id": "14441", "nome": "Maquina 14441", "ip": "172.25.217.35", "protocolo": "SCHNEIDER", "porta": 502},
}
maquina_ativa_id = None
_alt31a_lock = threading.RLock()


def _alt31a_maquina_ativa():
    with _alt31a_lock:
        item = MAQUINAS_DISPONIVEIS.get(maquina_ativa_id)
        return dict(item) if item else None


def _alt31a_troca_bloqueada():
    # ALT32A: a troca e bloqueada somente durante a monitoracao.
    return bool(rodando)


def _alt31a_listar_maquinas(self):
    return {
        "sucesso": True,
        "maquinas": [dict(v) for v in MAQUINAS_DISPONIVEIS.values()],
        "maquina_ativa": _alt31a_maquina_ativa(),
    }


def _alt31a_selecionar_maquina(self, identificador):
    global maquina_ativa_id
    chave = str(identificador or "").strip()
    with _alt31a_lock:
        if _alt31a_troca_bloqueada():
            return {"sucesso": False, "mensagem": "Pare a monitoracao e aguarde o salvamento antes de trocar de maquina.", "maquina_ativa": _alt31a_maquina_ativa()}
        maquina = MAQUINAS_DISPONIVEIS.get(chave)
        if not maquina:
            return {"sucesso": False, "mensagem": "Selecione uma maquina valida.", "maquina_ativa": _alt31a_maquina_ativa()}
        maquina_ativa_id = chave
        config_html["maquina_id"] = chave
        config_html["ip"] = maquina["ip"]
        config_html["protocolo"] = maquina["protocolo"]
        config_html["porta"] = maquina["porta"]
    set_status(f'{maquina["nome"]} selecionada. Pronta para iniciar.')
    return {"sucesso": True, "mensagem": f'{maquina["nome"]} selecionada.', "maquina_ativa": dict(maquina), "configuracao": dict(config_html)}


def _alt31a_obter_maquina_ativa(self):
    maquina = _alt31a_maquina_ativa()
    return {"sucesso": bool(maquina), "maquina_ativa": maquina, "troca_bloqueada": _alt31a_troca_bloqueada()}


_alt31a_iniciar_anterior = OraculumHtmlApi.iniciar
def _alt31a_iniciar(self, *args, **kwargs):
    maquina = _alt31a_maquina_ativa()
    if not maquina:
        return {"sucesso": False, "mensagem": "Selecione a maquina antes de iniciar a monitoracao."}
    # Reaplica dados oficiais imediatamente antes da conexao.
    config_html["maquina_id"] = maquina["id"]
    config_html["ip"] = maquina["ip"]
    config_html["protocolo"] = maquina["protocolo"]
    config_html["porta"] = maquina["porta"]
    return _alt31a_iniciar_anterior(self, *args, **kwargs)


_alt31a_salvar_config_anterior = OraculumHtmlApi.salvar_configuracao
def _alt31a_salvar_configuracao(self, dados):
    dados = dict(dados or {})
    maquina = _alt31a_maquina_ativa()
    if maquina:
        # Campos de comunicacao enviados pelo navegador nao sao fonte oficial.
        dados["maquina_id"] = maquina["id"]
        dados["ip"] = maquina["ip"]
        dados["protocolo"] = maquina["protocolo"]
        dados["porta"] = maquina["porta"]
    resposta = _alt31a_salvar_config_anterior(self, dados)
    if maquina:
        config_html.update({"maquina_id": maquina["id"], "ip": maquina["ip"], "protocolo": maquina["protocolo"], "porta": maquina["porta"]})
    return resposta


_alt31a_obter_config_anterior = OraculumHtmlApi.obter_configuracao
def _alt31a_obter_configuracao(self, *args, **kwargs):
    resposta = _alt31a_obter_config_anterior(self, *args, **kwargs)
    maquina = _alt31a_maquina_ativa()
    alvo = resposta.get("configuracao") if isinstance(resposta, dict) and isinstance(resposta.get("configuracao"), dict) else resposta
    if isinstance(alvo, dict):
        alvo["maquina_id"] = maquina["id"] if maquina else None
        if maquina:
            alvo.update({"ip": maquina["ip"], "protocolo": maquina["protocolo"], "porta": maquina["porta"]})
    return resposta


_alt31a_registrar_resultado_anterior = _registrar_resultado_ciclo
def _registrar_resultado_ciclo(resultado):
    item = dict(resultado or {})
    maquina = _alt31a_maquina_ativa()
    if maquina:
        item["maquina_id"] = maquina["id"]
        item["maquina_nome"] = maquina["nome"]
        item["maquina_ip"] = maquina["ip"]
        item["maquina_protocolo"] = maquina["protocolo"]
    return _alt31a_registrar_resultado_anterior(item)


_alt31a_estado_anterior = OraculumHtmlApi.obter_estado
def _alt31a_obter_estado(self, *args, **kwargs):
    estado = _alt31a_estado_anterior(self, *args, **kwargs)
    maquina = _alt31a_maquina_ativa()
    estado["maquinas_disponiveis"] = [dict(v) for v in MAQUINAS_DISPONIVEIS.values()]
    estado["maquina_ativa"] = maquina
    estado["maquina_selecionada"] = bool(maquina)
    estado["troca_maquina_bloqueada"] = _alt31a_troca_bloqueada()
    estado["estado_comunicacao"] = (
        "monitorando" if estado.get("rodando") and estado.get("conectado")
        else "falha" if estado.get("rodando")
        else "conectada" if estado.get("conectado")
        else "desconectada" if maquina
        else "nao_selecionada"
    )
    return estado


_alt31a_detalhes_anterior = OraculumHtmlApi.obter_detalhes_ciclo
def _alt31a_obter_detalhes(self, arquivo_base):
    resposta = _alt31a_detalhes_anterior(self, arquivo_base)
    if resposta.get("sucesso"):
        with historico_resultados_lock:
            item = next((dict(x) for x in reversed(historico_resultados) if x.get("arquivo_base") == arquivo_base), None)
        if item:
            for chave in ("maquina_id", "maquina_nome", "maquina_ip", "maquina_protocolo"):
                resposta[chave] = item.get(chave)
    return resposta


OraculumHtmlApi.listar_maquinas = _alt31a_listar_maquinas
OraculumHtmlApi.selecionar_maquina = _alt31a_selecionar_maquina
OraculumHtmlApi.obter_maquina_ativa = _alt31a_obter_maquina_ativa
OraculumHtmlApi.iniciar = _alt31a_iniciar
OraculumHtmlApi.salvar_configuracao = _alt31a_salvar_configuracao
OraculumHtmlApi.obter_configuracao = _alt31a_obter_configuracao
OraculumHtmlApi.obter_estado = _alt31a_obter_estado
OraculumHtmlApi.obter_detalhes_ciclo = _alt31a_obter_detalhes
# === FIM ALT31A ===




# === ALT31B: SINCRONIZACAO DA CONFIGURACAO ===
# Padroniza todos os retornos de configuracao enviados ao pywebview.
# Esta camada e instalada depois da ALT31A para preservar a selecao segura
# da maquina e manter IP, protocolo e porta sob autoridade do backend.

def _alt31b_copia_configuracao():
    """Cria uma fotografia independente e completa da configuracao vigente."""
    configuracao = dict(config_html)
    configuracao["tags"] = list(config_html.get("tags") or [])

    maquina = _alt31a_maquina_ativa()
    configuracao["maquina_id"] = maquina["id"] if maquina else None

    if maquina:
        configuracao["ip"] = maquina["ip"]
        configuracao["protocolo"] = maquina["protocolo"]
        configuracao["porta"] = maquina["porta"]

    # Garante que todos os campos esperados pelo HTML existam na resposta.
    configuracao.setdefault("ip", "")
    configuracao.setdefault("protocolo", PROTOCOLO_PADRAO)
    configuracao.setdefault("porta", 502)
    configuracao.setdefault("offset_modbus", 0)
    configuracao.setdefault("trigger", TRIGGER_PADRAO)
    configuracao.setdefault("flag_monitor_status", FLAG_MONITOR_STATUS_PADRAO)
    configuracao.setdefault("tipo_trigger", TIPO_TRIGGER_PADRAO)
    configuracao.setdefault("trigger_habilitado", True)
    configuracao.setdefault("monitorar_pressao_zero", False)
    configuracao.setdefault(
        "tags",
        [PRESSAO_LIDA_PADRAO, PRESSAO_PROGRAMADA_PADRAO, INERCIA_PRESSAO_PADRAO],
    )
    configuracao.setdefault(
        "temperatura_programada_tag", TEMPERATURA_PROGRAMADA_PADRAO
    )
    configuracao.setdefault("temperatura_lida_1_tag", TEMPERATURA_LIDA_1_PADRAO)
    configuracao.setdefault("temperatura_lida_2_tag", TEMPERATURA_LIDA_2_PADRAO)
    return configuracao


def _alt31b_resposta_configuracao(mensagem, sucesso=True, maquina=None):
    """Monta o unico formato de retorno usado pela configuracao HTML."""
    maquina = dict(maquina) if maquina else _alt31a_maquina_ativa()
    return {
        "sucesso": bool(sucesso),
        "mensagem": str(mensagem),
        "configuracao": _alt31b_copia_configuracao(),
        "maquina_ativa": dict(maquina) if maquina else None,
    }


_alt31b_obter_configuracao_anterior = OraculumHtmlApi.obter_configuracao

def _alt31b_obter_configuracao(self, *args, **kwargs):
    # Executa a cadeia anterior para preservar inicializacoes e valores-padrao
    # das alteracoes 29B, 30B e 31A. A forma antiga da resposta nao e propagada.
    try:
        _alt31b_obter_configuracao_anterior(self, *args, **kwargs)
    except Exception as exc:
        print(f"[AVISO ALT31B] Falha na cadeia anterior de configuracao: {exc}")

    maquina = _alt31a_maquina_ativa()
    if maquina:
        config_html.update({
            "maquina_id": maquina["id"],
            "ip": maquina["ip"],
            "protocolo": maquina["protocolo"],
            "porta": maquina["porta"],
        })

    return _alt31b_resposta_configuracao("Configuracao carregada.")


_alt31b_selecionar_maquina_anterior = OraculumHtmlApi.selecionar_maquina

def _alt31b_selecionar_maquina(self, identificador):
    resposta = _alt31b_selecionar_maquina_anterior(self, identificador)
    if not isinstance(resposta, dict):
        return _alt31b_resposta_configuracao(
            "Resposta invalida ao selecionar a maquina.", sucesso=False
        )

    if not resposta.get("sucesso"):
        # Mantem a selecao valida anterior e tambem devolve sua configuracao.
        retorno = _alt31b_resposta_configuracao(
            resposta.get("mensagem", "Nao foi possivel selecionar a maquina."),
            sucesso=False,
            maquina=resposta.get("maquina_ativa"),
        )
        return retorno

    maquina = _alt31a_maquina_ativa()
    if not maquina:
        return _alt31b_resposta_configuracao(
            "A maquina nao permaneceu selecionada no backend.", sucesso=False
        )

    # Somente os quatro campos oficiais da maquina sao alterados.
    config_html.update({
        "maquina_id": maquina["id"],
        "ip": maquina["ip"],
        "protocolo": maquina["protocolo"],
        "porta": maquina["porta"],
    })
    return _alt31b_resposta_configuracao(
        resposta.get("mensagem", f'{maquina["nome"]} selecionada.'),
        maquina=maquina,
    )


_alt31b_salvar_configuracao_anterior = OraculumHtmlApi.salvar_configuracao

def _alt31b_salvar_configuracao(self, dados):
    maquina = _alt31a_maquina_ativa()
    dados_seguros = dict(dados or {})

    if maquina:
        # Ignora qualquer tentativa do navegador de substituir a comunicacao.
        dados_seguros.update({
            "maquina_id": maquina["id"],
            "ip": maquina["ip"],
            "protocolo": maquina["protocolo"],
            "porta": maquina["porta"],
        })

    resposta = _alt31b_salvar_configuracao_anterior(self, dados_seguros)
    sucesso = bool(isinstance(resposta, dict) and resposta.get("sucesso"))
    mensagem = (
        resposta.get("mensagem", "Configuracao salva.")
        if isinstance(resposta, dict)
        else "Resposta invalida ao salvar a configuracao."
    )

    # Reaplica os dados oficiais mesmo se a cadeia anterior tiver recebido
    # valores diferentes. Os demais campos de config_html sao preservados.
    if maquina:
        config_html.update({
            "maquina_id": maquina["id"],
            "ip": maquina["ip"],
            "protocolo": maquina["protocolo"],
            "porta": maquina["porta"],
        })

    return _alt31b_resposta_configuracao(
        mensagem,
        sucesso=sucesso,
        maquina=maquina,
    )


OraculumHtmlApi.obter_configuracao = _alt31b_obter_configuracao
OraculumHtmlApi.selecionar_maquina = _alt31b_selecionar_maquina
OraculumHtmlApi.salvar_configuracao = _alt31b_salvar_configuracao
# === FIM ALT31B ===




# === ALT32A APLICADA AUTOMATICAMENTE ===
# Fotografia da maquina do ciclo, usada pelo salvamento e pelo historico.
_alt32a_maquina_ciclo = None
_alt32a_lock = threading.RLock()


def _alt32a_fotografar_maquina():
    maquina = _alt31a_maquina_ativa()
    return dict(maquina) if maquina else None


def _alt32a_id_seguro(valor):
    texto = re.sub(r"[^0-9A-Za-z_-]+", "_", str(valor or "").strip())
    return texto.strip("_") or "nao_identificada"


# Captura a maquina no inicio. Uma troca posterior nao altera a origem do ciclo.
_alt32a_iniciar_anterior = OraculumHtmlApi.iniciar
def _alt32a_iniciar(self, *args, **kwargs):
    global _alt32a_maquina_ciclo
    resposta = _alt32a_iniciar_anterior(self, *args, **kwargs)
    if isinstance(resposta, dict) and resposta.get("sucesso") and rodando:
        with _alt32a_lock:
            _alt32a_maquina_ciclo = _alt32a_fotografar_maquina()
    return resposta


# Finaliza a aquisicao, aguarda a thread sair e limpa estados da comunicacao.
_alt32a_parar_anterior = OraculumHtmlApi.parar
def _alt32a_parar(self, *args, **kwargs):
    global rodando, pausado, ultima_comunicacao_ok
    global ultimo_trigger_lido, ultimo_monitor_status
    resposta = _alt32a_parar_anterior(self, *args, **kwargs)
    rodando = False
    pausado = False
    thread = thread_aquisicao
    if thread and thread.is_alive() and thread is not threading.current_thread():
        thread.join(timeout=max(1.0, INTERVALO_AQUISICAO_FIXO * 20))
    ultima_comunicacao_ok = 0.0
    ultimo_trigger_lido = 0
    ultimo_monitor_status = STATUS_CONCLUIDO
    if isinstance(resposta, dict):
        resposta["troca_maquina_bloqueada"] = False
        resposta["maquina_ativa"] = _alt31a_maquina_ativa()
    return resposta


# Enriquece o historico com a fotografia da maquina do ciclo.
_alt32a_registrar_anterior = _registrar_resultado_ciclo
def _registrar_resultado_ciclo(resultado):
    item = dict(resultado or {})
    with _alt32a_lock:
        maquina = dict(_alt32a_maquina_ciclo) if _alt32a_maquina_ciclo else _alt32a_fotografar_maquina()
    if maquina:
        item.update({
            "maquina_id": maquina.get("id"),
            "maquina_nome": maquina.get("nome"),
            "maquina_ip": maquina.get("ip"),
            "maquina_protocolo": maquina.get("protocolo"),
        })
    return _alt32a_registrar_anterior(item)


# ALT32B: a maquina acompanha explicitamente o ciclo ate o fim do salvamento.
# O snapshot e armazenado no snapshot_form para preservar compatibilidade com a fila existente.
def _alt32b_extrair_maquina(snapshot_form):
    for item in snapshot_form or []:
        if isinstance(item, dict) and item.get("__oraculum_meta__") == "ALT32B":
            m = item.get("maquina")
            return dict(m) if isinstance(m, dict) else None
    return None

_alt32b_finalizar_anterior = finalizar_ciclo_atual
def finalizar_ciclo_atual(numero, motivo):
    # Replica a finalizacao estavel e inclui a fotografia da maquina no pacote do ciclo.
    global tempos_sob_pressao, tempos_ventilacao
    snapshot = [list(b) for b in buffers]
    snapshot_tags = list(tags_ativas)
    snapshot_form = [dict(item) for item in ultimo_vetor_m340_descrito]
    with _alt32a_lock:
        maquina = dict(_alt32a_maquina_ciclo) if _alt32a_maquina_ciclo else _alt32a_fotografar_maquina()
    snapshot_form.append({"__oraculum_meta__": "ALT32B", "maquina": maquina})
    if not any(snapshot):
        print(f"[AVISO FINALIZACAO] Ciclo {numero} sem dados. Motivo: {motivo}")
        return False
    try:
        tempos_sob_pressao = obter_vetor_tempos_sob_pressao(snapshot)
        tempos_ventilacao = obter_vetor_tempos_ventilacao(snapshot)
        atualizar_label_tempos_sob_pressao()
        atualizar_label_tempos_ventilacao()
    except Exception as exc:
        print(f"[ERRO CALCULO TEMPOS] {type(exc).__name__}: {exc}")
        traceback.print_exc()
    fila_salvamento.put((snapshot, snapshot_tags, numero, snapshot_form))
    atualizar_flag_monitor_status(STATUS_CONCLUIDO)
    print(f"[ALT32B] Ciclo {numero} enfileirado para maquina {(maquina or {}).get('id','nao identificada')}.")
    return True

# Contexto exclusivo da thread de salvamento, usado pela geracao do PNG.
_alt32b_contexto = threading.local()
_alt32b_png_anterior = salvar_png_snapshot
def salvar_png_snapshot(caminho_png, snapshot_buffers, snapshot_tags):
    resultado = _alt32b_png_anterior(caminho_png, snapshot_buffers, snapshot_tags)
    maquina = getattr(_alt32b_contexto, 'maquina', None) or {}
    numero = getattr(_alt32b_contexto, 'numero_ciclo', 0)
    # Acrescenta a identificacao visual ao PNG final sem alterar os graficos.
    try:
        from matplotlib import image as mpimg
        imagem = mpimg.imread(caminho_png)
        figura = Figure(figsize=(12, 10), dpi=150)
        eixo = figura.add_axes([0, 0, 1, 0.94])
        eixo.imshow(imagem)
        eixo.axis('off')
        figura.suptitle(
            f"Oraculum | Máquina {maquina.get('id','não identificada')} | Ciclo {int(numero):04d}",
            fontsize=14, fontweight='bold', y=0.985
        )
        figura.savefig(caminho_png, bbox_inches='tight', pad_inches=0.08)
    except Exception as exc:
        print(f"[AVISO ALT32B PNG] Identificacao visual nao aplicada: {exc}")
    return resultado

_alt32b_salvar_anterior = salvar_ciclo_automatico
def salvar_ciclo_automatico(snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form=None):
    """ALT32C: CSV e PNG ja nascem com o nome definitivo."""
    maquina = _alt32b_extrair_maquina(snapshot_form) or _alt32a_fotografar_maquina() or {}
    _alt32b_contexto.maquina = maquina
    _alt32b_contexto.numero_ciclo = numero_ciclo
    try:
        return _alt32b_salvar_anterior(snapshot_buffers, snapshot_tags, numero_ciclo, snapshot_form)
    finally:
        _alt32b_contexto.maquina = None
        _alt32b_contexto.numero_ciclo = None

# Compatibilidade dos detalhes com arquivos antigos e novos.
def _alt32b_validar_base(nome_base):
    nome=os.path.basename(str(nome_base or '').strip())
    if nome != str(nome_base or '').strip(): raise ValueError('Arquivo-base invalido.')
    if not re.match(r'^(?:Maquina_[0-9A-Za-z_-]+_)?ciclo_\d+_\d{8}_\d{6}$',nome):
        raise ValueError('O arquivo-base nao pertence a um ciclo do Oraculum.')
    return nome
_alt27a_validar_base = _alt32b_validar_base

_alt32b_detalhes_anterior = OraculumHtmlApi.obter_detalhes_ciclo
def _alt32b_obter_detalhes(self, arquivo_base):
    resposta=_alt32b_detalhes_anterior(self,arquivo_base)
    if resposta.get('sucesso'):
        with historico_resultados_lock:
            item=next((dict(x) for x in reversed(historico_resultados) if x.get('arquivo_base')==arquivo_base),None)
        if item:
            for chave in ('maquina_id','maquina_nome','maquina_ip','maquina_protocolo'):
                resposta[chave]=item.get(chave)
    return resposta

# === ALT32B: IDENTIFICACAO CONSOLIDADA DA MAQUINA ===
OraculumHtmlApi.obter_detalhes_ciclo = _alt32b_obter_detalhes
# === FIM ALT32B ===
OraculumHtmlApi.iniciar = _alt32a_iniciar
OraculumHtmlApi.parar = _alt32a_parar
# === FIM ALT32A ===


def localizar_html():
    pasta = os.path.dirname(os.path.abspath(__file__))
    for caminho in (os.path.join(pasta, "index.html"), os.path.join(pasta, "interface", "index.html")):
        if os.path.isfile(caminho):
            return caminho
    raise FileNotFoundError("index.html não encontrado ao lado do app.py nem na pasta interface.")


def fechar_html(*_args):
    global fechando, rodando
    fechando = True
    rodando = False
    try:
        root.destroy()
    except Exception:
        pass


def main():
    global thread_salvamento, modo_html_ativo
    if webview is None:
        raise RuntimeError("pywebview não instalado. Execute: python -m pip install pywebview")

    modo_html_ativo = True

    # Reaproveita a inicialização estável para manter compatibilidade interna,
    # mas oculta a janela Tkinter antes de abrir o HTML.
    criar_interface()
    root.withdraw()

    thread_salvamento = threading.Thread(target=processar_fila_salvamento, daemon=True)
    thread_salvamento.start()

    caminho_html = localizar_html()
    print(f"[INFO] Abrindo interface HTML: {caminho_html}")

    janela = webview.create_window(
        "Oraculum - Osciloscópio Industrial",
        caminho_html,
        js_api=OraculumHtmlApi(),
        width=1400,
        height=900,
        min_size=(1100, 700),
    )
    janela.events.closed += fechar_html
    webview.start(debug=False)


if __name__ == "__main__":
    main()