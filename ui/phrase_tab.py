"""Reiter „Phrasen“: eigene Phrasen in Schleife üben, mit Presets.

Eine Phrase pro Zeile. Ein Durchgang = alle Phrasen einmal, jeweils
getrennt durch eine Leertaste (jede Phrase steht trotzdem in eigener Zeile). Eigene Einstellungen, unabhängig vom Reiter „Training“.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGroupBox,
                               QHBoxLayout, QInputDialog, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QRadioButton,
                               QSpinBox, QVBoxLayout, QWidget)

import config
from core.models import InputMode, SessionSettings, SourceMode
from core.session import new_seed
from core.text_source import parse_phrases
from storage.presets import PresetStore
from ui import theme
from ui.widgets import CUSTOM, fit_combo, plain_spin

NO_PRESET = "— Preset laden —"
INFINITE = "Unendlich (Esc beendet)"


class PhraseTab(QWidget):
    start_requested = Signal(object)    # SessionSettings

    def __init__(self, presets: PresetStore, parent=None) -> None:
        super().__init__(parent)
        self.presets = presets
        self._loaded_name = ""            # Name des zuletzt geladenen/gespeicherten Presets

        # --- Presets -------------------------------------------------------------------
        self.preset_combo = QComboBox()
        self.preset_combo.activated.connect(self._load_selected)
        self.save_as_btn = QPushButton("Speichern unter …")
        self.save_as_btn.clicked.connect(self._save_as)
        self.overwrite_btn = QPushButton("Überschreiben")
        self.overwrite_btn.clicked.connect(self._overwrite)
        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.clicked.connect(self._delete)
        preset_row = QHBoxLayout()
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.save_as_btn)
        preset_row.addWidget(self.overwrite_btn)
        preset_row.addWidget(self.delete_btn)

        # --- Textfeld ------------------------------------------------------------------
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("PhraseEditor")
        self.editor.setFont(theme.mono_font(15))
        self.editor.setPlaceholderText("Eine Phrase pro Zeile, z. B.:\n\nGröße\nqu\nß ö ä ü\n"
                                       "Rückenschmerzen\nMit freundlichen Grüßen")
        self.editor.setPlainText(presets.last_text())
        self.editor.textChanged.connect(self._refresh)
        self.count_label = QLabel()
        self.count_label.setObjectName("Hint")

        left = QVBoxLayout()
        left.addLayout(preset_row)
        left.addWidget(self.editor, 1)
        left.addWidget(self.count_label)

        # --- Durchgänge ----------------------------------------------------------------
        self.reps_combo = QComboBox()
        for n in config.REPETITION_PRESETS:
            self.reps_combo.addItem(f"{n}×", n)
        self.reps_combo.addItem(CUSTOM, -1)
        self.reps_combo.addItem(INFINITE, None)
        self.reps_combo.setCurrentIndex(1)
        self.reps_spin = QSpinBox()
        self.reps_spin.setRange(1, 999)
        self.reps_spin.setValue(15)
        self.reps_spin.setSuffix("×")
        self.reps_combo.currentIndexChanged.connect(self._refresh)
        reps_box = QGroupBox("Durchgänge")
        rl = QHBoxLayout(reps_box)
        rl.addWidget(self.reps_combo)
        rl.addWidget(self.reps_spin)
        rl.addStretch(1)

        # --- Reihenfolge ----------------------------------------------------------------
        self.rb_in_order = QRadioButton("Der Reihe nach")
        self.rb_shuffle = QRadioButton("Zufällig gemischt")
        order_group = QButtonGroup(self)
        order_group.addButton(self.rb_in_order)
        order_group.addButton(self.rb_shuffle)
        self.rb_in_order.setChecked(True)
        order_box = QGroupBox("Reihenfolge")
        ol = QVBoxLayout(order_box)
        ol.addWidget(self.rb_in_order)
        ol.addWidget(self.rb_shuffle)

        # --- Bei Fehler -------------------------------------------------------------------
        self.rb_continue = QRadioButton("Weitertippen")
        self.rb_restart = QRadioButton("Phrase neu beginnen")
        self.rb_death = QRadioButton("Death by Mistake (Runde endet)")
        err_group = QButtonGroup(self)
        for rb in (self.rb_continue, self.rb_restart, self.rb_death):
            err_group.addButton(rb)
        self.rb_continue.setChecked(True)
        err_box = QGroupBox("Bei Fehler")
        el = QVBoxLayout(err_box)
        for rb in (self.rb_continue, self.rb_restart, self.rb_death):
            el.addWidget(rb)

        # --- Eingabe -------------------------------------------------------------------------
        self.rb_computer = QRadioButton("Computer (Backspace erlaubt)")
        self.rb_typewriter = QRadioButton("Schreibmaschine (kein Backspace)")
        in_group = QButtonGroup(self)
        in_group.addButton(self.rb_computer)
        in_group.addButton(self.rb_typewriter)
        self.rb_computer.setChecked(True)
        self.altgr_check = QCheckBox("AltGr-Zeichen zulassen")
        self.altgr_check.toggled.connect(self._refresh)
        in_box = QGroupBox("Eingabe")
        il = QVBoxLayout(in_box)
        il.addWidget(self.rb_computer)
        il.addWidget(self.rb_typewriter)
        il.addWidget(self.altgr_check)

        self.start_btn = QPushButton("Start Phrasen  (⌘/Strg + Enter)")
        self.start_btn.setObjectName("StartButton")
        self.start_btn.clicked.connect(self.try_start)

        right = QVBoxLayout()
        right.addWidget(reps_box)
        right.addWidget(order_box)
        right.addWidget(err_box)
        right.addWidget(in_box)
        right.addStretch(1)
        right.addWidget(self.start_btn)

        outer = QHBoxLayout(self)
        outer.addLayout(left, 3)
        outer.addSpacing(16)
        outer.addLayout(right, 2)

        fit_combo(self.reps_combo)
        plain_spin(self.reps_spin)
        self._reload_presets()
        self._refresh()

    # --- Zustand ---------------------------------------------------------------------

    def phrases(self) -> list[str]:
        return parse_phrases(self.editor.toPlainText(), self.altgr_check.isChecked())

    def _refresh(self) -> None:
        n = len(self.phrases())
        self.count_label.setText(f"{n} Phrase{'n' if n != 1 else ''}  ·  "
                                 "Ein Durchgang = alle Phrasen einmal, getrennt durch eine Leertaste")
        self.reps_spin.setVisible(self.reps_combo.currentData() == -1)
        self.start_btn.setEnabled(n > 0)
        name = self._selected_name()
        own = bool(name) and not self.presets.is_template(name)   # Vorlagen sind schreibgeschützt
        self.overwrite_btn.setEnabled(own)
        self.delete_btn.setEnabled(own)
        tip = ("Mitgelieferte Vorlage – kann nicht überschrieben oder gelöscht werden. "
               "Änderungen mit „Speichern unter …“ als eigenes Preset sichern.")
        for btn in (self.overwrite_btn, self.delete_btn):
            btn.setToolTip("" if own or not name else tip)

    # --- Presets ----------------------------------------------------------------------

    def _reload_presets(self, select: str = "") -> None:
        self.preset_combo.clear()
        self.preset_combo.addItem(NO_PRESET)
        for name in self.presets.own_names():
            self.preset_combo.addItem(name)
        templates = self.presets.template_names()
        if templates:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in templates:                     # mitgelieferte Vorlagen unten
                self.preset_combo.addItem(name)
                self.preset_combo.setItemData(self.preset_combo.count() - 1,
                                              "Mitgelieferte Vorlage", Qt.ItemDataRole.ToolTipRole)
        idx = self.preset_combo.findText(select) if select else 0
        self.preset_combo.setCurrentIndex(max(0, idx))
        fit_combo(self.preset_combo)
        self._refresh()

    def _selected_name(self) -> str:
        return self.preset_combo.currentText() if self.preset_combo.currentIndex() > 0 else ""

    def _load_selected(self) -> None:
        name = self._selected_name()
        if name:
            text = self.presets.get(name)
            if text is not None:
                self.editor.setPlainText(text)
                self._loaded_name = name
        self._refresh()

    def _save_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Preset speichern", "Name des Presets:",
                                        text=self._selected_name())
        name = name.strip()
        if not ok or not name:
            return
        if name in self.presets.names():
            answer = QMessageBox.question(self, "Preset überschreiben?",
                                          f"„{name}“ gibt es schon. Überschreiben?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._store(name)

    def _overwrite(self) -> None:
        name = self._selected_name()
        if name:
            self._store(name)

    def _store(self, name: str) -> None:
        if not self.presets.save(name, self.editor.toPlainText()):
            QMessageBox.warning(self, "Fehler", "Preset konnte nicht gespeichert werden.")
            return
        self._loaded_name = name
        self._reload_presets(select=name)

    def _delete(self) -> None:
        name = self._selected_name()
        if not name:
            return
        answer = QMessageBox.question(self, "Preset löschen?", f"Preset „{name}“ löschen?")
        if answer == QMessageBox.StandardButton.Yes:
            self.presets.delete(name)
            if self._loaded_name == name:
                self._loaded_name = ""
            self._reload_presets()

    # --- Start -------------------------------------------------------------------------

    def current_settings(self) -> SessionSettings:
        data = self.reps_combo.currentData()
        reps = None if data is None else (self.reps_spin.value() if data == -1 else data)
        # Name nur übernehmen, wenn der Text noch dem gewählten Preset entspricht
        name = self._selected_name()
        if name and self.presets.get(name) != self.editor.toPlainText():
            name = ""
        return SessionSettings(
            source_mode=SourceMode.PHRASES,
            time_limit_s=None,
            word_count=0,
            specific_file=None,
            input_mode=InputMode.TYPEWRITER if self.rb_typewriter.isChecked() else InputMode.COMPUTER,
            death_by_mistake=self.rb_death.isChecked(),
            allow_altgr=self.altgr_check.isChecked(),
            seed=new_seed(),
            phrases=tuple(self.editor.toPlainText().splitlines()),
            repetitions=reps,
            shuffle=self.rb_shuffle.isChecked(),
            restart_phrase_on_error=self.rb_restart.isChecked(),
            phrase_set_name=name or "Eigene Phrasen",
        )

    def try_start(self) -> None:
        if self.start_btn.isEnabled():
            self.presets.set_last_text(self.editor.toPlainText())
            self.start_requested.emit(self.current_settings())
