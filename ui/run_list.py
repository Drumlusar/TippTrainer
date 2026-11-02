"""Seitenliste „Letzte Runden“: eine anklickbare Zeile pro gespeicherter Runde.

Jede Zeile zeigt zwei Textzeilen, damit nichts abgeschnitten wird:
    31.10. 23:00   Wörter · 1 min · DbM                    ☆
    355 A/min  ·  2 Fehler  ·  fertig   (Einheit umschaltbar)
Klick auf die Zeile öffnet den Endbildschirm, der Stern markiert die Runde
als „dauerhaft speichern“. Bei vielen Runden erscheint eine Scrollbar.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QLabel, QScrollArea,
                               QToolButton, QVBoxLayout, QWidget)

from core.models import SessionEnd, SourceMode
from core.scoring import score
from ui import units
from ui import theme
from storage.run_store import StoredRun

SOURCE_SHORT = {SourceMode.RANDOM_WORDS: "Wörter", SourceMode.RANDOM_TEXT: "Zufallstext"}
RESULT_SHORT = {SessionEnd.COMPLETED: "fertig", SessionEnd.TIME_UP: "Zeit um",
                SessionEnd.DIED: "gestorben", SessionEnd.STOPPED: "beendet"}

# Filter im Reiter Verlauf
FILTER_ALL, FILTER_NORMAL, FILTER_DEATH = "Alle Runden", "Normale Runden", "Nur Death by Mistake"
FILTER_PINNED = "★ Gespeicherte"


def result_label(run: StoredRun) -> tuple[str, str | None]:
    """Ergebniswort und ggf. Farbe. Bei Death by Mistake: „gestorben“ (rot) oder
    „überlebt“ (grün), damit man den Ausgang auf einen Blick sieht."""
    r = run.result
    if r.settings.death_by_mistake:
        if r.end_reason is SessionEnd.DIED:
            return "gestorben", theme.hexc("error")
        return "überlebt", theme.hexc("ok")
    return RESULT_SHORT.get(r.end_reason, r.end_reason.value), None


def matches_filter(run: StoredRun, flt: str) -> bool:
    if flt == FILTER_PINNED:
        return run.pinned
    dbm = run.result.settings.death_by_mistake
    return flt == FILTER_ALL or (flt == FILTER_DEATH) == dbm


def fmt_limit(seconds: int) -> str:
    if seconds < 60 or seconds % 60:
        return f"{seconds} s"
    return f"{seconds // 60} min"


def run_lines(run: StoredRun, keyboard_name: str = "") -> tuple[str, str]:
    """Die beiden Textzeilen einer Runde."""
    r = run.result
    s = r.settings
    if s.source_mode is SourceMode.PHRASES:
        mode = f"Phrasen: {', '.join(r.text_names)} · "
        mode += f"{s.repetitions}×" if s.repetitions else "∞"
    else:
        mode = SOURCE_SHORT.get(s.source_mode, ", ".join(r.text_names))
        if s.source_mode is SourceMode.RANDOM_WORDS and r.text_names:
            mode += f" ({r.text_names[0].removesuffix('.txt')})"
    if s.time_limit_s is not None:
        mode += f" · {fmt_limit(s.time_limit_s)}"
    if s.input_mode.name == "TYPEWRITER":
        mode += " · Schreibm."
    if s.exam_mode:
        mode += " · Prüfung"
    if s.profile:                                  # Profilname ersetzt die Detailangaben
        mode = f"Profil: {s.profile}"
    if keyboard_name:                            # nur bei mehreren Tastaturen angezeigt
        mode += f" · {keyboard_name}"
    top = f"{run.when:%d.%m. %H:%M}   {mode}"
    bottom = f"{units.fmt(r.cpm_avg, with_unit=True)}  ·  {r.errors} Fehler  ·  "
    return top, bottom


class RunRow(QFrame):
    clicked = Signal(str)
    pin_toggled = Signal(str, bool)

    def __init__(self, run: StoredRun, penalty: int = 10, is_record: bool = False,
                 keyboard_name: str = "") -> None:
        super().__init__()
        self.run_id = run.id
        self.setObjectName("RunRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Klicken: Auswertung anzeigen")

        top, bottom = run_lines(run, keyboard_name)
        word, color = result_label(run)
        dbm = run.result.settings.death_by_mistake
        self.setProperty("dbm", dbm)                  # roter Rand links (style.qss)
        l_top = QLabel(top)
        l_top.setObjectName("RunTop")
        l_bottom = QLabel()
        l_bottom.setObjectName("RunBottom")
        l_bottom.setTextFormat(Qt.TextFormat.RichText)
        word_html = (f'<span style="color:{color}; font-weight:600;">{word}</span>'
                     if color else word)
        r = run.result
        points = score(r.keystrokes, r.mistakes, r.duration_s, penalty)
        l_bottom.setText(bottom.replace("  ", "&nbsp; ")
                         + f"{points:.0f} Punkte&nbsp; ·&nbsp; " + word_html)
        self.record_badge = QLabel("REKORD")
        self.record_badge.setObjectName("RecordBadge")
        self.record_badge.setToolTip("Bestleistung für diesen Text bzw. dieses Profil (Reiter „Highscores“)")
        self.record_badge.setVisible(is_record)
        self.nostats_badge = QLabel("OHNE STATISTIK")
        self.nostats_badge.setObjectName("NoStatsBadge")
        self.nostats_badge.setToolTip("Diese Runde zählt nicht im Reiter Statistik "
                                      "(in der Auswertung umschaltbar).")
        self.nostats_badge.setVisible(run.stats is not None and not run.in_stats)
        self.badge = QLabel("DEATH BY MISTAKE")
        self.badge.setObjectName("DbmBadge")
        self.badge.setVisible(dbm)

        self.star = QToolButton()
        self.star.setObjectName("PinButton")
        self.star.setCheckable(True)
        self.star.setChecked(run.pinned)
        self.star.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.star.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_star()
        self.star.toggled.connect(self._on_star)

        grid = QGridLayout(self)
        grid.setContentsMargins(10, 6, 6, 6)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(1)
        grid.addWidget(l_top, 0, 0)
        grid.addWidget(l_bottom, 1, 0)
        grid.addWidget(self.nostats_badge, 0, 1, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.record_badge, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.badge, 0, 3, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.star, 0, 4, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        grid.setColumnStretch(0, 1)

    def _update_star(self) -> None:
        pinned = self.star.isChecked()
        self.star.setText("★" if pinned else "☆")
        self.star.setToolTip("Dauerhaft gespeichert – klicken zum Aufheben" if pinned
                             else "Dauerhaft speichern (sonst nur die letzten Runden)")

    def _on_star(self, checked: bool) -> None:
        self._update_star()
        self.pin_toggled.emit(self.run_id, checked)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.run_id)
        super().mouseReleaseEvent(event)


class RunList(QScrollArea):
    open_requested = Signal(str)
    pin_toggled = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RunList")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._inner = QWidget()
        self._inner.setObjectName("RunListInner")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(0, 0, 4, 0)
        self._layout.setSpacing(4)
        self.setWidget(self._inner)
        self.empty = QLabel("Noch keine Runden gespeichert.")
        self.empty.setObjectName("Hint")
        self._all: list[StoredRun] = []
        self._filter = FILTER_ALL
        self._keyboard: str | None = None              # Tastatur-ID, None = alle
        self._kb_names: dict[str, str] = {}            # ID -> Name (leer = nur eine Tastatur)
        self._penalty = 10
        self._records: set[str] = set()
        self.set_runs([])

    def set_keyboard_filter(self, keyboard_id: str | None) -> None:
        self._keyboard = keyboard_id
        self.set_runs(self._all)

    def set_keyboard_names(self, names: dict[str, str]) -> None:
        """Bei mehr als einer Tastatur steht ihr Name in jeder Zeile."""
        self._kb_names = names if len(names) > 1 else {}

    def set_filter(self, flt: str) -> None:
        self._filter = flt
        self.set_runs(self._all)

    def set_runs(self, runs: list[StoredRun], penalty: int | None = None,
                 record_whens: set[str] | None = None) -> None:
        if penalty is not None:
            self._penalty = penalty
        if record_whens is not None:
            self._records = set(record_whens)
        self._all = list(runs)
        runs = [r for r in runs if matches_filter(r, self._filter)
                and (self._keyboard is None
                     or (r.result.settings.keyboard or "standard") == self._keyboard)]
        self.empty.setText("Noch keine Runden gespeichert." if not self._all
                           else "Keine Runden für diesen Filter.")
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self.empty:
                widget.setParent(None)      # sofort aus dem Fenster lösen ...
                widget.deleteLater()        # ... und später freigeben
        if not runs:
            self._layout.addWidget(self.empty)
            self.empty.show()
        else:
            self.empty.hide()
            for run in runs:
                kb = self._kb_names.get(run.result.settings.keyboard or "standard", "gelöschte Tastatur") \
                    if self._kb_names else ""
                row = RunRow(run, self._penalty,
                             run.when.strftime("%Y-%m-%d %H:%M:%S") in self._records, kb)
                row.clicked.connect(self.open_requested.emit)
                row.pin_toggled.connect(self.pin_toggled.emit)
                self._layout.addWidget(row)
        self._layout.addStretch(1)
