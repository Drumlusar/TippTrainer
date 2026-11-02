from datetime import date

import pytest

from core import char_stats as cs
from core.models import InputMode, SessionSettings, SourceMode
from core.session import SessionController
from core.text_source import RawText, TextLibrary
from storage.stats_store import StatsStore

T0 = 10.0


def session(text, mode=InputMode.COMPUTER):
    c = SessionController(TextLibrary(texts=[RawText("t.txt", text)]),
                          clock=lambda: pytest.fail("now fehlt"))
    c.start(SessionSettings(SourceMode.RANDOM_TEXT, None, 0, None, mode, False, False, 1))
    return c


def tippe(c, folge):
    """folge: Liste aus (Zeichen, Sekunde); ⌫ = Backspace."""
    for ch, t in folge:
        c.on_backspace(now=T0 + t) if ch == "⌫" else c.on_char(ch, now=T0 + t)


# --- Wörter ----------------------------------------------------------------------------

def test_woerter_mit_satzzeichen_und_fehlern():
    text = "Haus, Baum und (Tür)."
    # Fehler an Position 6 („B“) und 19 („)“ – Satzzeichen zählt nicht zum Wort)
    words = cs.words_with_mistakes(text, len(text), {6: 1, 19: 1})
    assert words == [("Haus", False), ("Baum", True), ("und", False), ("Tür", False)]


def test_abgeschnittenes_wort_zaehlt_nicht():
    assert cs.words_with_mistakes("Haus Baum", 7, {}) == [("Haus", False)]


def test_zahlen_allein_sind_kein_wort():
    assert cs.words_with_mistakes("um 12 Uhr", 9, {}) == [("um", False), ("Uhr", False)]


# --- Erfassung in der Session --------------------------------------------------------------

def test_protokoll_tempo_und_verwechslung():
    c = session("Haus")
    tippe(c, [("H", 0), ("a", 0.2), ("i", 0.5), ("⌫", 0.7), ("u", 0.9), ("s", 4.0)])
    st = c.typing_stats()
    assert st.chars["a"] == [1, 0, 200, 1]
    assert st.chars["u"] == [2, 1, 200, 1]          # 1× falsch (i), 1× richtig 0,2 s nach ⌫
    assert st.chars["s"] == [1, 0, 0, 0]            # 3,1 s Pause -> kein Tempowert
    assert st.chars["H"] == [1, 0, 0, 0]            # erster Anschlag: kein Abstand
    assert st.confusions == {"u": {"i": 1}}
    assert st.words == {"Haus": [1, 1]}


def test_gross_und_klein_getrennt():
    c = session("Aa")
    tippe(c, [("a", 0), ("a", 0.3)])
    st = c.typing_stats()
    assert st.chars["A"] == [1, 1, 0, 0] and st.chars["a"] == [1, 0, 300, 1]
    upper, lower = cs.case_summary(st)
    assert upper.error_rate == 100 and lower.error_rate == 0


# --- Auswertung -----------------------------------------------------------------------------

def stats():
    return cs.Stats(
        chars={"e": [100, 2, 9000, 90], "ß": [30, 6, 6000, 20], "q": [5, 5, 0, 0],
               "E": [20, 4, 6000, 15], "?": [20, 1, 500, 2]},
        confusions={"e": {"r": 2}, "ß": {"s": 5, "ü": 1}},
        words={"Größe": [4, 3], "Haus": [10, 0], "quer": [2, 1]})


def test_zeichen_rangliste_mit_mindestanzahl():
    rows = cs.char_rows(stats(), min_keys=20)
    assert [r.char for r in rows] == ["ß", "E", "?", "e"]       # q hat zu wenig Anschläge
    avg = cs.overall_avg_ms(stats())                              # 21500 ms / 127
    ss = next(r for r in rows if r.char == "ß")
    assert ss.avg_ms == 300
    assert cs.slower_pct(ss, avg) == pytest.approx((300 / (21500 / 127) - 1) * 100)


