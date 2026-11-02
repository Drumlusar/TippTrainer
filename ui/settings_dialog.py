"""Fenster „Einstellungen“: Design, Schriftgrößen, Tastaturen, Bildschirmtastatur und Tempo-Cursor.

Tastaturen anlegen, umbenennen und löschen wirkt sofort; Layout und aktive Tastatur
werden mit „Übernehmen“ gespeichert."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout)

from storage.app_settings import AppSettings
from storage.keyboards import KeyboardStore
from ui import theme, units
from core.keyboard_layout import LAYOUTS
from ui.keyboard_view import MODES as KEYBOARD_MODES
from ui.widgets import fit_combo, plain_spin

UI_SCALES = (80, 90, 100, 110, 125, 140, 160)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, keyboards: KeyboardStore | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.settings = settings
        self.keyboards = keyboards if keyboards is not None else KeyboardStore(settings)
        self._layouts: dict[str, str] = {}          # geänderte Layouts bis „Übernehmen“

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

        # --- Bildschirmtastatur ------------------------------------------------------------
        self.keyboard_combo = QComboBox()
        for key, label in KEYBOARD_MODES.items():
            self.keyboard_combo.addItem(label, key)
        self.keyboard_combo.setCurrentIndex(max(0, self.keyboard_combo.findData(settings.keyboard_mode)))
        self.kb_select = QComboBox()                   # Tastatur, die gerade benutzt wird
        self.kb_new_btn = QPushButton("Neu …")
        self.kb_rename_btn = QPushButton("Umbenennen …")
        self.kb_delete_btn = QPushButton("Löschen")
        self.kb_new_btn.clicked.connect(self._kb_new)
        self.kb_rename_btn.clicked.connect(self._kb_rename)
        self.kb_delete_btn.clicked.connect(self._kb_delete)
        kb_row = QHBoxLayout()
        kb_row.addWidget(self.kb_select, 1)
        for btn in (self.kb_new_btn, self.kb_rename_btn, self.kb_delete_btn):
            kb_row.addWidget(btn)
        self.layout_combo = QComboBox()
        for lay in LAYOUTS.values():
            self.layout_combo.addItem(lay.name, lay.id)
        self.layout_combo.setToolTip("Layout der gewählten Tastatur – für die Bildschirmtastatur "
                                     "und die Tastaturansicht im Reiter Statistik. Welches Zeichen "
                                     "eine Taste wirklich erzeugt, legt das Betriebssystem fest.")
        self._fill_keyboards(self.keyboards.active().id)
        self.kb_select.currentIndexChanged.connect(self._show_kb_layout)
        self.layout_combo.currentIndexChanged.connect(self._layout_changed)
        self.keyboard_combo.setToolTip(
            "Nächste Taste: die Taste für das nächste Zeichen leuchtet, bei Großbuchstaben und "
            "Sonderzeichen auch Shift (Seite der anderen Hand) bzw. AltGr / ⌥.\n"
            "Gedrückte Tasten: jede Taste blinkt kurz auf, grün = richtig, rot = falsch.")
        self.kb_select.setToolTip("Tastatur, auf der Sie tippen (auch oben im Menü umschaltbar). "
                                  "Statistik, Highscores, Fortschritt und Verlauf lassen sich "
                                  "danach filtern.")
        kb_hint = QLabel("Jede Runde zählt für die gewählte Tastatur, ältere Runden für die "
                         "erste. Das Layout ändert nur die Anzeige – welches Zeichen eine Taste "
                         "erzeugt, legt das Betriebssystem fest.")
        kb_hint.setObjectName("Hint")
        kb_hint.setWordWrap(True)
        kb = QGroupBox("Tastatur und Bildschirmtastatur")
        kg = QGridLayout(kb)
        kg.setVerticalSpacing(8)
        for row, (text, item) in enumerate((("Tastatur", kb_row), ("Layout", self.layout_combo),
                                            ("Bildschirmtastatur", self.keyboard_combo))):
            kg.addWidget(QLabel(text), row, 0)
            if isinstance(item, QHBoxLayout):
                kg.addLayout(item, row, 1)
            else:
                kg.addWidget(item, row, 1, Qt.AlignmentFlag.AlignLeft)
        kg.addWidget(kb_hint, 3, 0, 1, 2)
        kg.setColumnStretch(1, 1)

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
        pv = QVBoxLayout(pace)
        pl = QFormLayout()
        pl.addRow(self.pace_check)
        pl.addRow("Zieltempo", self.pace_spin)
        pv.addLayout(pl)
        pv.addWidget(hint)

        for combo in (self.design_combo, self.scale_combo, self.keyboard_combo, self.layout_combo):
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
        layout.addWidget(kb)
        layout.addWidget(pace)
        layout.addWidget(buttons)
        self.setMinimumWidth(500)
        # Umbrechende Hinweistexte brauchen eine feste Breite, damit Qt ihre Höhe kennt
        for lbl in (kb_hint, hint):
            lbl.setMinimumWidth(440)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

    def save(self) -> None:
        """Werte in den Einstellungen speichern (nach „Übernehmen“)."""
        s = self.settings
        s.design = self.design_combo.currentText()
        s.text_size = self.text_spin.value()
        s.ui_scale = self.scale_combo.currentData()
        s.keyboard_mode = self.keyboard_combo.currentData()
        for kid, layout in self._layouts.items():
            self.keyboards.update(kid, layout=layout)
        if self.kb_select.currentData():
            self.keyboards.set_active(self.kb_select.currentData())
        s.pace_on = self.pace_check.isChecked()
        value = self.pace_spin.value()
        s.pace_cpm = value * 5 if units.unit() == units.WPM else value

    # --- Tastaturen --------------------------------------------------------------------

    def _fill_keyboards(self, select: str) -> None:
        self.kb_select.blockSignals(True)
        self.kb_select.clear()
        for k in self.keyboards.all():
            self.kb_select.addItem(k.name, k.id)
        self.kb_select.setCurrentIndex(max(0, self.kb_select.findData(select)))
        self.kb_select.blockSignals(False)
        fit_combo(self.kb_select)
        self._show_kb_layout()

    def _show_kb_layout(self) -> None:
        kid = self.kb_select.currentData()
        kb = self.keyboards.get(kid)
        layout = self._layouts.get(kid, kb.layout if kb else "qwertz")
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentIndex(max(0, self.layout_combo.findData(layout)))
        self.layout_combo.blockSignals(False)
        self.kb_delete_btn.setEnabled(self.keyboards.can_delete(kid))
        self.kb_delete_btn.setToolTip("" if self.keyboards.can_delete(kid) else
                                      "Die erste Tastatur enthält die älteren Runden und kann "
                                      "nur umbenannt werden.")

    def _layout_changed(self) -> None:
        self._layouts[self.kb_select.currentData()] = self.layout_combo.currentData()

    def _ask_name(self, title: str, current: str = "", except_id: str | None = None) -> str:
        name, ok = QInputDialog.getText(self, title, "Name der Tastatur (z. B. MacBook, Keychron):",
                                        text=current)
        name = name.strip()
        if not ok or not name:
            return ""
        if self.keyboards.name_taken(name, except_id):
            QMessageBox.warning(self, title, f"Eine Tastatur „{name}“ gibt es schon.")
            return ""
        return name

    def _kb_new(self) -> None:
        name = self._ask_name("Neue Tastatur")
        if name:
            new_id = self.keyboards.add(name, self.layout_combo.currentData())
            self._fill_keyboards(new_id)

    def _kb_rename(self) -> None:
        kid = self.kb_select.currentData()
        name = self._ask_name("Tastatur umbenennen", self.kb_select.currentText(), kid)
        if name:
            self.keyboards.update(kid, name=name)
            self._fill_keyboards(kid)

    def _kb_delete(self) -> None:
        kid = self.kb_select.currentData()
        if not self.keyboards.can_delete(kid):
            return
        answer = QMessageBox.question(
            self, "Tastatur löschen?",
            f"Tastatur „{self.kb_select.currentText()}“ löschen?\n"
            "Ihre Runden bleiben gespeichert und erscheinen unter „Alle Tastaturen“.")
        if answer == QMessageBox.StandardButton.Yes:
            self.keyboards.delete(kid)
            self._layouts.pop(kid, None)
            self._fill_keyboards(self.keyboards.active().id)

    def showEvent(self, event) -> None:
        # Umbrechende Hinweistexte unterschätzen die Mindesthöhe – nie kleiner als nötig öffnen
        hint = self.sizeHint()
        self.setMinimumSize(hint)
        self.resize(hint)
        super().showEvent(event)
