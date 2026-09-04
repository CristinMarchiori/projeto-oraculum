# plot_manager.py
# Gerenciador de display do osciloscópio (Tektronix-like)
# Responsável por:
# - Roll mode (RUN)
# - Time/Div real (10 divisões)
# - Grid major/minor
# - Autoscale somente em Y
# - Atualização de linhas

# =====================================================================
# CONSTANTES DO INSTRUMENTO
# =====================================================================
N_DIVS = 10
SUB_DIVS = 5
JANELA_OSC = 5000


def update_plot(
    *,
    running: bool,
    buffers: dict,
    linhas: dict,
    ax,
    canvas,
    intervalo: float,
    tempo_div: float,
    ch_colors: list,
    cursor_state,
    reset_cursors_visual,
    atualizar_medidas,
    cursor_var_a,
    cursor_var_b,
    medidas_text,
    texto_intervalo
):
    """
    Atualiza o display do osciloscópio.
    Mantém comportamento Tektronix real.
    """

    # ==============================================================
    # RUN MODE (ROLL MODE)
    # ==============================================================
    if running and buffers:
        janela_tempo = tempo_div * N_DIVS
        texto_intervalo.set_text(f"Time/Div = {tempo_div:.3f} s")

        t_max = 0.0

        for i, tag in enumerate(buffers):
            janela = buffers[tag][-JANELA_OSC:]
            tempo = [k * intervalo for k in range(len(janela))]

            if tempo:
                t_max = max(t_max, tempo[-1])

            if tag not in linhas:
                linhas[tag], = ax.plot(
                    [],
                    [],
                    color=ch_colors[i % len(ch_colors)],
                    linewidth=1.6,
                    label=tag
                )

            linhas[tag].set_data(tempo, janela)

        # ===== EIXO X (ROLLING WINDOW) =====
        if t_max > janela_tempo:
            x_min = t_max - janela