def test_verwechslungen_und_woerter():
    assert cs.confusion_rows(stats())[0] == ("ß", "s", 5)
    assert [w[0] for w in cs.word_rows(stats())] == ["Größe", "quer"]   # „Haus“ ohne Fehler fehlt


def test_tasten_fassen_gross_klein_und_shift_zusammen():
    keys = cs.key_rows(stats())
    assert keys["e"].keys == 120 and keys["e"].mistakes == 6
    assert keys["ß"].keys == 50                                   # ß + ? (Shift+ß)


# --- Speicher ----------------------------------------------------------------------------------

def test_speichern_und_zeitraum(tmp_path):
    store = StatsStore(tmp_path / "s.json")
    store.add(date(2026, 10, 1), cs.Stats(chars={"a": [10, 1, 1000, 9]}))
    store.add(date(2026, 11, 1), cs.Stats(chars={"a": [5, 0, 500, 5]}, words={"Haus": [1, 0]}))
    store.add(date(2026, 11, 1), cs.Stats(chars={"a": [5, 2, 0, 0]}, words={"Haus": [1, 1]}))
    today = date(2026, 11, 1)
    assert store.load(7, today).chars["a"] == [10, 2, 500, 5]
    assert store.load(None, today).chars["a"] == [20, 3, 1500, 14]
    assert store.load(7, today).words["Haus"] == [2, 1]


def test_kaputte_statistikdatei(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{kaputt", encoding="utf-8")
    store = StatsStore(p)
    assert store.load().chars == {}
    assert store.add(date(2026, 11, 1), cs.Stats(chars={"a": [1, 0, 0, 0]}))


# --- Runden aus der Statistik nehmen ------------------------------------------------------

def test_runde_herausrechnen_und_wieder_aufnehmen(tmp_path):
    store = StatsStore(tmp_path / "s.json")
    day = date(2026, 11, 1)
    a = cs.Stats(chars={"a": [10, 1, 900, 9]}, confusions={"a": {"s": 1}}, words={"Haus": [2, 1]})
    b = cs.Stats(chars={"a": [5, 2, 300, 3], "ß": [4, 4, 0, 0]}, confusions={"ß": {"s": 4}},
                 words={"Größe": [1, 1]})
    store.add(day, a)
    store.add(day, b)
    store.add(day, b, sign=-1)                       # Runde b ausschließen
    st = store.load(None, day)
    assert st.chars == {"a": [10, 1, 900, 9]}        # ß ganz verschwunden, nicht [0,0,0,0]
    assert st.confusions == {"a": {"s": 1}}
    assert st.words == {"Haus": [2, 1]}
    store.add(day, b)                                # wieder aufnehmen
    assert store.load(None, day).chars["ß"] == [4, 4, 0, 0]


def test_runde_merkt_sich_ihren_statistikbeitrag(tmp_path):
    from datetime import datetime
    from core.models import CharState, SessionEnd, SessionResult
    from storage.run_store import RunStore
    s = SessionSettings(SourceMode.RANDOM_TEXT, None, 0, None, InputMode.COMPUTER, False, False, 1)
    r = SessionResult(s, SessionEnd.COMPLETED, ["t.txt"], "ab", [CharState.CORRECT] * 2,
                      1.0, 2, 0, 0, 120.0, 120.0, typed_chars=2)
    store = RunStore(tmp_path)
    st = cs.Stats(chars={"a": [1, 0, 100, 1]})
    with_stats = store.save(r, datetime(2026, 11, 1, 15, 0), stats=st)
    without = store.save(r, datetime(2026, 11, 1, 15, 1))
    run = store.load(with_stats)
    assert run.stats == st and run.in_stats is True
    assert store.load(without).stats is None and store.load(without).in_stats is False
    store.set_in_stats(with_stats, False)
    assert store.load(with_stats).in_stats is False


def test_tasten_je_layout():
    from core.keyboard_layout import LAYOUTS
    keys = cs.key_rows(stats(), LAYOUTS["qwerty"])
    assert keys["e"].keys == 120
    assert "ß" not in keys                    # gibt es auf QWERTY nicht -> nicht angezeigt
