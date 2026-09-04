# scope_engine.py

class ScopeEngine:
    def __init__(self, n_divs, sub_divs):
        self.n_divs = n_divs
        self.sub_divs = sub_divs

    def calc_x_axis(self, mode, t_max, tempo_div):
        """
        Retorna:
        x_min, x_max, major_ticks, minor_ticks
        """

        # ===============================
        # AUTO SCALE = Time/Div automático
        # ===============================
        if mode == "AUTO":
            if t_max > 0:
                tempo_div = (t_max * 1.1) / self.n_divs
            else:
                tempo_div = tempo_div  # fallback

        # ===============================
        # ROLL (e AUTO convertido em ROLL)
        # ===============================
        janela = tempo_div * self.n_divs

        if t_max > janela:
            x_max = t_max
            x_min = x_max - janela
        else:
            x_min = 0.0
            x_max = janela

        # Grid métrico fixo (Tektronix)
        major_ticks = [
            x_min + i * tempo_div
            for i in range(self.n_divs + 1)
        ]

        sub = tempo_div / self.sub_divs
        minor_ticks = []

        for i in range(self.n_divs):
            base = major_ticks[i]
            for j in range(1, self.sub_divs):
                minor_ticks.append(base + j * sub)

        return x_min, x_max, major_ticks, minor_ticks
