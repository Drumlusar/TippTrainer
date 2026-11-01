import random

import pytest

from core.models import (CharState, InputMode, KeyOutcome, SessionEnd,
                         SessionSettings, SourceMode)
from core.session import SessionController, SessionState
from core.text_source import PhraseSource, TextLibrary, parse_phrases

T0 = 100.0


def settings(phrases=("ab", "cd"), reps=2, shuffle=False, restart=False, death=False,
             mode=InputMode.COMPUTER, seed=1):
    return SessionSettings(SourceMode.PHRASES, None, 0, None, mode, death, False, seed,
                           phrases=tuple(phrases), repetitions=reps, shuffle=shuffle,
                           restart_phrase_on_error=restart, phrase_set_name="Test")


def make(**kw):
    c = SessionController(TextLibrary(), clock=lambda: pytest.fail("now fehlt"))
    c.start(settings(**kw))
    return c


def tippe(c, text, t=T0, schritt=1.0):
    for ch in text:
        if ch == "⌫":
            c.on_backspace(now=t)
        else:
            c.on_char(ch, now=t)
        t += schritt
    return t


# --- Text aus Phrasen ------------------------------------------------------------------

def test_phrasen_parsen():
    assert parse_phrases("  Haus \n\n„Tür“\n  \nß", False) == ["Haus", '"Tür"', "ß"]


def test_feste_durchgaenge_der_reihe_nach():
    c = make(phrases=("ab", "cd"), reps=3)
    assert c.engine.target == "ab\ncd\nab\ncd\nab\ncd"


def test_eine_zeile_wird_als_block_wiederholt():
    c = make(phrases=("Hallo Welt",), reps=3)
    assert c.engine.target == "Hallo Welt\nHallo Welt\nHallo Welt"


def test_gemischt_jeder_durchgang_alle_phrasen_und_keine_doppelung_an_grenze():
    src = PhraseSource(["a", "b", "c", "d"], "t", random.Random(4), shuffle=True)
    vorher = None
    for _ in range(200):
        chunk = src.next_chunk()
        assert sorted(chunk.parts) == [0, 1, 2, 3]
        assert chunk.parts[0] != vorher
        vorher = chunk.parts[-1]


def test_gleicher_seed_gleiche_mischung():
    a = make(phrases=("a", "b", "c", "d"), reps=5, shuffle=True, seed=9).engine.target
    b = make(phrases=("a", "b", "c", "d"), reps=5, shuffle=True, seed=9).engine.target
    assert a == b


def test_leere_phrasen_nicht_moeglich():
    c = SessionController(TextLibrary())
    with pytest.raises(ValueError):
        c.start(settings(phrases=("", "  ")))


# --- Ende ---------------------------------------------------------------------------------

def test_feste_durchgaenge_enden_nach_letztem_zeichen():
    c = make(phrases=("ab",), reps=2)
    tippe(c, "ab\nab")
    assert c.end_reason is SessionEnd.COMPLETED


def test_unendlich_wird_nachgeladen_und_esc_beendet_mit_auswertung():
    c = make(phrases=("ab",), reps=None)
    t = tippe(c, "ab\n" * 30)                     # 90 Zeichen, weit über den ersten Puffer
    assert c.state is SessionState.RUNNING
    assert c.can_stop
    c.stop(now=t)
    r = c.result()
    assert r.end_reason is SessionEnd.STOPPED
    assert r.target_text == "ab\n" * 30           # nur der getippte Teil
    assert r.progress is None


def test_unendlich_vor_erstem_anschlag_kein_beenden():
    c = make(phrases=("ab",), reps=None)
    assert not c.can_stop


def test_feste_durchgaenge_esc_ist_abbruch():
    c = make(phrases=("ab",), reps=3)
    tippe(c, "a")
    assert not c.can_stop


def test_durchgang_anzeige():
    c = make(phrases=("ab", "cd"), reps=3)
    assert c.phrase_round == (1, 3)
    tippe(c, "ab\ncd\n")
    assert c.phrase_round == (2, 3)


# --- Bei Fehler Phrase neu ------------------------------------------------------------------

def test_fehler_setzt_auf_phrasenanfang_zurueck():
    c = make(phrases=("abc", "de"), reps=1, restart=True)
    tippe(c, "abc\nd")          # mitten in der zweiten Phrase
    assert c.engine.pos == 5
    c.on_char("x", now=T0 + 10)
    assert c.engine.pos == 4    # zurück an den Anfang von „de“
    assert c.engine.states[4] is CharState.PENDING
    assert c.engine.mistakes == 1 and c.engine.errors == 0
    assert c.state is SessionState.RUNNING


def test_falsches_enter_gehoert_zur_vorigen_phrase():
    c = make(phrases=("ab", "cd"), reps=1, restart=True)
    tippe(c, "ab ")             # Leerzeichen statt Enter
    assert c.engine.pos == 0    # „ab“ muss neu getippt werden


def test_neu_beginnen_danach_richtig_ist_korrigiert():
    c = make(phrases=("ab",), reps=1, restart=True)
    tippe(c, "xab")
    r = c.result()
    assert r.end_reason is SessionEnd.COMPLETED
    assert r.char_states[0] is CharState.CORRECTED


def test_death_by_mistake_hat_vorrang():
    c = make(phrases=("ab",), reps=2, restart=True, death=True)
    assert c.on_char("x", now=T0) is KeyOutcome.WRONG
    assert c.end_reason is SessionEnd.DIED


# --- Auswertung je Phrase -----------------------------------------------------------------

def test_statistik_je_phrase():
    c = make(phrases=("ab", "xyz"), reps=2)
    # 1 Zeichen pro Sekunde; in „xyz“ ein Tippfehler (wird nicht korrigiert)
    tippe(c, "ab\n" + "xqz\n" + "ab\n" + "xyz")
    stats = {s.phrase: s for s in c.result().phrase_stats}
    assert stats["ab"].reps == 2 and stats["xyz"].reps == 2
    assert stats["xyz"].mistakes == 1 and stats["ab"].mistakes == 0
    # „ab\\n“: 3 Anschläge; Zeit vom Enter davor bis zum eigenen Enter = 3 s
    # (erster Durchgang ab Startzeit: nur 2 s, weil der erste Anschlag den Start setzt)
    assert stats["ab"].keystrokes == 6
    assert stats["ab"].duration_s == pytest.approx(2 + 3)
    assert stats["xyz"].cpm == pytest.approx(7 / 7 * 60)   # „xqz\\n“ + „xyz“ = 7 in 7 s


def test_statistik_unvollstaendige_phrase_zaehlt_nur_fehler():
    c = make(phrases=("ab", "cd"), reps=1)
    tippe(c, "ab\nx")
    c.abort(now=T0 + 10)
    stats = {s.phrase: s for s in c.result().phrase_stats}
    assert stats["cd"].reps == 0 and stats["cd"].mistakes == 1


def test_netto_apm():
    c = make(phrases=("abcd",), reps=1, mode=InputMode.TYPEWRITER)
    tippe(c, "abxd")            # 4 Zeichen in 3 s, davon 1 falsch
    r = c.result()
    assert r.cpm_avg == pytest.approx(4 / 3 * 60)
    assert r.net_cpm == pytest.approx(3 / 3 * 60)
