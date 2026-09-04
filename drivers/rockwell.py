# drivers/rockwell.py
import time
from pylogix import PLC


# ==========================================================
# CONEXÃO COM CLP ROCKWELL
# ==========================================================
def conectar_clp(ip, slot=0):
    comm = PLC()
    comm.IPAddress = ip
    comm.ProcessorSlot = slot

    try:
        # leitura neutra apenas para validar sessão
        r = comm.GetPLCTime()
        if r.Status != "Success":
            raise Exception(r.Status)

        print(f"[Rockwell] Conectado ao CLP {ip} (slot {slot})")
        return comm

    except Exception as e:
        raise Exception(f"[Rockwell] Falha conexão CLP {ip} (slot {slot}): {e}")


# ==========================================================
# THREAD DE LEITURA CONTÍNUA (CONTRATO IGUAL AO SCHNEIDER)
# ==========================================================
t0 = time.perf_counter()

def leitor_clp(ip, tags, intervalo, buffers, stop_event):
    comm = conectar_clp(ip, slot=0)

    while not stop_event.is_set():
        t = time.perf_counter() - t0

        for tag in tags:
            r = comm.Read(tag)
            if r.Status == "Success":
                buffers[tag].append((t, r.Value))
            else:
                print(f"[Rockwell] Erro lendo {tag}: {r.Status}")

        time.sleep(intervalo)
