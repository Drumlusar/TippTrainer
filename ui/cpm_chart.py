"""Tempo-Verlauf (A/min oder W/min) als matplotlib-Grafik im dunklen Theme.

Eine Linie (Tempo pro Sekunde, geglättet über 5 s), eine gestrichelte
Durchschnittslinie und rote Kreuze an den Zeitpunkten, an denen Fehler
passiert sind (auch später korrigierte).
"""
from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")

import numpy as np                                                  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg      # noqa: E402
from matplotlib.figure import Figure                                # noqa: E402

BG = "#26272c"
LINE = "#e2b714"
AVG = "#8a8d96"
ERR = "#f2545b"
INK = "#b8b6b0"
MUTED = "#6c6f78"
GRID = "#34363c"


class CpmChart(FigureCanvasQTAgg):
    def __init__(self, parent=None) -> None:
        self.fig = Figure(figsize=(5, 3), facecolor=BG, layout="constrained")
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)

    def plot(self, series: list[float], avg: float, error_times: list[float],
             unit: str = "A/min") -> None:
        ax = self.ax
        ax.clear()
        ax.set_facecolor(BG)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=MUTED, labelsize=9, length=0, pad=6)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)

        if not series:
            ax.set_xticks([])
            ax.set_yticks([])
            ax.text(0.5, 0.5, "Runde zu kurz für einen Verlauf", color=MUTED,
                    ha="center", va="center", transform=ax.transAxes)
            self.draw_idle()
            return

        x = np.arange(1, len(series) + 1)
        y = np.asarray(series)
        ax.plot(x, y, color=LINE, linewidth=2, solid_capstyle="round", label=unit)
        ax.axhline(avg, color=AVG, linewidth=1.2, linestyle=(0, (5, 4)),
                   label=f"Durchschnitt {avg:.0f}")

        errs = [t for t in error_times if t <= x[-1]]
        if errs:
            ey = np.interp(errs, np.concatenate(([0], x)), np.concatenate(([y[0]], y)))
            ax.scatter(errs, ey, marker="x", s=46, linewidths=2, color=ERR, zorder=3,
                       label=f"Fehler ({len(error_times)})")

        ax.set_xlim(0, max(x[-1], 5))
        ax.set_ylim(0, max(y.max(), avg) * 1.15 + 1)
        ax.set_xlabel("Sekunden", color=MUTED, fontsize=9)
        ax.set_ylabel(unit, color=MUTED, fontsize=9)
        leg = ax.legend(loc="lower right", fontsize=8, frameon=False, labelcolor=INK)
        leg.set_zorder(4)
        self.draw_idle()
