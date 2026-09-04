import socket
import struct
import random


# ==========================================================
# CONFIGURAÇÕES MODBUS TCP
# ==========================================================

PORT = 502
UNIT_ID = 1
TIMEOUT = 2.0


# ==========================================================
# UTILITÁRIOS
# ==========================================================

def parse_mw_register(register):
    """
    Converte endereço MW para número inteiro de registrador.

    Aceita:
        3004
        "3004"
        "MW3004"
        "%MW3004"

    Retorna:
        3004
    """

    if register is None:
        raise ValueError("Registrador MW vazio.")

    texto = str(register).strip().upper()
    texto = texto.replace("%", "")
    texto = texto.replace("MW", "")
    texto = texto.strip()

    if not texto:
        raise ValueError("Registrador MW inválido.")

    return int(texto)


def _modbus_tcp_request(ip, function_code, payload):
    """
    Envia uma requisição Modbus TCP básica.

    MBAP:
        Transaction ID
        Protocol ID
        Length
        Unit ID

    PDU:
        Function Code
        Payload
    """

    transaction_id = random.randint(0, 65535)

    pdu = struct.pack(">B", function_code) + payload

    mbap = struct.pack(
        ">HHHB",
        transaction_id,
        0,
        len(pdu) + 1,
        UNIT_ID
    )

    pacote = mbap + pdu

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(TIMEOUT)
        s.connect((ip, PORT))
        s.sendall(pacote)
        resposta = s.recv(4096)

    if len(resposta) < 8:
        raise Exception("Resposta Modbus TCP incompleta.")

    resposta_tid = struct.unpack(">H", resposta[0:2])[0]

    if resposta_tid != transaction_id:
        raise Exception(
            f"Transaction ID diferente. Enviado={transaction_id}, recebido={resposta_tid}"
        )

    resposta_function_code = resposta[7]

    if resposta_function_code & 0x80:
        if len(resposta) >= 9:
            exception_code = resposta[8]
        else:
            exception_code = "desconhecido"

        raise Exception(
            f"Erro Modbus. Function={function_code}, Exception={exception_code}"
        )

    if resposta_function_code != function_code:
        raise Exception(
            f"Function code inesperado. Esperado={function_code}, recebido={resposta_function_code}"
        )

    return resposta


def _uint16_to_int16(valor):
    """
    Converte UINT16 para INT16 com sinal.
    """

    valor = int(valor) & 0xFFFF

    if valor >= 0x8000:
        return valor - 0x10000

    return valor


def _words_to_real(word_hi, word_lo):
    """
    Converte dois registradores para REAL 32 bits.

    Padrão usado:
        word_hi primeiro
        word_lo depois

    Se algum equipamento estiver com ordem invertida, ajustar aqui.
    """

    raw = struct.pack(">HH", int(word_hi) & 0xFFFF, int(word_lo) & 0xFFFF)
    return struct.unpack(">f", raw)[0]


def _words_to_dint(word_hi, word_lo):
    """
    Converte dois registradores para DINT 32 bits com sinal.
    """

    raw = struct.pack(">HH", int(word_hi) & 0xFFFF, int(word_lo) & 0xFFFF)
    return struct.unpack(">i", raw)[0]


def _words_to_udint(word_hi, word_lo):
    """
    Converte dois registradores para UDINT 32 bits sem sinal.
    """

    raw = struct.pack(">HH", int(word_hi) & 0xFFFF, int(word_lo) & 0xFFFF)
    return struct.unpack(">I", raw)[0]


# ==========================================================
# LEITURA MW INDIVIDUAL
# ==========================================================

def read_mw(ip, register, tipo="INT", bit=None):
    """
    Lê um registrador MW Schneider/M340 via Modbus TCP.

    Usa Function 03 - Read Holding Registers.

    Parâmetros:
        ip:
            IP do CLP.

        register:
            Registrador MW.
            Aceita:
                3004
                "3004"
                "MW3004"
                "%MW3004"

        tipo:
            "INT"
            "UINT"
            "REAL"
            "DINT"
            "UDINT"
            "BOOL"

        bit:
            Para leitura booleana de bit dentro da word.
            Exemplo:
                read_mw(ip, 3000, tipo="BOOL", bit=0)

    Retorno:
        Valor convertido conforme o tipo.
    """

    registro = parse_mw_register(register)
    tipo = str(tipo).strip().upper()

    if tipo in ["REAL", "DINT", "UDINT"]:
        quantidade = 2
    else:
        quantidade = 1

    valores = read_mw_block(ip, registro, quantidade)

    if not valores:
        raise Exception("Nenhum valor retornado na leitura MW.")

    valor = valores[0]

    if tipo == "BOOL":
        if bit is None:
            return bool(valor)

        bit = int(bit)

        if bit < 0 or bit > 15:
            raise ValueError("Bit inválido. Use bit entre 0 e 15.")

        return bool((valor >> bit) & 1)

    if tipo == "UINT":
        return int(valor) & 0xFFFF

    if tipo == "INT":
        return _uint16_to_int16(valor)

    if tipo == "REAL":
        return _words_to_real(valores[0], valores[1])

    if tipo == "DINT":
        return _words_to_dint(valores[0], valores[1])

    if tipo == "UDINT":
        return _words_to_udint(valores[0], valores[1])

    # Padrão de segurança
    return _uint16_to_int16(valor)


