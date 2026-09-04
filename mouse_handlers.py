# mouse_handlers.py
# Mouse / PAN / ZOOM handlers (Matplotlib)

def on_mouse_press(event, ax, running, cursor_state, pan_state):
    if event.inaxes != ax or running:
        return

    # === Cursor Y dragging ===
    if cursor_state.cursorYA_enabled or cursor_state.cursorYB_enabled:
        if event.ydata is None:
            return

        distYA = abs(event.ydata - cursor_state.cursorYA_y) if cursor_state.cursorYA_y is not None else float("inf")
        distYB = abs(event.ydata - cursor_state.cursorYB_y) if cursor_state.cursorYB_y is not None else float("inf")

        cursor_state.cursorY_selected = "YA" if distYA <= distYB else "YB"
        cursor_state.cursor_dragging = True
        return

    # === Cursor X dragging (já existente) ===
    if cursor_state.cursorA_enabled or cursor_state.cursorB_enabled:
        distA = abs(event.xdata - cursor_state.cursorA_x) if cursor_state.cursorA_x is not None else float("inf")
        distB = abs(event.xdata - cursor_state.cursorB_x) if cursor_state.cursorB_x is not None else float("inf")

        cursor_state.cursor_selected = "A" if distA <= distB else "B"
        cursor_state.cursor_dragging = True
        return

    # === PAN ===
    if event.button == 1:
        pan_state["active"] = True
        pan_state["start_x"] = event.xdata
        pan_state["xlim_start"] = ax.get_xlim()
        

def on_mouse_release(event, cursor_state, pan_state):
    cursor_state.cursor_dragging = False
    cursor_state.cursor_selected = None
    cursor_state.cursorY_selected = None   # <<< ADICIONE
    pan_state["active"] = False


def on_mouse_move(
    event,
    ax,
    canvas,
    running,
    cursor_state,
    pan_state,
    atualizar_medidas_cb
):
    if event.inaxes != ax or running:
        return

    # === Cursor Y dragging ===
    if cursor_state.cursor_dragging and cursor_state.cursorY_selected:
        if event.ydata is None:
            return

        if cursor_state.cursorY_selected == "YA":
            cursor_state.cursorYA_y = event.ydata
            cursor_state.cursorYA_line.set_ydata([event.ydata, event.ydata])

        elif cursor_state.cursorY_selected == "YB":
            cursor_state.cursorYB_y = event.ydata
            cursor_state.cursorYB_line.set_ydata([event.ydata, event.ydata])

        atualizar_medidas_cb()
        canvas.draw_idle()
        return

    # === Cursor X dragging (já existente) ===
    if cursor_state.cursor_dragging and cursor_state.cursor_selected:
        if cursor_state.cursor_selected == "A":
            cursor_state.cursorA_x = event.xdata
            cursor_state.cursorA_line.set_xdata([event.xdata, event.xdata])
        elif cursor_state.cursor_selected == "B":
            cursor_state.cursorB_x = event.xdata
            cursor_state.cursorB_line.set_xdata([event.xdata, event.xdata])

        atualizar_medidas_cb()
        canvas.draw_idle()
        return

    # === PAN ===
    if pan_state["active"]:
        dx = event.xdata - pan_state["start_x"]
        ax.set_xlim(
            pan_state["xlim_start"][0] - dx,
            pan_state["xlim_start"][1] - dx
        )
        canvas.draw_idle()


def on_scroll(event, ax, running, entry_tempo_div, entry_divisoes, canvas, safe_float):
    if running or event.xdata is None:
        return

    tempo_div = safe_float(entry_tempo_div.get(), 0.5)
    n_div = int(entry_divisoes.get())

    tempo_div *= 0.9 if event.button == "up" else 1 / 0.9

    entry_tempo_div.delete(0, "end")
    entry_tempo_div.insert(0, f"{tempo_div:.6f}")

    width = tempo_div * n_div
    ax.set_xlim(event.xdata - width / 2, event.xdata + width / 2)
    canvas.draw_idle()
