# clp_comm_schneider.py
# Backend de leitura Modbus TCP
# Compatível com Schneider M340
# Interface compatível com app.py (osciloscópio)

import time
import socket
import struct
import random

# ==========================================================
# CONSTANTES MODBUS
# ==========================================================
PORT = 502
UNIT_ID = 1
TIMEOUT = 2.0


# ==========================================================
# FUNÇÃO MODBUS BÁSICA
# ==========================================================
def read_mw(ip, register, tipo="INT", bit=None):
    """
    Lê %MW via Modbus TCP.

    tipo:
      - INT
      - REAL
      - BOOL (necessita bit)

    BOOL retorna True/False
    INT / REAL retornam número
    """

    tid = random.randint(0, 65535)
    count = 2 if tipo.upper() == "REAL" else 1

    # PDU - Function 03
    pdu = struct.pack(">BHH", 3, register, count)

    # MBAP
    mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, UNIT_ID)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)

    try:
        sock.connect((ip, PORT))
        sock.sendall(mbap + pdu)
        resp = sock.recv(256)

        # Dados começam após MBAP + FC + bytecount
        data = resp[9:]

        if tipo.upper() == "BOOL":
            word = struct.unpack(">H", data[:2])[0]
            return bool((word >> bit) & 1)

        if tipo.upper() == "REAL":
            return struct.unpack(">f", data[:4])[0]

        # INT (default)
        return struct.unpack(">h", data[:2])[0]

    finally:
        sock.close()


# ==========================================================
# PARSE DA TAG (string vinda do app.py)
# ==========================================================
def parse_tag(tag):
    """
    Exemplos aceitos:
      MW15030
      MW15030:INT
      MW15030:REAL
      MW15030:BOOL:3
    """

    parts = tag.split(":")
    register = int(parts[0].replace("MW", ""))

    if len(parts) == 1:
        return register, "INT", None

    tipo = parts[1].upper()

    if tipo == "REAL":
        return register, "REAL", None

    if tipo == "BOOL":
        bit = int(parts[2])
        return register, "BOOL", bit

    return register, "INT", None


# ==========================================================
# THREAD DE LEITURA CONTÍNUA (chamada pelo app.py)
# ==========================================================
def leitor_clp(ip, tags, intervalo, buffers, stop_event):
    """
    Interface esperada pelo app.py.

    ip        -> IP do CLP (string)
    tags      -> lista de strings (ex: ["MW15030:REAL"])
    intervalo -> tempo entre leituras
    buffers   -> dict { tag: [] }
    stop_event-> threading.Event
    """
    t0 = time.perf_counter()                 
    
    while not stop_event.is_set():
        t = time.perf_counter() - t0

        for tag in tags:
            try:
                register, tipo, bit = parse_tag(tag)

                if tipo == "BOOL":
                    valor = read_mw(ip, register, tipo="BOOL", bit=bit)
                    valor = 1 if valor else 0   # BOOL → nível lógico
                else:
                    valor = read_mw(ip, register, tipo=tipo)

                timestamp = time.time()
                buffers[tag].append((timestamp, valor))

            except Exception as e:
                print(f"[Schneider] Erro lendo {tag}: {e}")

        time.sleep(intervalo)