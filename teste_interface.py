from pathlib import Path

import webview


class OraculumWebAPI:
    def testar_conexao(self):
        print("HTML chamou a função Python testar_conexao()")

        return {
            "sucesso": True,
            "mensagem": "Comunicação HTML ↔ Python funcionando"
        }

    def obter_estado(self):
        return {
            "conectado": True,
            "monitorando": False,
            "ciclo_ativo": False,
            "pressao_lida": 123.4,
            "pressao_programada": 180.0,
            "inercia_pressao": 5.0,
            "trigger": 0,
            "monitor_status": 1,
            "tempo_sob_pressao": 12.5,
            "tempo_ventilacao": 4.8,
            "mensagem": "Valores fixos recebidos do Python"
        }


def main():
    arquivo_html = (
        Path(__file__).resolve().parent
        / "interface"
        / "index.html"
    )

    print(f"HTML: {arquivo_html}")
    print(f"Existe: {arquivo_html.exists()}")

    if not arquivo_html.exists():
        raise FileNotFoundError(
            f"Interface não encontrada: {arquivo_html}"
        )

    api = OraculumWebAPI()

    webview.create_window(
        title="Oraculum - Teste da Ponte Python",
        url=arquivo_html.as_uri(),
        js_api=api,
        width=1440,
        height=900,
        min_size=(1100, 700),
        resizable=True
    )

    webview.start()


if __name__ == "__main__":
    main()