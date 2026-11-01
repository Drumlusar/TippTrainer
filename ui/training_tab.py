"""Reiter „Training“: Zufällige Wörter, zufälliger oder spezifischer Text – mit Test-Profilen.

Ein Profil speichert alle Einstellungen dieses Reiters unter einem Namen. Wird mit
genau diesen Einstellungen gestartet, trägt die Runde den Profilnamen und zählt in
dessen Bestenliste und Fortschrittskurve.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog,
                               QGridLayout, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QRadioButton,
                               QSpinBox, QVBoxLayout, QWidget)

import config
from core.models import InputMode, SessionSettings, SourceMode
from core.session import new_seed
from core.text_source import TextLibrary, text_group
from storage.profiles import ProfileStore
from ui.widgets import CUSTOM, fit_combo, fmt_preset, plain_spin

NO_PROFILE = "— kein Profil —"
ALL_TEXTS = "Alle Texte"


def sub_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SubLabel")
    return lbl


class TrainingTab(QWidget):
    start_requested = Signal(object)    # SessionSettings

    def __init__(self, library: TextLibrary, profiles: ProfileStore | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.library = library
        self.profiles = profiles if profiles is not None else ProfileStore()
        self._applying = False

        # --- Profil ------------------------------------------------------------------------
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("Feste Testbedingungen mit eigener Bestenliste und "
                                      "Fortschrittskurve (Reiter Highscores / Fortschritt).")
        self.profile_combo.activated.connect(self._load_profile)
        self.save_profile_btn = QPushButton("Als Profil speichern …")
        self.save_profile_btn.clicked.connect(self._save_profile)
        self.delete_profile_btn = QPushButton("Löschen")
        self.delete_profile_btn.clicked.connect(self._delete_profile)
        prof_box = QGroupBox("Test-Profil")
        pl = QHBoxLayout(prof_box)
        pl.addWidget(self.profile_combo, 1)
        pl.addWidget(self.save_profile_btn)
        pl.addWidget(self.delete_profile_btn)

        # --- Zeitlimit ---------------------------------------------------------------------
        self.time_check = QCheckBox("Zeitlimit")
        self.time_combo = QComboBox()
        for s in config.TIME_LIMIT_PRESETS_S:
            self.time_combo.addItem(fmt_preset(s), s)
        self.time_combo.addItem(CUSTOM, None)
        self.time_combo.setCurrentIndex(config.TIME_LIMIT_PRESETS_S.index(60))
        self.time_spin = QSpinBox()
        self.time_spin.setRange(5, 3600)
        self.time_spin.setValue(90)
        self.time_spin.setSuffix(" s")
        time_box = QGroupBox("Modus")
        tl = QHBoxLayout(time_box)
        tl.addWidget(self.time_check)
        tl.addWidget(self.time_combo)
        tl.addWidget(self.time_spin)
        tl.addStretch(1)

        # --- Textquelle ----------------------------------------------------------------------
        self.rb_words = QRadioButton(SourceMode.RANDOM_WORDS.value)
        self.rb_random = QRadioButton(SourceMode.RANDOM_TEXT.value)
        self.rb_specific = QRadioButton(SourceMode.SPECIFIC_TEXT.value)
        self.source_group = QButtonGroup(self)
        for rb in (self.rb_words, self.rb_random, self.rb_specific):
            self.source_group.addButton(rb)

        self.words_combo = QComboBox()
        for n in config.WORD_COUNT_PRESETS:
            self.words_combo.addItem(f"{n} Wörter", n)
        self.words_combo.addItem(CUSTOM, None)
        self.words_combo.setCurrentIndex(config.WORD_COUNT_PRESETS.index(config.DEFAULT_WORD_COUNT))
        self.words_spin = QSpinBox()
        self.words_spin.setRange(1, 2000)
        self.words_spin.setValue(75)
        self.words_spin.setSuffix(" Wörter")

        self.wordlist_combo = QComboBox()
        self.wordlist_combo.setToolTip("Jede .txt-Datei in daten/wortlisten/ ist eine Liste.")
        self.lower_check = QCheckBox("nur Kleinbuchstaben, ohne Satzzeichen")
        self.lower_check.setToolTip("Online-Stil: Großbuchstaben werden klein, Wörter mit "
                                    "Satzzeichen oder Ziffern entfallen.")
        self.min_spin = QSpinBox()
        self.max_spin = QSpinBox()
        for spin, prefix in ((self.min_spin, "min. "), (self.max_spin, "max. ")):
            spin.setRange(0, 30)
            spin.setSpecialValueText(prefix + "egal")
            spin.setPrefix(prefix)
            spin.setSuffix(" Buchst.")
        self.group_combo = QComboBox()
        self.group_combo.setToolTip("Gruppe = Dateiname bis zum letzten „_“, "
                                    "z. B. lang_de_… oder leicht_…")
        self.file_combo = QComboBox()
        self.browse_btn = QPushButton("Durchsuchen …")
        self.browse_btn.clicked.connect(self._browse)

        self.wl_label, self.filter_label, self.len_label = (
            sub_label("Wortliste"), sub_label("Filter"), sub_label("Wortlänge"))
        src_box = QGroupBox("Text")
        sl = QGridLayout(src_box)
        sl.addWidget(self.rb_words, 0, 0)
        sl.addWidget(self.words_combo, 0, 1)
        sl.addWidget(self.words_spin, 0, 2)
        sl.addWidget(self.wl_label, 1, 0)
        sl.addWidget(self.wordlist_combo, 1, 1)
        sl.addWidget(self.filter_label, 2, 0)
        sl.addWidget(self.lower_check, 2, 1, 1, 2)
        sl.addWidget(self.len_label, 3, 0)
        sl.addWidget(self.min_spin, 3, 1)
        sl.addWidget(self.max_spin, 3, 2)
        sl.addWidget(self.rb_random, 4, 0)
        sl.addWidget(self.group_combo, 4, 1)
        sl.addWidget(self.rb_specific, 5, 0)
        sl.addWidget(self.file_combo, 5, 1)
        sl.addWidget(self.browse_btn, 5, 2)
        sl.setColumnStretch(3, 1)

        # --- Eingabe -------------------------------------------------------------------------
        self.rb_computer = QRadioButton("Computer (Backspace erlaubt)")
        self.rb_typewriter = QRadioButton("Schreibmaschine (kein Backspace)")
        self.input_group = QButtonGroup(self)
        self.input_group.addButton(self.rb_computer)
        self.input_group.addButton(self.rb_typewriter)
        self.rb_computer.setChecked(True)
        self.death_check = QCheckBox("Death by Mistake (Stopp beim ersten Fehler)")
        self.altgr_check = QCheckBox("AltGr-Zeichen zulassen  ( @ € { } [ ] \\ ~ | )")
        self.skip_check = QCheckBox("Leertaste springt zum nächsten Wort (wie online)")
        self.skip_check.setToolTip("Leertaste mitten im Wort: Rest des Wortes zählt als "
                                   "verpasst, weiter geht es beim nächsten Wort.")
        self.exam_check = QCheckBox("Prüfungsmodus (keine Live-Fehler, kein Live-Tempo)")
        self.exam_check.setToolTip("Wie bei einer Abschrift: Fehler und Tempo erst in der Auswertung.")
        in_box = QGroupBox("Eingabe")
        il = QVBoxLayout(in_box)
        for w in (self.rb_computer, self.rb_typewriter):
            il.addWidget(w)
        il.addSpacing(6)
        for w in (self.death_check, self.altgr_check, self.skip_check, self.exam_check):
            il.addWidget(w)

        # --- Start + Hinweise ------------------------------------------------------------------
        self.start_btn = QPushButton("Start Training  (Enter)")
        self.start_btn.setObjectName("StartButton")
        self.start_btn.clicked.connect(self.try_start)
        self.problems = QLabel()
        self.problems.setObjectName("Problems")
        self.problems.setWordWrap(True)

        left = QVBoxLayout()
        left.addWidget(prof_box)
        left.addWidget(time_box)
        left.addWidget(src_box)
        left.addStretch(1)
        right = QVBoxLayout()
        right.addWidget(in_box)
        right.addStretch(1)
        right.addWidget(self.start_btn)
        right.addWidget(self.problems)
        outer = QHBoxLayout(self)
        outer.addLayout(left, 11)
        outer.addSpacing(12)
        outer.addLayout(right, 9)

        for combo in (self.time_combo, self.words_combo, self.file_combo):
            fit_combo(combo)
        for spin in (self.time_spin, self.words_spin, self.min_spin, self.max_spin):
            plain_spin(spin)

        self._fill_files()
        self._fill_wordlists()
        self._fill_groups()
        self._fill_profiles()
        if library.texts:
            self.rb_random.setChecked(True)
        else:
            self.rb_words.setChecked(True)

        for w in (self.time_check, self.rb_words, self.rb_random, self.rb_specific,
                  self.rb_computer, self.rb_typewriter, self.death_check, self.altgr_check,
                  self.skip_check, self.exam_check, self.lower_check):
            w.toggled.connect(self._refresh)
        for combo in (self.time_combo, self.words_combo, self.file_combo, self.wordlist_combo,
                      self.group_combo):
            combo.currentIndexChanged.connect(self._refresh)
        for spin in (self.time_spin, self.words_spin, self.min_spin, self.max_spin):
            spin.valueChanged.connect(self._refresh)
        self._refresh()

    # --- Listen (neu) füllen ------------------------------------------------------------------

    def _fill_files(self) -> None:
        """Dateiliste aus der Bibliothek; eine per „Durchsuchen“ gewählte Datei und
        die aktuelle Auswahl bleiben erhalten."""
        current = self.file_combo.currentData()
        extra = [(self.file_combo.itemText(i), self.file_combo.itemData(i))
                 for i in range(self.file_combo.count())
                 if Path(self.file_combo.itemData(i)).parent != config.TEXT_DIR]
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for t in self.library.texts:
            self.file_combo.addItem(t.name, str(config.TEXT_DIR / t.name))
        for name, data in extra:
            self.file_combo.addItem(name, data)
        idx = self.file_combo.findData(current)
        if idx >= 0:
            self.file_combo.setCurrentIndex(idx)
        self.file_combo.blockSignals(False)
        fit_combo(self.file_combo)
        if self.library.problems:
            self.problems.setText("Hinweise:\n• " + "\n• ".join(self.library.problems))
            self.problems.show()
        else:
            self.problems.hide()

    def _fill_wordlists(self) -> None:
        current = self.wordlist_combo.currentData() or self.library.wordlist_name
        self.wordlist_combo.blockSignals(True)
        self.wordlist_combo.clear()
        for name in self.library.wordlist_names:
            self.wordlist_combo.addItem(name.removesuffix(".txt"), name)
        self.wordlist_combo.setCurrentIndex(max(0, self.wordlist_combo.findData(current)))
        self.wordlist_combo.blockSignals(False)
        fit_combo(self.wordlist_combo)

    def _fill_groups(self) -> None:
        current = self.group_combo.currentData() or ""
        counts: dict[str, int] = {}
        for t in self.library.texts:
            g = text_group(t.name)
            if g:
                counts[g] = counts.get(g, 0) + 1
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem(ALL_TEXTS, "")
        for g in sorted(counts):
            self.group_combo.addItem(f"{g}_…  ({counts[g]})", g)
        self.group_combo.setCurrentIndex(max(0, self.group_combo.findData(current)))
        self.group_combo.blockSignals(False)
        fit_combo(self.group_combo)

    def _fill_profiles(self, select: str | None = None) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(NO_PROFILE)
        for name in self.profiles.names():
            self.profile_combo.addItem(name)
        if select:
            self.profile_combo.setCurrentIndex(max(0, self.profile_combo.findText(select)))
        self.profile_combo.blockSignals(False)
        fit_combo(self.profile_combo)

    def set_library(self, library: TextLibrary) -> None:
        self.library = library
        self._fill_files()
        self._fill_wordlists()
        self._fill_groups()
        self._refresh()

    # --- Abhängigkeiten der Einstellungen ------------------------------------------------------

    def _refresh(self) -> None:
        if self._applying:
            return
        has_words = bool(self.library.wordlist_names)
        has_texts = bool(self.library.texts)
        timed = self.time_check.isChecked()

        self.time_combo.setEnabled(timed)
        self.time_spin.setVisible(self.time_combo.currentData() is None)
        self.time_spin.setEnabled(timed)

        self.rb_words.setEnabled(has_words)
        self.rb_random.setEnabled(has_texts)

        words_mode = self.rb_words.isChecked()
        self.words_combo.setEnabled(words_mode and not timed)
        self.words_spin.setVisible(self.words_combo.currentData() is None)
        self.words_spin.setEnabled(words_mode and not timed)
        for w in (self.wordlist_combo, self.wl_label, self.lower_check, self.filter_label,
                  self.min_spin, self.max_spin, self.len_label):
            w.setEnabled(words_mode)
        self.group_combo.setEnabled(self.rb_random.isChecked())
        specific = self.rb_specific.isChecked()
        self.file_combo.setEnabled(specific)

        ok = ((words_mode and has_words) or (self.rb_random.isChecked() and has_texts)
              or (specific and self.file_combo.count() > 0))
        self.start_btn.setEnabled(ok)

        # Profil anzeigen, wenn die Einstellungen genau einem Profil entsprechen
        name = self.profiles.matching(self.current_settings()) if ok else ""
        self.profile_combo.blockSignals(True)
        self.profile_combo.setCurrentIndex(max(0, self.profile_combo.findText(name)) if name else 0)
        self.profile_combo.blockSignals(False)
        self.delete_profile_btn.setEnabled(bool(name))

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Text wählen", str(config.TEXT_DIR),
                                              "Textdateien (*.txt);;Alle Dateien (*)")
        if path:
            self.file_combo.addItem(Path(path).name, path)
            fit_combo(self.file_combo)
            self.file_combo.setCurrentIndex(self.file_combo.count() - 1)
            self.rb_specific.setChecked(True)
            self._refresh()

    # --- Profile ---------------------------------------------------------------------------------

    def _load_profile(self) -> None:
        name = self.profile_combo.currentText()
        if self.profile_combo.currentIndex() == 0:
            return
        s = self.profiles.get(name)
        if s is None:
            QMessageBox.warning(self, "Profil", f"Profil „{name}“ konnte nicht geladen werden.")
            return
        self.apply_settings(s)

    def apply_settings(self, s: SessionSettings) -> None:
        """Alle Bedienelemente auf diese Einstellungen setzen."""
        self._applying = True
        try:
            self.time_check.setChecked(s.time_limit_s is not None)
            if s.time_limit_s is not None:
                idx = self.time_combo.findData(s.time_limit_s)
                if idx < 0:
                    idx = self.time_combo.count() - 1          # „Eigene …“
                    self.time_spin.setValue(s.time_limit_s)
                self.time_combo.setCurrentIndex(idx)
            {SourceMode.RANDOM_WORDS: self.rb_words, SourceMode.RANDOM_TEXT: self.rb_random,
             SourceMode.SPECIFIC_TEXT: self.rb_specific}.get(s.source_mode, self.rb_random).setChecked(True)
            idx = self.words_combo.findData(s.word_count)
            if idx < 0:
                idx = self.words_combo.count() - 1
                self.words_spin.setValue(s.word_count)
            self.words_combo.setCurrentIndex(idx)
            if s.wordlist:
                self.wordlist_combo.setCurrentIndex(max(0, self.wordlist_combo.findData(s.wordlist)))
            self.lower_check.setChecked(s.words_lowercase)
            self.min_spin.setValue(s.word_min_len)
            self.max_spin.setValue(s.word_max_len)
            self.group_combo.setCurrentIndex(max(0, self.group_combo.findData(s.text_group)))
            if s.specific_file is not None:
                data = str(s.specific_file)
                if self.file_combo.findData(data) < 0:
                    self.file_combo.addItem(s.specific_file.name, data)
                self.file_combo.setCurrentIndex(self.file_combo.findData(data))
            (self.rb_typewriter if s.input_mode is InputMode.TYPEWRITER else self.rb_computer).setChecked(True)
            self.death_check.setChecked(s.death_by_mistake)
            self.altgr_check.setChecked(s.allow_altgr)
            self.skip_check.setChecked(s.space_skips_word)
            self.exam_check.setChecked(s.exam_mode)
        finally:
            self._applying = False
        self._refresh()

    def _save_profile(self) -> None:
        current = self.profile_combo.currentText() if self.profile_combo.currentIndex() else ""
        name, ok = QInputDialog.getText(self, "Test-Profil speichern", "Name des Profils:",
                                        text=current)
        name = name.strip()
        if not ok or not name:
            return
        if name in self.profiles.names():
            answer = QMessageBox.question(self, "Profil überschreiben?",
                                          f"„{name}“ gibt es schon. Überschreiben?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        if self.profiles.save(name, self.current_settings()):
            self._fill_profiles(select=name)
            self._refresh()

    def _delete_profile(self) -> None:
        name = self.profile_combo.currentText()
        if self.profile_combo.currentIndex() == 0:
            return
        answer = QMessageBox.question(self, "Profil löschen?",
                                      f"Profil „{name}“ löschen?\n(Die Runden und Highscores "
                                      "dieses Profils bleiben im Verlauf erhalten.)")
        if answer == QMessageBox.StandardButton.Yes:
            self.profiles.delete(name)
            self._fill_profiles()
            self._refresh()

    # --- Einstellungen erzeugen --------------------------------------------------------------

    def current_settings(self) -> SessionSettings:
        """Einstellungen des Reiters. Felder, die im gewählten Modus keine Rolle spielen,
        bekommen ihren Standardwert – so lassen sich Profile eindeutig wiedererkennen."""
        timed = self.time_check.isChecked()
        time_limit = (self.time_combo.currentData() or self.time_spin.value()) if timed else None
        if self.rb_words.isChecked():
            mode = SourceMode.RANDOM_WORDS
        elif self.rb_random.isChecked():
            mode = SourceMode.RANDOM_TEXT
        else:
            mode = SourceMode.SPECIFIC_TEXT
        words = mode is SourceMode.RANDOM_WORDS
        word_count = ((self.words_combo.currentData() or self.words_spin.value())
                      if words and not timed else config.DEFAULT_WORD_COUNT)
        file = (Path(self.file_combo.currentData())
                if mode is SourceMode.SPECIFIC_TEXT and self.file_combo.currentData() else None)
        min_len, max_len = self.min_spin.value(), self.max_spin.value()
        if max_len and min_len > max_len:
            min_len, max_len = max_len, min_len
        return SessionSettings(
            source_mode=mode,
            time_limit_s=time_limit,
            word_count=word_count,
            specific_file=file,
            input_mode=InputMode.TYPEWRITER if self.rb_typewriter.isChecked() else InputMode.COMPUTER,
            death_by_mistake=self.death_check.isChecked(),
            allow_altgr=self.altgr_check.isChecked(),
            seed=new_seed(),
            wordlist=(self.wordlist_combo.currentData() or "") if words else "",
            words_lowercase=self.lower_check.isChecked() if words else False,
            word_min_len=min_len if words else 0,
            word_max_len=max_len if words else 0,
            text_group=(self.group_combo.currentData() or "") if mode is SourceMode.RANDOM_TEXT else "",
            space_skips_word=self.skip_check.isChecked(),
            exam_mode=self.exam_check.isChecked(),
        )

    def try_start(self) -> None:
        if self.start_btn.isEnabled():
            s = self.current_settings()
            self.start_requested.emit(replace(s, profile=self.profiles.matching(s)))
