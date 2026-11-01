"""Reiter „Fortschritt“: Entwicklung je Test-Profil über die Zeit.

Oben: Netto-Tempo pro Tag (Punkte) und gleitender 7-Tage-Schnitt (Linie).
Unten, kleiner: Fehlerquote pro Tag und 7-Tage-Schnitt. Zwei getrennte Achsen statt
einer Doppelachse, damit sich die Skalen nicht vermischen.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")

import matplotlib.dates as mdates                                   # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg      # noqa: E402
from matplotlib.figure import Figure                                # noqa: E402
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel,      # noqa: E402
                               QVBoxLayout, QWidget)

import config                                                       # noqa: E402
from storage.progress import DayPoint, profile_progress             # noqa: E402
from ui import units                                                # noqa: E402
from ui.cpm_chart import BG, ERR, GRID, INK, LINE, MUTED            # noqa: E402
from ui.widgets import fit_combo                                    # noqa: E402

DOT = "#8a7a3a"        # Tageswerte: gedämpftes Gold, Linie = kräftiges Gold
ERR_DOT = "#8f4a4e"


def _style(ax) -> None:
    ax.set_facecolor(BG)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0, pad=6)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


class ProgressChart(FigureCanvasQTAgg):
    def __init__(self, parent=None) -> None:
        self.fig = Figure(figsize=(6, 4), facecolor=BG, layout="constrained")
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax_speed, self.ax_err = self.fig.subplots(
            2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1.3]})

    def plot(self, points: list[DayPoint]) -> None:
        a1, a2 = self.ax_speed, self.ax_err
        a1.clear()
        a2.clear()
        _style(a1)
        _style(a2)
        if not points:
            for ax in (a1, a2):
                ax.set_xticks([])
                ax.set_yticks([])
            a1.text(0.5, 0.5, "Noch keine Runden mit diesem Profil", color=MUTED,
                    ha="center", va="center", transform=a1.transAxes)
            self.draw_idle()
            return
        u = units.unit()
        days = [p.day for p in points]
        a1.scatter(days, [units.conv(p.net_cpm) for p in points], s=26, color=DOT,
                   zorder=3, label="Tagesmittel")
        a1.plot(days, [units.conv(p.net_cpm_7d) for p in points], color=LINE, linewidth=2.2,
                label="7-Tage-Schnitt")
        a1.set_ylabel(f"Netto {u}", color=MUTED, fontsize=9)
        top = max(units.conv(max(p.net_cpm for p in points)), 1)
        a1.set_ylim(0, top * 1.15)
        a1.legend(loc="lower right", fontsize=8, frameon=False, labelcolor=INK)

        a2.scatter(days, [p.error_rate for p in points], s=18, color=ERR_DOT, zorder=3)
        a2.plot(days, [p.error_rate_7d for p in points], color=ERR, linewidth=1.8)
        a2.set_ylabel("Fehler %", color=MUTED, fontsize=9)
        a2.set_ylim(0, max(max(p.error_rate for p in points), 1) * 1.25)

        a2.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
        a2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
        if len(days) == 1:                         # ein einzelner Tag: etwas Rand
            from datetime import timedelta
            a2.set_xlim(days[0] - timedelta(days=3), days[0] + timedelta(days=3))
        self.draw_idle()


class ProgressTab(QWidget):
    def __init__(self, history_file: Path = config.HISTORY_FILE, parent=None) -> None:
        super().__init__(parent)
        self.history_file = history_file
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self.refresh)
        label = QLabel("Profil:")
        label.setObjectName("Hint")
        self.summary = QLabel()
        self.summary.setObjectName("Hint")
        top = QHBoxLayout()
        top.addWidget(label)
        top.addWidget(self.profile_combo)
        top.addSpacing(16)
        top.addWidget(self.summary, 1)
        self.chart = ProgressChart()
        hint = QLabel("Es zählen Runden, die mit genau den Einstellungen des Profils gestartet "
                      "wurden. Punkte = Mittel eines Tages, Linie = Mittel aller Runden der "
                      "letzten 7 Tage.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.chart, 1)
        layout.addWidget(hint)

    def set_profiles(self, names: list[str], select: str | None = None) -> None:
        current = select or self.profile_combo.currentText()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        idx = self.profile_combo.findText(current)
        self.profile_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.profile_combo.blockSignals(False)
        fit_combo(self.profile_combo)
        self.refresh()

    def refresh(self) -> None:
        name = self.profile_combo.currentText()
        points = profile_progress(name, self.history_file) if name else []
        self.chart.plot(points)
        if not points:
            self.summary.setText("")
            return
        runs = sum(p.runs for p in points)
        last = points[-1]
        text = (f"{runs} Runden an {len(points)} Tagen   ·   7-Tage-Schnitt "
                f"{units.fmt(last.net_cpm_7d, with_unit=True)} netto, "
                f"{last.error_rate_7d:.1f} % Fehler")
        cons = [p.consistency for p in points if p.consistency is not None
                and (last.day - p.day).days < 7]       # gleiches 7-Tage-Fenster
        if cons:
            text += f", Konsistenz {sum(cons) / len(cons):.0f} %"
        self.summary.setText(text)
