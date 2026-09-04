import time
from pylogix import PLC

# ==========================================================
# CONEXÃO COM CLP ROCKWELL
# ==========================================================
def conectar_clp(ip, tag_teste):
    while True:
        try:
            comm = PLC()
            comm.IPAddress = ip
            test = comm.Read(tag_teste)
            if getattr(test, "Status", None) == "Success":
                print(f"Conectado ao CLP {ip}")
                return comm
        except Exception:
            pass

        print("Tentando reconectar ao CLP...")
        time.sleep(1)


# ==========================================================
# THREAD DE LEITURA CONTÍNUA
# ==========================================================
def leitor_clp(ip, tags, intervalo, buffers, stop_event):
    comm = conectar_clp(ip, tags[0])

    while not stop_event.is_set():
        try:
            for tag in tags:
                r = comm.Read(tag)
                if getattr(r, "Status", None) == "Success":
                    buffers[tag].append(r.Value)
                else:
                    print(f"Erro lendo {tag}, reconectando...")
                    try:
                        comm.Close()
                    except:
                        pass
                    comm = conectar_clp(ip, tags[0])
                    break

        except Exception:
            try:
                comm.Close()
            except:
                pass
            comm = conectar_clp(ip, tags[0])

        time.sleep(intervalo)
