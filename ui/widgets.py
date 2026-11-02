"""Kleine gemeinsame Helfer für die Menü-Reiter."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QSpinBox

CUSTOM = "Eigene …"


def fit_combo(combo: QComboBox) -> None:
    """Combobox so breit wie ihr längster Eintrag; Aufklappliste nie schmaler als nötig."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    view = combo.view()
    view.setTextElideMode(Qt.TextElideMode.ElideNone)
    view.setMinimumWidth(view.sizeHintForColumn(0) + 36)
    combo.adjustSize()


def plain_spin(spin: QSpinBox) -> None:
    """Spinbox einheitlich gestalten. Die Pfeiltasten bleiben an (gestaltet in
    style.qss) – mit NoButtons blendet Qt bei diesem Stylesheet den Text aus."""
    spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
    spin.setMinimumWidth(max(110, spin.sizeHint().width() + 10))


def fmt_preset(seconds: int) -> str:
    return f"{seconds} s" if seconds < 60 else f"{seconds // 60} min"


ALL_KEYBOARDS = "Alle Tastaturen"


def fill_keyboard_combo(combo: QComboBox, keyboards, select: str | None = None,
                        with_all: bool = True) -> None:
    """Auswahlliste mit Tastaturen füllen (Daten = Tastatur-ID, None = alle).
    Die bisherige Auswahl bleibt erhalten, sonst wird `select` gewählt."""
    current = combo.currentData() if combo.count() else select
    if combo.count() and combo.currentIndex() == 0 and with_all:
        current = None                      # „Alle“ war gewählt
    combo.blockSignals(True)
    combo.clear()
    if with_all:
        combo.addItem(ALL_KEYBOARDS, None)
    for k in keyboards:
        combo.addItem(k.name, k.id)
    idx = combo.findData(current) if current is not None else (0 if with_all else -1)
    if idx < 0:
        idx = max(0, combo.findData(select)) if select is not None else 0
    combo.setCurrentIndex(idx)
    combo.blockSignals(False)
    fit_combo(combo)
