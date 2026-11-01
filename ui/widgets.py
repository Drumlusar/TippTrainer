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
