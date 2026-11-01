"""Fenster „Einstellungen“: Design, Schriftgrößen und Tempo-Cursor."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout)

from storage.app_settings import AppSettings
from ui import theme, units
from ui.widgets import fit_combo, plain_spin

UI_SCALES = (80, 90, 100, 110, 125, 140, 160)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.settings = settings

        # --- Darstellung -------------------------------------------------------------------
        self.design_combo = QComboBox()
        self.design_combo.addItems(list(theme.THEMES))
        self.design_combo.setCurrentText(settings.design)
        self.text_spin = QSpinBox()
        self.text_spin.setRange(12, 60)
        self.text_spin.setSuffix(" pt")
        self.text_spin.setValue(settings.text_size)
        self.text_spin.setToolTip("Größe des Textes, der getippt wird (Standard 26 pt).")
        self.scale_combo = QComboBox()
        for pct in UI_SCALES:
            self.scale_combo.addItem(f"{pct} %" + ("  (Standard)" if pct == 100 else ""), pct)
        idx = self.scale_combo.findData(settings.ui_scale)
        self.scale_combo.setCurrentIndex(idx if idx >= 0 else UI_SCALES.index(100))
        self.scale_combo.setToolTip("Schrift von Menüs, Tabellen und Auswertung.")
        look = QGroupBox("Darstellung")
        fl = QFormLayout(look)
        fl.addRow("Design", self.design_combo)
        fl.addRow("Schriftgröße Tipptext", self.text_spin)
        fl.addRow("Schriftgröße Oberfläche", self.scale_combo)

        # --- Tempo-Cursor ------------------------------------------------------------------
        self.pace_check = QCheckBox("Tempo-Cursor anzeigen")
        self.pace_check.setChecked(settings.pace_on)
        self.pace_spin = QSpinBox()
        self.pace_spin.setRange(5, 2000)
        self.pace_spin.setSuffix(" " + units.unit())
        self.pace_spin.setValue(round(units.conv(settings.pace_cpm)))
        self.pace_check.toggled.connect(self.pace_spin.setEnabled)
        self.pace_spin.setEnabled(settings.pace_on)
        hint = QLabel("Ein schmaler grauer Cursor läuft ab dem ersten Anschlag gleichmäßig mit "
                      "diesem Tempo durch den Text. Liegt er vor Ihrem Cursor, sind Sie langsamer "
                      "als das Ziel. Im Prüfungsmodus bleibt er ausgeblendet.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        pace = QGroupBox("Tempo-Cursor")
        pl = QFormLayout(pace)
        pl.addRow(self.pace_check)
        pl.addRow("Zieltempo", self.pace_spin)
        pl.addRow(hint)

        for combo in (self.design_combo, self.scale_combo):
            fit_combo(combo)
        for spin in (self.text_spin, self.pace_spin):
            plain_spin(spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(look)
        layout.addWidget(pace)
        layout.addWidget(buttons)
        self.setMinimumWidth(460)

    def save(self) -> None:
        """Werte in den Einstellungen speichern (nach „Übernehmen“)."""
        s = self.settings
        s.design = self.design_combo.currentText()
        s.text_size = self.text_spin.value()
        s.ui_scale = self.scale_combo.currentData()
        s.pace_on = self.pace_check.isChecked()
        value = self.pace_spin.value()
        s.pace_cpm = value * 5 if units.unit() == units.WPM else value