# ==========================================================
# LEITURA DE BLOCO / VETOR MW
# ==========================================================

def read_mw_block(ip, start_register, quantidade):
    """
    Lê um bloco contínuo de registradores MW Schneider/M340 via Modbus TCP.

    Usa Function 03 - Read Holding Registers.

    Exemplo:
        read_mw_block("172.25.217.210", 5000, 10)

    Lê:
        %MW5000 até %MW5009

    Retorno:
        Lista de inteiros UINT16.
    """

    registro_inicial = parse_mw_register(start_register)
    quantidade = int(quantidade)

    if quantidade <= 0:
        raise ValueError("Quantidade de registradores inválida.")

    if quantidade > 125:
        raise ValueError(
            "Quantidade máxima por leitura Modbus FC03 é 125 registradores. "
            "Use read_mw_block_auto para ler vetores maiores."
        )

    payload = struct.pack(
        ">HH",
        registro_inicial,
        quantidade
    )

    resposta = _modbus_tcp_request(
        ip=ip,
        function_code=3,
        payload=payload
    )

    if len(resposta) < 9:
        raise Exception("Resposta Modbus incompleta ao ler bloco MW.")

    byte_count = resposta[8]
    esperado = quantidade * 2

    if byte_count != esperado:
        raise Exception(
            f"Quantidade de bytes inesperada. Esperado={esperado}, recebido={byte_count}."
        )

    dados = resposta[9:9 + byte_count]

    if len(dados) != esperado:
        raise Exception(
            f"Tamanho de dados inválido. Esperado={esperado}, recebido={len(dados)}."
        )

    valores = []

    for i in range(0, len(dados), 2):
        valor = struct.unpack(">H", dados[i:i + 2])[0]
        valores.append(valor)

    return valores


def read_mw_block_auto(ip, start_register, quantidade, bloco_max=100):
    """
    Lê um vetor MW grande em blocos menores.

    Recomendado para vetor de parâmetros de processo.

    Exemplo:
        read_mw_block_auto("172.25.217.210", "%MW5000", 300)

    Lê:
        %MW5000 até %MW5299

    Retorno:
        Lista única com todos os valores UINT16.
    """

    registro_atual = parse_mw_register(start_register)
    quantidade = int(quantidade)
    bloco_max = int(bloco_max)

    if quantidade <= 0:
        raise ValueError("Quantidade de registradores inválida.")

    if bloco_max <= 0:
        raise ValueError("Tamanho do bloco inválido.")

    if bloco_max > 125:
        bloco_max = 125

    valores_total = []
    restante = quantidade

    while restante > 0:
        qtd_bloco = min(bloco_max, restante)

        bloco = read_mw_block(
            ip=ip,
            start_register=registro_atual,
            quantidade=qtd_bloco
        )

        valores_total.extend(bloco)

        registro_atual += qtd_bloco
        restante -= qtd_bloco

    return valores_total


# ==========================================================
# ESCRITA MW INDIVIDUAL
# ==========================================================

def write_mw(ip, register, value):
    """
    Escreve um valor inteiro em um registrador MW Schneider/M340 via Modbus TCP.

    Usa Function 06 - Write Single Register.

    Exemplo:
        write_mw("172.25.217.210", "%MW3004", 1)
    """

    registro = parse_mw_register(register)
    valor = int(value) & 0xFFFF

    payload = struct.pack(
        ">HH",
        registro,
        valor
    )

    resposta = _modbus_tcp_request(
        ip=ip,
        function_code=6,
        payload=payload
    )

    if len(resposta) < 12:
        raise Exception("Resposta Modbus incompleta ao escrever MW.")

    resposta_registro = struct.unpack(">H", resposta[8:10])[0]
    resposta_valor = struct.unpack(">H", resposta[10:12])[0]

    if resposta_registro != registro:
        raise Exception(
            f"Registrador de resposta diferente. Enviado={registro}, recebido={resposta_registro}"
        )

    if resposta_valor != valor:
        raise Exception(
            f"Valor de resposta diferente. Enviado={valor}, recebido={resposta_valor}"
        )

    return True


# ==========================================================
# ALIAS OPCIONAL PARA COMPATIBILIDADE
# ==========================================================

def write_mw_schneider(ip, register, value):
    """
    Alias para manter compatibilidade caso algum arquivo use este nome.
    """

    return write_mw(ip, register, value)


# ==========================================================
# TESTE MANUAL
# ==========================================================

if __name__ == "__main__":
    ip_teste = "172.25.217.210"

    try:
        print("Teste leitura MW individual:")
        valor = read_mw(ip_teste, "%MW3004", tipo="UINT")
        print(f"%MW3004 = {valor}")

        print("\nTeste leitura bloco:")
        vetor = read_mw_block(ip_teste, "%MW3000", 5)

        for i, valor in enumerate(vetor):
            print(f"%MW{3000 + i} = {valor}")

    except Exception as e:
        print(f"Erro no teste Modbus: {e}")