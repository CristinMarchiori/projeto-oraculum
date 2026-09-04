# cursors.py
# Cursores verticais A/B + medições (Tektronix style)

CURSOR_A_COLOR = "#00FFFF"
CURSOR_B_COLOR = "#FFFF00"
CURSOR_YA_COLOR = "#FF3333"
CURSOR_YB_COLOR = "#33FF33"



class CursorState:
    def __init__(self):
        self.cursorA_enabled = False
        self.cursorB_enabled = False
        self.cursorA_x = None
        self.cursorB_x = None
        self.cursorA_line = None
        self.cursorB_line = None
        self.cursor_selected = None
        self.cursor_dragging = False

        self.cursorYA_enabled = False
        self.cursorYB_enabled = False
        self.cursorYA_y = None
        self.cursorYB_y = None
        self.cursorYA_line = None
        self.cursorYB_line = None
        self.cursorY_selected = None

        
        


# ==========================================================
# UTILS
# ==========================================================
def format_time(value):
    abs_v = abs(value)
    sign = "-" if value < 0 else ""
    if abs_v >= 1:
        return f"{sign}{abs_v:.3f} s"
    elif abs_v >= 1e-3:
        return f"{sign}{abs_v*1e3:.3f} ms"
    elif abs_v >= 1e-6:
        return f"{sign}{abs_v*1e6:.3f} µs"
    else:
        return f"{sign}{abs_v*1e9:.3f} ns"


# ==========================================================
# RESET VISUAL
# ==========================================================
def reset_cursors_visual(state: CursorState):
    if state.cursorA_line is not None:
        try: state.cursorA_line.remove()
        except: pass
    if state.cursorB_line is not None:
        try: state.cursorB_line.remove()
        except: pass

    state.cursorA_line = None
    state.cursorB_line = None
    state.cursorA_x = None
    state.cursorB_x = None


# ==========================================================
# MEDIÇÕES
# ==========================================================
def atualizar_medidas(state: CursorState, cursor_var_a, cursor_var_b, medidas_text):
    linhas = []

    # ==================================================
    # MEDIÇÕES X (tempo)
    # ==================================================
    if cursor_var_a and cursor_var_b:
        if cursor_var_a.get() and cursor_var_b.get():
            if state.cursorA_x is not None and state.cursorB_x is not None:
                XA = state.cursorA_x
                XB = state.cursorB_x

                dT = XB - XA
                abs_dt = abs(dT)
                freq = (1.0 / abs_dt) if abs_dt > 0 else None

                linhas.append(f"XA: {format_time(XA)}")
                linhas.append(f"XB: {format_time(XB)}")
                linhas.append(f"Δt: {format_time(dT)}")

                if freq:
                    linhas.append(f"Freq: {freq:,.3f} Hz")
                else:
                    linhas.append("Freq: ∞")

    # ==================================================
    # MEDIÇÕES Y (amplitude)
    # ==================================================
    if (
        state.cursorYA_y is not None
        and state.cursorYB_y is not None
    ):
        YA = state.cursorYA_y
        YB = state.cursorYB_y
        dY = YB - YA

        linhas.append("")  # linha em branco (separador)
        linhas.append(f"YA: {YA:.3f}")
        linhas.append(f"YB: {YB:.3f}")
        linhas.append(f"ΔY: {dY:.3f}")

    # ==================================================
    # SAÍDA FINAL
    # ==================================================
    if linhas:
        medidas_text.set_text("\n".join(linhas))
    else:
        medidas_text.set_text("")



# ==========================================================
# TOGGLE DOS CURSORES (🔥 CHAVE DA CORREÇÃO 🔥)
# ==========================================================
def toggle_cursor(which, state: CursorState, ax, canvas,
                  running, cursor_var_a, cursor_var_b, medidas_text):

    if running:
        cursor_var_a.set(False)
        cursor_var_b.set(False)
        return

    if which == "A":
        state.cursorA_enabled = cursor_var_a.get()
        if state.cursorA_enabled:
            xmin, xmax = ax.get_xlim()
            state.cursorA_x = xmin + 0.25 * (xmax - xmin)
            state.cursorA_line = ax.axvline(
                state.cursorA_x,
                color=CURSOR_A_COLOR,
                linewidth=1.8,
                zorder=10
            )
        else:
            if state.cursorA_line:
                state.cursorA_line.remove()
            state.cursorA_line = None
            state.cursorA_x = None

    elif which == "B":
        state.cursorB_enabled = cursor_var_b.get()
        if state.cursorB_enabled:
            xmin, xmax = ax.get_xlim()
            state.cursorB_x = xmin + 0.75 * (xmax - xmin)
            state.cursorB_line = ax.axvline(
                state.cursorB_x,
                color=CURSOR_B_COLOR,
                linewidth=1.8,
                zorder=10
            )
        else:
            if state.cursorB_line:
                state.cursorB_line.remove()
            state.cursorB_line = None
            state.cursorB_x = None

    # 🔑 ATUALIZA MEDIÇÕES IMEDIATAMENTE
    atualizar_medidas(state, cursor_var_a, cursor_var_b, medidas_text)

    canvas.draw_idle()



# ==========================================================
# TOGGLE DOS CURSORES Y 
# ==========================================================
def toggle_cursor_y(which, state: CursorState, ax, canvas,
                    running, cursor_var_ya, cursor_var_yb, medidas_text):

    if running:
        cursor_var_ya.set(False)
        cursor_var_yb.set(False)
        return

    ymin, ymax = ax.get_ylim()

    if which == "YA":
        state.cursorYA_enabled = cursor_var_ya.get()
        if state.cursorYA_enabled:
            state.cursorYA_y = ymin + 0.25 * (ymax - ymin)
            state.cursorYA_line = ax.axhline(
                state.cursorYA_y,
                color=CURSOR_YA_COLOR,
                linewidth=1.6,
                zorder=10
            )
        else:
            if state.cursorYA_line:
                state.cursorYA_line.remove()
            state.cursorYA_line = None
            state.cursorYA_y = None

    elif which == "YB":
        state.cursorYB_enabled = cursor_var_yb.get()
        if state.cursorYB_enabled:
            state.cursorYB_y = ymin + 0.75 * (ymax - ymin)
            state.cursorYB_line = ax.axhline(
                state.cursorYB_y,
                color=CURSOR_YB_COLOR,
                linewidth=1.6,
                zorder=10
            )
        else:
            if state.cursorYB_line:
                state.cursorYB_line.remove()
            state.cursorYB_line = None
            state.cursorYB_y = None

    atualizar_medidas(state, None, None, medidas_text)
    canvas.draw_idle()
