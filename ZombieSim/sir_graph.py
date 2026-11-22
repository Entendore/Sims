"""
Z-POC: Matplotlib SIR graph embedded in a Qt canvas.
"""

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvasQTAgg


class SIRGraphCanvas(FigureCanvasQTAgg):
    """Embedded matplotlib SIR chart with throttled redraws."""

    def __init__(self, parent=None, width=5, height=3):
        self.fig, self.ax = plt.subplots(
            figsize=(width, height), facecolor="#14161c"
        )
        super().__init__(self.fig)
        self.setMinimumHeight(200)
        self._tick = 0

    def reset(self):
        self._tick = 0

    def update_plot(self, simulation, force=False):
        self._tick += 1
        if not force and self._tick % 3 != 0:
            return

        self.ax.clear()
        if simulation.history_s:
            days = range(len(simulation.history_s))
            self.ax.fill_between(days, simulation.history_s, alpha=0.12, color="cyan")
            self.ax.fill_between(days, simulation.history_r, alpha=0.12, color="yellow")
            self.ax.plot(
                days, simulation.history_s, "c-", label="Susceptible", linewidth=1.5
            )
            self.ax.plot(
                days, simulation.history_i, "m-", label="Infected", linewidth=2
            )
            self.ax.plot(
                days, simulation.history_r, "y-", label="Removed", linewidth=1.5
            )
            if simulation.history_new:
                self.ax.bar(
                    days, simulation.history_new, alpha=0.18, color="red",
                    label="New Cases",
                )

        self.ax.set_title("SIR Model", color="white", fontsize=10)
        self.ax.set_xlabel("Days", color="white", fontsize=8)
        self.ax.set_ylabel("Population", color="white", fontsize=8)
        self.ax.legend(
            fontsize=7, loc="right",
            facecolor="#2c3e50", edgecolor="#555", labelcolor="white",
        )
        self.ax.grid(True, linestyle="--", alpha=0.18)
        self.ax.set_facecolor("#12141a")
        self.ax.tick_params(colors="white", labelsize=7)
        for spine in self.ax.spines.values():
            spine.set_edgecolor("#333")
        self.fig.tight_layout()
        self.draw()