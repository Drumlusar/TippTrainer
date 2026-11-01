"""Fortschrittskurve je Profil und Einheiten-Umrechnung."""
from datetime import date, datetime

from core.models import InputMode, SessionEnd, SessionResult, SessionSettings, SourceMode
from storage import history
from storage.progress import Run, daily, profile_progress
from ui import units


def _result(profile: str, keystrokes: int = 300, errors: int = 3) -> SessionResult:
    s = SessionSettings(SourceMode.RANDOM_WORDS, 60, 50, None, InputMode.COMPUTER,
                        False, False, 1, profile=profile)
    return SessionResult(settings=s, text_names=["englisch_200.txt"], end_reason=SessionEnd.TIME_UP,
                         duration_s=60.0, keystrokes=keystrokes, typed_chars=keystrokes,
                         errors=errors, mistakes=errors, cpm_avg=float(keystrokes), cpm_peak=400.0,
                         cpm_series=[], error_times_s=[], target_text="", char_states=[])


def test_daily_means_and_rolling_window():
    runs = [Run(date(2026, 10, 1), 200, 2.0, 80), Run(date(2026, 10, 1), 220, 4.0, None),
            Run(date(2026, 10, 5), 260, 1.0, 90), Run(date(2026, 10, 9), 300, 1.0, None)]
    pts = daily(runs)
    assert [p.day.day for p in pts] == [1, 5, 9]
    assert pts[0].runs == 2 and pts[0].net_cpm == 210 and pts[0].error_rate == 3.0
    assert pts[0].consistency == 80                      # nur Runden mit Wert
    assert pts[1].net_cpm_7d == (200 + 220 + 260) / 3      # 1.–5. Oktober
    # 9. Oktober: Fenster 3.–9. -> der 1. fällt heraus
    assert pts[2].net_cpm_7d == (260 + 300) / 2
    assert pts[2].consistency is None


def test_profile_progress_reads_only_that_profile(tmp_path):
    csv = tmp_path / "s.csv"
    history.append(_result("A"), csv, datetime(2026, 10, 1, 10))
    history.append(_result("A", 360), csv, datetime(2026, 10, 2, 10))
    history.append(_result("B"), csv, datetime(2026, 10, 2, 11))
    history.append(_result(""), csv, datetime(2026, 10, 2, 12))
    pts = profile_progress("A", csv)
    assert len(pts) == 2 and sum(p.runs for p in pts) == 2
    assert profile_progress("C", csv) == []


def test_units():
    units.set_unit("W/min")
    try:
        assert units.conv(300) == 60 and units.fmt(300, with_unit=True) == "60 W/min"
        assert units.fmt(300, "A/min") == "300" and units.other() == "A/min"
        assert units.fmt(None) == "–"
    finally:
        units.set_unit("A/min")
    units.set_unit("Unsinn")
    assert units.unit() == "A/min"


def test_training_tab_profile_roundtrip(tmp_path):
    """Profil laden -> Bedienelemente -> current_settings ergibt wieder genau dieses Profil."""
    import os

    import pytest
    pytest.importorskip("PySide6")          # wie die anderen UI-Tests: ohne PySide6 überspringen
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from core.text_source import TextLibrary
    from storage.profiles import DEFAULT_PROFILES, ProfileStore
    from ui.training_tab import TrainingTab
    app = QApplication.instance() or QApplication([])  # noqa: F841
    store = ProfileStore(tmp_path / "p.json")
    tab = TrainingTab(TextLibrary.load(), store)
    for name, _ in DEFAULT_PROFILES:
        tab.apply_settings(store.get(name))
        assert store.matching(tab.current_settings()) == name
        assert tab.profile_combo.currentText() == name
    tab.death_check.setChecked(not tab.death_check.isChecked())   # Abweichung -> kein Profil
    assert store.matching(tab.current_settings()) == ""
    assert tab.profile_combo.currentIndex() == 0


def test_darstellungs_einstellungen(tmp_path):
    from storage.app_settings import AppSettings
    s = AppSettings(tmp_path / "e.json")
    assert (s.design, s.text_size, s.ui_scale, s.pace_on, s.pace_cpm) == ("Dunkel", 26, 100, False, 500.0)
    s.design, s.text_size, s.ui_scale, s.pace_on, s.pace_cpm = "Hell", 99, 10, True, 300
    s2 = AppSettings(tmp_path / "e.json")
    assert (s2.design, s2.text_size, s2.ui_scale, s2.pace_on, s2.pace_cpm) == ("Hell", 60, 80, True, 300.0)
    s.set("design", "Lila")
    assert s.design == "Dunkel"


def test_stylesheet_beide_designs_vollstaendig():
    """Kein Platzhalter (@name) bleibt übrig; Schriftgrößen werden skaliert."""
    import re
    import pytest
    pytest.importorskip("PySide6")
    from ui import theme
    try:
        for name in theme.THEMES:
            theme.set_theme(name)
            qss = theme.load_stylesheet(1.5)
            assert not re.search(r"@[a-z_]+", qss), name
            assert theme.hexc("bg") in qss
            assert "font-size: 51px" in qss          # Titel 34 px × 1,5
    finally:
        theme.set_theme(theme.DARK)
