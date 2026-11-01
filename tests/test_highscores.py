from datetime import datetime, timedelta

import pytest

from core.models import (CharState, InputMode, SessionEnd, SessionResult,
                         SessionSettings, SourceMode)
from core.scoring import score
from storage import highscores as hs
from storage import history
from storage.run_store import RunStore

T = datetime(2026, 11, 1, 13, 0, 0)


# --- Punkte ----------------------------------------------------------------------

def test_punkte_beispiel():
    assert score(300, 10, 60.0, penalty=10) == pytest.approx(200)


def test_keine_minuspunkte():
    assert score(50, 20, 60.0, penalty=10) == 0.0


def test_strafe_null_ist_brutto():
    assert score(300, 10, 60.0, penalty=0) == pytest.approx(300)


# --- Welche Runden zählen? -----------------------------------------------------------

def result(source=SourceMode.SPECIFIC_TEXT, time_limit=None, end=SessionEnd.COMPLETED,
           names=("a.txt",), keystrokes=300, errors=2, mistakes=5, dur=60.0,
           mode=InputMode.COMPUTER, dbm=False):
    s = SessionSettings(source, time_limit, 50, None, mode, dbm, False, 1)
    return SessionResult(s, end, list(names), "x", [CharState.CORRECT], dur, keystrokes,
                         errors, mistakes, keystrokes / dur * 60, 0.0, typed_chars=keystrokes)


@pytest.mark.parametrize("r, zaehlt", [
    (result(), True),
    (result(source=SourceMode.RANDOM_TEXT), True),
    (result(dbm=True), True),                                   # überlebt
    (result(dbm=True, end=SessionEnd.DIED), False),
    (result(time_limit=60), False),
    (result(names=("a.txt", "b.txt")), False),
    (result(source=SourceMode.RANDOM_WORDS, names=("deutsch.txt",)), False),
    (result(source=SourceMode.PHRASES, names=("Umlaute",)), False),
])
def test_zaehlt(r, zaehlt):
    assert hs.eligible(r) is zaehlt


# --- Auswertung aus der CSV --------------------------------------------------------

@pytest.fixture
def csv(tmp_path):
    p = tmp_path / "s.csv"
    runs = [
        (result(names=("a.txt",), keystrokes=300, errors=0, mistakes=10), 0),   # 200 P
        (result(names=("a.txt",), keystrokes=280, errors=0, mistakes=0), 1),    # 280 P
        (result(names=("a.txt",), keystrokes=320, errors=2, mistakes=4,
                mode=InputMode.TYPEWRITER), 2),                                  # 280 P (später)
        (result(names=("b.txt",), keystrokes=200, errors=1, mistakes=1, dbm=True), 3),  # 190 P
        (result(names=("b.txt",), time_limit=60), 4),                            # zählt nicht
    ]
    for r, minute in runs:
        history.append(r, p, T + timedelta(minutes=minute))
    return p


def test_versuche_und_mistakes(csv):
    att = hs.load_attempts(csv)
    assert len(att) == 4
    assert att[0].mistakes == 10 and att[2].mistakes == 4


def test_rangliste_gleichstand_frueherer_gewinnt(csv):
    top = hs.top(hs.load_attempts(csv), "a.txt", penalty=10)
    assert [round(a.points(10)) for a in top] == [280, 280, 200]
    assert top[0].input_mode == "Computer"


def test_strafe_aendert_reihenfolge(csv):
    top = hs.top(hs.load_attempts(csv), "a.txt", penalty=0)
    assert top[0].keystrokes == 320


def test_filter(csv):
    att = hs.load_attempts(csv)
    assert len(hs.filter_attempts(att, input_mode="Schreibmaschine")) == 1
    assert len(hs.filter_attempts(att, dbm=True)) == 1
    assert len(hs.filter_attempts(att, dbm=False)) == 3


def test_uebersicht_enthaelt_auch_ungeuebte_texte(csv):
    rows = hs.summarize(hs.load_attempts(csv), 10, text_names=["a.txt", "neu.txt"])
    by = {r.text: r for r in rows}
    assert set(by) == {"a.txt", "neu.txt", "b.txt"}
    assert by["neu.txt"].best is None and by["neu.txt"].attempts == 0
    assert by["a.txt"].attempts == 3
    assert by["a.txt"].last == "2026-11-01 13:02:00"


def test_rekorde_und_geschuetzte(csv):
    att = hs.load_attempts(csv)
    assert hs.record_whens(att, 10) == {"2026-11-01 13:01:00", "2026-11-01 13:03:00"}
    assert hs.best_points(att, "a.txt", 10) == pytest.approx(280)
    assert hs.best_points(att, "neu.txt", 10) is None
    assert len(hs.protected_whens(att, 10, n=2)) == 3      # 2 von a.txt + 1 von b.txt


def test_highscore_auswertung_wird_nicht_aufgeraeumt(tmp_path):
    store = RunStore(tmp_path, keep_recent=2)
    first = T
    store.save(result(), first)
    protected = {first.strftime("%Y-%m-%d %H:%M:%S")}
    for i in range(1, 5):
        store.save(result(), T + timedelta(minutes=i), protected)
    whens = {r.when for r in store.list_runs()}
    assert first in whens and len(whens) == 3
    assert store.find_by_when("2026-11-01 13:00:00", "a.txt") is not None
