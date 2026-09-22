"""Driver isolado para leitura de tags Rockwell / Allen-Bradley via pylogix."""

from pylogix import PLC


def conectar_rockwell(ip, slot=0):
    """Cria e configura uma conexao Rockwell por IP e slot da CPU."""
    endereco_ip = str(ip or "").strip()
    if not endereco_ip:
        raise ValueError("Informe o IP do CLP Rockwell.")

    try:
        slot_cpu = int(slot)
    except (TypeError, ValueError) as erro:
        raise ValueError(f"Slot Rockwell invalido: {slot}") from erro

    conexao = PLC()
    conexao.IPAddress = endereco_ip
    conexao.ProcessorSlot = slot_cpu
    return conexao


def validar_resposta(resposta, tag):
    """Valida o retorno do pylogix e entrega somente o valor da tag."""
    nome_tag = str(tag or "").strip()
    if resposta is None:
        raise RuntimeError(f"Sem resposta para a tag {nome_tag}.")

    status = getattr(resposta, "Status", None)
    if status != "Success":
        raise RuntimeError(
            f"Falha ao ler {nome_tag}: {status or 'status desconhecido'}"
        )

    return getattr(resposta, "Value", None)


def fechar_rockwell(conexao):
    """Fecha a conexao sem mascarar o erro principal de uma operacao."""
    if conexao is None:
        return
    try:
        conexao.Close()
    except Exception as erro:
        print(f"[AVISO ROCKWELL] Falha ao fechar conexao: {erro}")


def ler_tag_rockwell(ip, tag, slot=0):
    """Le uma tag Rockwell e retorna seu valor normalizado."""
    nome_tag = str(tag or "").strip()
    if not nome_tag:
        raise ValueError("Informe a tag Rockwell.")

    conexao = conectar_rockwell(ip, slot)
    try:
        resposta = conexao.Read(nome_tag)
        return validar_resposta(resposta, nome_tag)
    finally:
        fechar_rockwell(conexao)


def ler_tags_rockwell(ip, tags, slot=0):
    """Le varias tags na mesma conexao e preserva a ordem recebida."""
    nomes_tags = [str(tag or "").strip() for tag in (tags or [])]
    if not nomes_tags or any(not tag for tag in nomes_tags):
        raise ValueError("Informe uma lista valida de tags Rockwell.")

    conexao = conectar_rockwell(ip, slot)
    try:
        valores = []
        for nome_tag in nomes_tags:
            resposta = conexao.Read(nome_tag)
            valores.append(validar_resposta(resposta, nome_tag))
        return valores
    finally:
        fechar_rockwell(conexao)

def escrever_tag_rockwell(ip, tag, valor, slot=0):
    """Escreve um valor em uma tag Rockwell e valida o retorno."""
    nome_tag = str(tag or "").strip()

    if not nome_tag:
        raise ValueError("Informe a tag Rockwell.")

    conexao = conectar_rockwell(ip, slot)

    try:
        resposta = conexao.Write(nome_tag, valor)

        if resposta is None:
            raise RuntimeError(
                f"Sem resposta ao escrever a tag {nome_tag}."
            )

        status = getattr(resposta, "Status", None)

        if status != "Success":
            raise RuntimeError(
                f"Falha ao escrever {nome_tag}: "
                f"{status or 'status desconhecido'}"
            )

        return getattr(resposta, "Value", valor)

    finally:
        fechar_rockwell(conexao)