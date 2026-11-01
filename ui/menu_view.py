"""Hauptmenü mit Reitern: Training, Phrasen, Verlauf, Highscores, Fortschritt, Statistik.

Oben rechts: Tempo-Einheit (A/min oder W/min) für alle Anzeigen.

Enter startet den aktiven Reiter (im Phrasen-Textfeld fügt Enter eine Zeile
ein – dort startet ⌘/Strg + Enter).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QTabWidget,
                               QVBoxLayout, QWidget)

import config
from core.text_source import TextLibrary
from storage.presets import PresetStore
from storage.profiles import ProfileStore
from storage.stats_store import StatsStore
from ui.highscore_tab import HighscoreTab
from ui import units
from ui.phrase_tab import PhraseTab
from ui.progress_tab import ProgressTab
from ui.stats_tab import StatsTab
from ui.run_list import (FILTER_ALL, FILTER_DEATH, FILTER_NORMAL, FILTER_PINNED,
                         RunList)
from ui.widgets import fit_combo
from ui.training_tab import TrainingTab

TAB_TRAINING, TAB_PHRASES, TAB_HISTORY, TAB_HIGHSCORES = range(4)


class MenuView(QWidget):
    start_requested = Signal(object)     # SessionSettings
    open_run_requested = Signal(str)     # Run-ID
    pin_run_requested = Signal(str, bool)
    unit_changed = Signal(str)

    def __init__(self, library: TextLibrary, presets: PresetStore | None = None,
                 penalty: int = config.SCORE_PENALTY,
                 stats_store: StatsStore | None = None,
                 profiles: ProfileStore | None = None,
                 history_file=config.HISTORY_FILE, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MenuView")

        title = QLabel("Tipptrainer")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(list(units.UNITS))
        self.unit_combo.setCurrentText(units.unit())
        self.unit_combo.setToolTip("Tempo-Einheit für alle Anzeigen. W/min = A/min / 5 "
                                   "(ein Wort zählt als 5 Anschläge).")
        self.unit_combo.currentTextChanged.connect(self.unit_changed.emit)
        fit_combo(self.unit_combo)
        unit_label = QLabel("Einheit:")
        unit_label.setObjectName("Hint")
        head = QHBoxLayout()
        head.addSpacing(self.unit_combo.sizeHint().width() + 60)   # Titel optisch mittig
        head.addStretch(1)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(unit_label)
        head.addWidget(self.unit_combo)

        self.profiles = profiles if profiles is not None else ProfileStore()
        self.training = TrainingTab(library, self.profiles)
        self.phrases = PhraseTab(presets if presets is not None else PresetStore())
        self.training.start_requested.connect(self.start_requested.emit)
        self.phrases.start_requested.connect(self.start_requested.emit)

        # Verlauf
        self.run_list = RunList()
        self.run_list.open_requested.connect(self.open_run_requested.emit)
        self.run_list.pin_toggled.connect(self.pin_run_requested.emit)
        legend = QLabel(f"Klick = Auswertung  ·  ☆ = dauerhaft speichern "
                        f"(sonst bleiben die letzten {config.KEEP_RECENT_RUNS} Runden)")
        legend.setObjectName("Hint")
        self.filter_combo = QComboBox()
        for f in (FILTER_ALL, FILTER_NORMAL, FILTER_DEATH, FILTER_PINNED):
            self.filter_combo.addItem(f)
        self.filter_combo.currentTextChanged.connect(self.run_list.set_filter)
        fit_combo(self.filter_combo)
        filter_row = QHBoxLayout()
        filter_label = QLabel("Anzeigen:")
        filter_label.setObjectName("Hint")
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch(1)
        history = QWidget()
        hl = QVBoxLayout(history)
        hl.addLayout(filter_row)
        hl.addWidget(self.run_list, 1)
        hl.addWidget(legend)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MenuTabs")
        self.tabs.addTab(self.training, "Training")
        self.tabs.addTab(self.phrases, "Phrasen")
        self.tabs.addTab(history, "Verlauf")
        self.highscores = HighscoreTab(penalty)
        self.tabs.addTab(self.highscores, "Highscores")
        self.progress = ProgressTab(history_file)
        self.tabs.addTab(self.progress, "Fortschritt")
        self.stats = StatsTab(stats_store if stats_store is not None else StatsStore(),
                              self.phrases.presets)
        self.stats.preset_saved.connect(lambda name: self.phrases._reload_presets(select=name))
        self.tabs.addTab(self.stats, "Statistik")
        self.tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.save_warning = QLabel()
        self.save_warning.setObjectName("Problems")
        self.save_warning.setWordWrap(True)
        self.save_warning.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 10, 36, 14)
        layout.addLayout(head)
        layout.addWidget(self.save_warning)
        layout.addWidget(self.tabs, 1)

        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for seq in ("Return", "Enter"):
            QShortcut(QKeySequence(seq), self, activated=self._enter, context=ctx)
        for seq in ("Ctrl+Return", "Ctrl+Enter"):     # Ctrl = ⌘ auf dem Mac
            QShortcut(QKeySequence(seq), self, activated=self.start_current, context=ctx)

    # --- Start --------------------------------------------------------------------------

    def _enter(self) -> None:
        # Das Phrasen-Textfeld nimmt Enter selbst (neue Zeile); hier landet Enter
        # nur, wenn ein anderes Element den Fokus hat.
        self.start_current()

    def start_current(self) -> None:
        tab = self.tabs.currentIndex()
        if tab == TAB_TRAINING:
            self.training.try_start()
        elif tab == TAB_PHRASES:
            self.phrases.try_start()

    # --- von außen ------------------------------------------------------------------------

    def set_library(self, library: TextLibrary) -> None:
        self.training.set_library(library)

    def set_runs(self, runs, penalty: int = config.SCORE_PENALTY,
                 record_whens: set[str] = frozenset()) -> None:
        self.run_list.set_runs(runs, penalty, record_whens)

    def set_save_warning(self, text: str) -> None:
        self.save_warning.setText(text)
        self.save_warning.setVisible(bool(text))
