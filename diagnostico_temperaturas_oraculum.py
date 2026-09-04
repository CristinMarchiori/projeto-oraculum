"""Diagnóstico somente leitura dos sinais do Oraculum.
Coloque ao lado de modbus_simple.py e execute com o Oraculum fechado.
Não escreve no CLP.
"""
import sys
import traceback

try:
    from modbus_simple import read_mw
except Exception as exc:
    print(f"[ERRO] Não foi possível importar modbus_simple.py: {exc}")
    input("Pressione Enter para fechar...")
    raise SystemExit(1)

IP = "172.25.217.210"
OFFSET = 0

SINAIS = [
    ("Trigger", "MW3000:BOOL:0"),
    ("Pressão lida", "MW413:UINT"),
    ("Pressão programada", "MW3002:UINT"),
    ("Inércia", "MW515:UINT"),
    ("Temperatura programada", "MW409:UINT"),
    ("Temperatura lida 1", "MW410:UINT"),
    ("Temperatura lida 2", "MW411:UINT"),
]


def parse_tag(tag):
    partes = str(tag).strip().upper().replace("%", "").split(":")
    endereco = partes[0]
    if not endereco.startswith("MW") or not endereco[2:].isdigit():
        raise ValueError(f"Endereço inválido: {tag}")
    registro = int(endereco[2:]) + OFFSET
    tipo = partes[1] if len(partes) > 1 and partes[1] else "INT"
    bit = int(partes[2]) if len(partes) > 2 and partes[2] else None
    return registro, tipo, bit


def ler(nome, tag):
    registro, tipo, bit = parse_tag(tag)
    valor = read_mw(IP, registro, tipo=tipo, bit=bit)
    return valor


def main():
    print("=" * 72)
    print("DIAGNÓSTICO SOMENTE LEITURA - ORACULUM")
    print(f"IP: {IP} | Offset: {OFFSET}")
    print("=" * 72)
    resultados = []
    for nome, tag in SINAIS:
        try:
            valor = ler(nome, tag)
            resultados.append((nome, tag, True, valor, ""))
            print(f"[OK]   {nome:<25} {tag:<18} = {valor}")
        except Exception as exc:
            resultados.append((nome, tag, False, None, f"{type(exc).__name__}: {exc}"))
            print(f"[FALHA] {nome:<25} {tag:<18} -> {type(exc).__name__}: {exc}")

    print("-" * 72)
    pressao_ok = all(r[2] for r in resultados[1:4])
    temp_ok = all(r[2] for r in resultados[4:7])
    print(f"Sinais atuais de pressão: {'OK' if pressao_ok else 'FALHA'}")
    print(f"Sinais de temperatura:    {'OK' if temp_ok else 'FALHA'}")
    if pressao_ok and not temp_ok:
        print("Conclusão: a comunicação base funciona, mas ao menos uma tag térmica falhou.")
    elif not pressao_ok:
        print("Conclusão: existe falha também nos sinais atuais; verificar conexão/IP/offset.")
    elif temp_ok:
        print("Conclusão: as três tags térmicas responderam individualmente.")
    print("=" * 72)
    input("Pressione Enter para fechar...")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("Pressione Enter para fechar...")
        sys.exit(1)
