"""Hauptfenster: QStackedWidget mit Menü, Tippansicht, Deathscreen und Ergebnis."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox, QStackedWidget

import config
from core.models import SessionEnd, SessionResult
from core.scoring import score
from core.session import SessionController, new_seed
from core.text_normalizer import TextLoadError
from core.text_source import TextLibrary
from storage import highscores as hs
from storage import history
from storage.app_settings import AppSettings
from storage.stats_store import StatsStore
from core.models import SourceMode
from storage.presets import PresetStore
from storage.profiles import ProfileStore
from storage.run_store import RunStore
from ui import theme, units
from ui.settings_dialog import SettingsDialog
from ui.death_view import DeathView
from ui.menu_view import MenuView
from ui.result_view import ResultView
from ui.typing_view import TypingView


class MainWindow(QMainWindow):
    def __init__(self, library: TextLibrary | None = None,
                 history_file: Path = config.HISTORY_FILE,
                 run_store: RunStore | None = None,
                 presets: PresetStore | None = None,
                 app_settings: AppSettings | None = None,
                 stats_store: StatsStore | None = None,
                 profiles: ProfileStore | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Tipptrainer")
        self.resize(1120, 700)
        self.setMinimumSize(860, 540)

        self._reload_library = library is None          # Tests übergeben eine feste Bibliothek
        self.library = library if library is not None else TextLibrary.load()
        self.history_file = history_file
        self.runs = run_store if run_store is not None else RunStore()
        self.controller = SessionController(self.library)
        self.shown: SessionResult | None = None    # Ergebnis, das gerade angezeigt wird

        self.settings = app_settings if app_settings is not None else AppSettings()
        self.stats_store = stats_store if stats_store is not None else StatsStore()
        units.set_unit(self.settings.unit)
        theme.set_theme(self.settings.design)          # vor dem Aufbau der Ansichten
        self.profiles = profiles if profiles is not None else ProfileStore()
        self.menu = MenuView(self.library, presets, self.settings.penalty, self.stats_store,
                             self.profiles, history_file)
        self.typing = TypingView(self.controller)
        self.death = DeathView()
        self.result = ResultView()

        self.stack = QStackedWidget()
        for view in (self.menu, self.typing, self.death, self.result):
            self.stack.addWidget(view)
        self.setCentralWidget(self.stack)

        self.menu.start_requested.connect(self.start_session)
        self.menu.open_run_requested.connect(self.open_run)
        self.menu.pin_run_requested.connect(self.pin_run)
        self.menu.highscores.open_attempt.connect(self.open_attempt)
        self.menu.highscores.open_profile_attempt.connect(self.open_profile_attempt)
        self.menu.unit_changed.connect(self.set_unit)
        self.menu.settings_requested.connect(self.open_settings)
        self.apply_appearance()
        self.menu.highscores.penalty_changed.connect(self.set_penalty)
        self.typing.finished.connect(self.on_finished)
        self.typing.aborted.connect(self.show_menu)
        self.shown_run_id: str | None = None
        for view in (self.death, self.result):
            view.stats_toggled.connect(self.toggle_stats)
            view.restart_requested.connect(self.restart_shown)
            view.new_text_requested.connect(self.new_text_for_shown)
            view.menu_requested.connect(self.show_menu)

        self.show_menu()

    # --- Ablauf ----------------------------------------------------------------------

    def start_session(self, settings) -> None:
        # Profil immer frisch bestimmen: ein inzwischen geändertes oder gelöschtes Profil
        # soll einer wiederholten alten Runde nicht mehr anhaften.
        settings = replace(settings, profile=self.profiles.matching(settings))
        self._run(lambda: self.controller.start(settings))

    def restart_shown(self) -> None:
        """Gleicher Text wie die angezeigte Runde (gleiche Einstellungen, gleicher Seed) –
        funktioniert auch für ältere Runden aus der Liste."""
        if self.shown is not None:
            self.start_session(self.shown.settings)

    def new_text_for_shown(self) -> None:
        if self.shown is not None:
            self.start_session(replace(self.shown.settings, seed=new_seed()))

    def _run(self, action) -> None:
        try:
            action()
        except (ValueError, TextLoadError) as exc:
            QMessageBox.warning(self, "Start nicht möglich", str(exc))
            self.show_menu()
            return
        self.stack.setCurrentWidget(self.typing)
        self.typing.begin()

    @property
    def penalty(self) -> int:
        return self.menu.highscores.penalty

    def on_finished(self) -> None:
        r = self.controller.result()
        when = datetime.now()
        when_str = when.strftime(history.DATE_FMT)
        banners: list[str] = []
        counts = history.should_save(r) and hs.eligible(r)
        before = hs.best_points(hs.load_attempts(self.history_file), r.text_names[0],
                                self.penalty) if counts else None
        prof = r.settings.profile
        prof_counts = history.should_save(r) and hs.profile_eligible(r)
        prof_before = hs.best_points(hs.load_profile_attempts(self.history_file), prof,
                                     self.penalty) if prof_counts else None

        csv_ok = history.append(r, self.history_file, when, self.penalty)
        # Statistik-Reiter: Texte und Zufällige Wörter, keine Phrasen, keine Abbrüche
        stats = None
        if history.should_save(r) and r.settings.source_mode is not SourceMode.PHRASES:
            stats = self.controller.typing_stats()
            self.stats_store.add(when.date(), stats)
        protected = self._protected()
        run_id = self.runs.save(r, when, protected, stats)
        run_ok = run_id is not None
        failed = history.should_save(r) and not (csv_ok and run_ok)
        self.menu.set_save_warning(
            "Letzte Runde konnte nicht vollständig gespeichert werden "
            f"(Datei geöffnet?):\n{self.history_file.parent}" if failed else "")

        now_pts = score(r.keystrokes, r.mistakes, r.duration_s, self.penalty)
        if counts and csv_ok:
            text = r.text_names[0]
            if before is None:
                banners.append(f"Erster Eintrag in der Bestenliste für {text}")
            elif now_pts > before:
                banners.append(f"Neuer Rekord für {text}!  (bisher {before:.0f} Punkte)")
                self.menu.highscores.highlight_when = when_str
            self.menu.highscores.select_text(text)
        if prof_counts and csv_ok:
            if prof_before is None:
                banners.append(f"Erster Eintrag für Profil „{prof}“")
            elif now_pts > prof_before:
                banners.append(f"Neuer Rekord im Profil „{prof}“!  (bisher {prof_before:.0f} Punkte)")
                self.menu.highscores.highlight_when = when_str
            self.menu.highscores.select_text(prof, profile=True)
            self.menu.progress.set_profiles(self.profiles.names(), select=prof)
        self.show_result(r, "      ".join(banners) or None, run_id, stats is not None, True)

    def show_result(self, r: SessionResult, banner: str | None = None,
                    run_id: str | None = None, has_stats: bool = False,
                    in_stats: bool = False) -> None:
        self.shown = r
        self.shown_run_id = run_id
        view = self.death if r.end_reason is SessionEnd.DIED else self.result
        view.set_stats_option(run_id is not None and has_stats, in_stats)
        self.stack.setCurrentWidget(view)
        if view is self.death:
            self.death.show_result(r)
        else:
            self.result.show_result(r, self.penalty, banner)

    def toggle_stats(self, include: bool) -> None:
        """Angezeigte Runde in die Statistik aufnehmen oder wieder herausrechnen."""
        run = self.runs.load(self.shown_run_id) if self.shown_run_id else None
        if run is None or run.stats is None or run.in_stats == include:
            return
        if self.stats_store.add(run.when.date(), run.stats, 1 if include else -1):
            self.runs.set_in_stats(run.id, include)

    # --- Highscores --------------------------------------------------------------------

    def open_attempt(self, when: str, text: str) -> None:
        run = self.runs.find_by_when(when, text)
        if run is None:
            QMessageBox.information(
                self, "Keine Auswertung gespeichert",
                "Für diese Runde gibt es keine gespeicherte Auswertung mehr – vermutlich "
                "stammt sie aus der Zeit vor der Highscore-Funktion.\n"
                "Die Kennzahlen in der Bestenliste bleiben trotzdem erhalten.")
            return
        records = hs.record_whens(hs.load_attempts(self.history_file), self.penalty)
        self.show_result(run.result, f"Rekord für {text}" if when in records else None,
                         run.id, run.stats is not None, run.in_stats)

    def open_profile_attempt(self, when: str, profile: str) -> None:
        run = self.runs.find_by_when(when, None)
        if run is None or run.result.settings.profile != profile:
            QMessageBox.information(self, "Keine Auswertung gespeichert",
                                    "Für diese Runde gibt es keine gespeicherte Auswertung mehr.\n"
                                    "Die Kennzahlen in der Bestenliste bleiben trotzdem erhalten.")
            return
        records = hs.record_whens(hs.load_profile_attempts(self.history_file), self.penalty)
        self.show_result(run.result, f"Rekord im Profil „{profile}“" if when in records else None,
                         run.id, run.stats is not None, run.in_stats)

    def _protected(self) -> set[str]:
        """Top 10 je Text und je Profil – deren Auswertungen werden nie aufgeräumt."""
        return (hs.protected_whens(hs.load_attempts(self.history_file), self.penalty)
                | hs.protected_whens(hs.load_profile_attempts(self.history_file), self.penalty))

    # --- Einstellungen ---------------------------------------------------------------

    def apply_appearance(self) -> None:
        """Design, Schriftgrößen und Tempo-Cursor aus den Einstellungen übernehmen."""
        s = self.settings
        theme.set_theme(s.design)
        scale = s.ui_scale / 100
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.load_stylesheet(scale))
        self.typing.display.set_font_size(s.text_size)
        self.typing.display.pace_cpm = s.pace_cpm if s.pace_on else None
        self.result.text_pt = max(10, round(14 * scale))

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dlg.save()
            self.apply_appearance()
            self.show_menu()              # Listen und Diagramme in neuen Farben neu aufbauen

    def set_unit(self, unit: str) -> None:
        units.set_unit(unit)
        self.settings.unit = units.unit()
        combo = self.menu.unit_combo
        combo.blockSignals(True)
        combo.setCurrentText(units.unit())
        combo.blockSignals(False)
        self.show_menu()                     # alle Listen in der neuen Einheit neu aufbauen

    def set_penalty(self, value: int) -> None:
        self.settings.penalty = value
        self._refresh_runs()

    def _refresh_runs(self) -> None:
        attempts = hs.load_attempts(self.history_file)
        records = (hs.record_whens(attempts, self.penalty)
                   | hs.record_whens(hs.load_profile_attempts(self.history_file), self.penalty))
        self.menu.set_runs(self.runs.list_runs(), self.penalty, records)
        return attempts

    # --- Liste „Letzte Runden“ ------------------------------------------------------

    def open_run(self, run_id: str) -> None:
        run = self.runs.load(run_id)
        if run is None:
            QMessageBox.warning(self, "Runde nicht gefunden",
                                "Diese Runde konnte nicht geladen werden.")
            self.show_menu()
            return
        self.show_result(run.result, None, run.id, run.stats is not None, run.in_stats)

    def pin_run(self, run_id: str, pinned: bool) -> None:
        if not self.runs.set_pinned(run_id, pinned):
            QMessageBox.warning(self, "Speichern fehlgeschlagen",
                                "Die Markierung konnte nicht gespeichert werden.")
            self.show_menu()

    def show_menu(self) -> None:
        # Textordner neu einlesen, damit neu abgelegte Dateien sofort erscheinen
        if self._reload_library:
            self.library = TextLibrary.load()
            self.controller.library = self.library
            self.menu.set_library(self.library)
        attempts = self._refresh_runs()
        self.menu.stats.refresh()
        names = self.profiles.names()
        self.menu.highscores.set_data(attempts, [t.name for t in self.library.texts],
                                      hs.load_profile_attempts(self.history_file), names)
        self.menu.progress.set_profiles(names)
        self.stack.setCurrentWidget(self.menu)
        self.menu.setFocus()
