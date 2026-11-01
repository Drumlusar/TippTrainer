"""Gemeinsame Basis für Deathscreen und Ergebnisansicht.

Schutz vor versehentlichem Wegklicken: In den ersten 0,5 s nach dem
Erscheinen werden ALLE Tasten ignoriert (nicht nur die Leertaste) – wer
im Tippfluss noch ein „n“ oder Leerzeichen nachschiebt, landet nicht
sofort in der nächsten Runde.

Tasten danach: Leertaste = gleicher Text, N = neuer Text, Esc = Menü.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget

import config

HINT_TEXT = "Leertaste = gleicher Text   ·   N = neuer Text   ·   Esc = Menü"


def show_char(ch: str) -> str:
    return {" ": "Leerzeichen", "\n": "Enter"}.get(ch, f"„{ch}“")


class LockedEndView(QWidget):
    stats_toggled = Signal(bool)          # „In Statistik zählen“ vom Nutzer umgeschaltet
    restart_requested = Signal()
    new_text_requested = Signal()
    menu_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._shown_at = 0.0
        self.hint = QLabel(HINT_TEXT)
        self.hint.setObjectName("Hint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_check = QCheckBox("In Statistik zählen")
        self.stats_check.setObjectName("StatsCheck")
        self.stats_check.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # Leertaste = Neustart, nicht Haken
        self.stats_check.setToolTip("Aus = diese Runde fließt nicht in den Reiter Statistik ein "
                                    "(lässt sich jederzeit wieder einschalten).")
        # nur echte Klicks (kein setChecked beim Anzeigen) lösen das Umschalten aus
        self.stats_check.clicked.connect(lambda: self.stats_toggled.emit(self.stats_check.isChecked()))
        self.stats_check.hide()

    def make_stats_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.stats_check)
        row.addStretch(1)
        return row

    def set_stats_option(self, available: bool, checked: bool = True) -> None:
        """Schalter nur für Runden zeigen, die überhaupt zur Statistik beitragen."""
        self.stats_check.setVisible(available)
        self.stats_check.setChecked(checked)

    def make_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        for text, signal in (("Nochmal", self.restart_requested),
                             ("Neuer Text", self.new_text_requested),
                             ("Menü", self.menu_requested)):
            b = QPushButton(text)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # Leertaste soll keinen Button auslösen
            b.clicked.connect(signal.emit)
            row.addWidget(b)
        row.addStretch(1)
        return row

    def arm(self) -> None:
        """Beim Anzeigen aufrufen: Sperre starten, Hinweis nach Ablauf einblenden."""
        self._shown_at = time.monotonic()
        self.hint.setText(" ")
        QTimer.singleShot(int(config.RESTART_LOCK_S * 1000), lambda: self.hint.setText(HINT_TEXT))
        self.setFocus()

    def locked(self) -> bool:
        return time.monotonic() - self._shown_at < config.RESTART_LOCK_S

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.locked() or event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.menu_requested.emit()
        elif key == Qt.Key.Key_Space:
            self.restart_requested.emit()
        elif key == Qt.Key.Key_N:
            self.new_text_requested.emit()
        else:
            super().keyPressEvent(event)
