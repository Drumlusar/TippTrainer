"""Benannte Tastaturen: Verwaltung, Zuordnung der Runden, getrennte Statistik und Filter."""
import json
from dataclasses import replace
from datetime import date, datetime

from core import char_stats as cs
from core.models import InputMode, SessionEnd, SessionResult, SessionSettings, SourceMode
from storage import highscores as hs
from storage import history
from storage.app_settings import AppSettings
from storage.keyboards import DEFAULT_ID, KeyboardStore
from storage.profiles import ProfileStore
from storage.progress import profile_progress
from storage.stats_store import StatsStore


def test_standard_tastatur_und_verwaltung(tmp_path):
    s = AppSettings(tmp_path / "e.json")
    s.keyboard_layout = "dvorak"                       # Layout aus der Zeit vor den Tastaturen
    kbs = KeyboardStore(s)
    assert [(k.id, k.name, k.layout) for k in kbs.all()] == [(DEFAULT_ID, "Standard", "dvorak")]
    assert kbs.active().id == DEFAULT_ID
    new = kbs.add("Keychron", "qwerty")
    assert kbs.set_active(new) and kbs.active().name == "Keychron"
    kbs.update(DEFAULT_ID, name="MacBook", layout="qwertz")
    assert kbs.name_of("") == "MacBook"                # ältere Runden -> erste Tastatur
    assert kbs.name_taken("macbook") and not kbs.name_taken("macbook", DEFAULT_ID)
    assert not kbs.can_delete(DEFAULT_ID)
    assert kbs.delete(new) and kbs.active().id == DEFAULT_ID
    assert kbs.name_of(new) == "gelöschte Tastatur"
    assert KeyboardStore(AppSettings(tmp_path / "e.json")).all()[0].name == "MacBook"


def test_statistik_je_tastatur_und_altes_format(tmp_path):
    p = tmp_path / "st.json"
    alt = cs.Stats(chars={"a": [10, 1, 1000, 9]})
    p.write_text(json.dumps({"version": 1, "tage": {"2026-11-01": alt.to_json()}}), encoding="utf-8")
    store = StatsStore(p)
    today = date(2026, 11, 2)
    assert store.load(None, today, keyboard=DEFAULT_ID).chars["a"] == [10, 1, 1000, 9]
    store.add(date(2026, 11, 2), cs.Stats(chars={"a": [5, 0, 500, 5]}), keyboard="tastatur1")
    assert store.load(None, today, keyboard="tastatur1").chars["a"] == [5, 0, 500, 5]
    assert store.load(None, today, keyboard=DEFAULT_ID).chars["a"] == [10, 1, 1000, 9]
    assert store.load(None, today).chars["a"] == [15, 1, 1500, 14]          # alle zusammen
    assert json.loads(p.read_text(encoding="utf-8"))["version"] == 2
    store.add(date(2026, 11, 2), cs.Stats(chars={"a": [5, 0, 500, 5]}), -1, keyboard="tastatur1")
    assert store.load(None, today, keyboard="tastatur1").chars == {}


def _result(keyboard: str, keystrokes: int = 300) -> SessionResult:
    s = SessionSettings(SourceMode.RANDOM_WORDS, 60, 50, None, InputMode.COMPUTER, False, False, 1,
                        profile="P", keyboard=keyboard)
    return SessionResult(settings=s, text_names=["w.txt"], end_reason=SessionEnd.TIME_UP,
                         duration_s=60.0, keystrokes=keystrokes, typed_chars=keystrokes,
                         errors=1, mistakes=1, cpm_avg=float(keystrokes), cpm_peak=400.0,
                         target_text="", char_states=[])


def test_highscores_und_fortschritt_filtern(tmp_path):
    csv = tmp_path / "s.csv"
    history.append(_result(""), csv, datetime(2026, 11, 1, 10))          # ältere Runde
    history.append(_result("tastatur1", 400), csv, datetime(2026, 11, 2, 10))
    att = hs.load_profile_attempts(csv)
    assert {a.keyboard for a in att} == {DEFAULT_ID, "tastatur1"}
    assert len(hs.filter_attempts(att, keyboard="tastatur1")) == 1
    assert len(hs.filter_attempts(att, keyboard=None)) == 2
    assert len(profile_progress("P", csv, "tastatur1")) == 1
    assert len(profile_progress("P", csv)) == 2


def test_profil_haengt_nicht_an_der_tastatur(tmp_path):
    store = ProfileStore(tmp_path / "p.json")
    s = SessionSettings(SourceMode.RANDOM_WORDS, 30, 50, None, InputMode.COMPUTER, False, False, 0)
    store.save("Mein Test", s)
    assert store.matching(replace(s, keyboard="tastatur1")) == "Mein Test"
