import pytest

import config
from core.models import (CharState, InputMode, KeyOutcome, SessionEnd,
                         SessionSettings, SourceMode)
from core.session import SessionController, SessionState
from core.text_source import RawText, TextLibrary

T0 = 500.0


def make(mode=SourceMode.RANDOM_TEXT, time_limit=None, death=False,
         input_mode=InputMode.COMPUTER, texts=None, words=None, seed=7, word_count=5):
    lib = TextLibrary(texts=texts or [RawText("a.txt", "Haus")],
                      words=words or ["eins", "zwei", "drei", "vier"],
                      wordlist_name="w.txt")
    s = SessionSettings(mode, time_limit, word_count, None, input_mode, death, False, seed)
    c = SessionController(lib, clock=lambda: pytest.fail("Tests müssen 'now' übergeben"))
    c.start(s)
    return c


def tippe(c, text, t_start=T0, schritt=0.25):
    """Text eintippen, ein Zeichen pro `schritt` Sekunden; ⌫ = Backspace. Gibt Endzeit zurück."""
    t = t_start
    for ch in text:
        if ch == "⌫":
            c.on_backspace(now=t)
        else:
            c.on_char(ch, now=t)
        t += schritt
    return t


# --- Ohne Zeitlimit ----------------------------------------------------------------

def test_zeit_startet_mit_erstem_anschlag():
    c = make()
    assert c.state is SessionState.WAITING
    c.tick(now=T0 + 100)                       # lange gewartet, nichts getippt
    assert c.elapsed(now=T0 + 100) == 0.0
    c.on_char("H", now=T0 + 100)
    assert c.state is SessionState.RUNNING
    assert c.elapsed(now=T0 + 101) == pytest.approx(1.0)


def test_text_fertig_beendet_runde():
    c = make()
    tippe(c, "Haus")                           # 4 Zeichen bei 0, 0.25, 0.5, 0.75 s
    assert c.state is SessionState.ENDED
    r = c.result()
    assert r.end_reason is SessionEnd.COMPLETED
    assert r.duration_s == pytest.approx(0.75)
    assert r.keystrokes == 4 and r.errors == 0
    assert r.text_names == ["a.txt"]


def test_letztes_zeichen_falsch_beendet_trotzdem():
    c = make()
    tippe(c, "Haux")
    assert c.result().end_reason is SessionEnd.COMPLETED
    assert c.result().errors == 1


def test_eingabe_nach_ende_ignoriert():
    c = make()
    t = tippe(c, "Haus")
    assert c.on_char("x", now=t) is KeyOutcome.IGNORED
    assert c.result().keystrokes == 4


def test_ergebnis_vor_ende_nicht_moeglich():
    c = make()
    tippe(c, "Ha")
    with pytest.raises(RuntimeError):
        c.result()


def test_fortschritt():
    c = make()
    tippe(c, "Ha")
    assert c.progress == 0.5


# --- Death by Mistake --------------------------------------------------------------

def test_death_by_mistake():
    c = make(death=True)
    tippe(c, "Hax")
    assert c.state is SessionState.ENDED
    r = c.result()
    assert r.end_reason is SessionEnd.DIED
    assert (c.last_error.expected, c.last_error.typed) == ("u", "x")
    assert r.keystrokes == 3


def test_death_im_computermodus_keine_korrektur_moeglich():
    c = make(death=True, input_mode=InputMode.COMPUTER)
    t = tippe(c, "Hax")
    assert c.on_backspace(now=t) is False


def test_neustart_gleicher_text_frische_werte():
    c = make(mode=SourceMode.RANDOM_WORDS, death=True, seed=123)
    erster_text = c.engine.target
    c.on_char("#", now=T0)                     # sofort tot
    assert c.end_reason is SessionEnd.DIED
    c.restart()
    assert c.state is SessionState.WAITING
    assert c.engine.target == erster_text
    assert c.engine.errors == 0 and c.metrics.keystrokes == 0


def test_neuer_text_neuer_seed():
    c = make(mode=SourceMode.RANDOM_WORDS, seed=123, word_count=30)
    alt = c.settings.seed
    c.new_text()
    assert c.settings.seed != alt


# --- Eingabemodi ----------------------------------------------------------------------

def test_backspace_vor_erstem_anschlag_wirkungslos():
    c = make()
    assert c.on_backspace(now=T0) is False
    assert c.state is SessionState.WAITING


def test_schreibmaschine_ohne_backspace():
    c = make(input_mode=InputMode.TYPEWRITER)
    t = tippe(c, "Hx")
    assert c.on_backspace(now=t) is False
    assert c.engine.pos == 2


def test_computer_mit_backspace():
    c = make()
    tippe(c, "Hx⌫aus")
    r = c.result()
    assert r.errors == 0 and r.mistakes == 1
    assert r.char_states[1] is CharState.CORRECTED


# --- Zeitlimit -------------------------------------------------------------------------

def test_zeitlimit_puffer_wird_aufgefuellt():
    c = make(time_limit=60)
    assert c.engine.remaining >= config.REFILL_THRESHOLD_CHARS
    tippe(c, c.engine.target[:40], schritt=0.1)
    assert c.engine.remaining >= config.REFILL_THRESHOLD_CHARS


def test_zeitlimit_texte_mit_enter_getrennt():
    texts = [RawText("a.txt", "Haus"), RawText("b.txt", "Baum")]
    c = make(time_limit=60, texts=texts)
    assert c.engine.target.startswith(("Haus\nBaum\nHaus", "Baum\nHaus\nBaum"))


def test_zeitlimit_endet_per_tick():
    c = make(time_limit=10)
    tippe(c, c.engine.target[:20])             # 20 Zeichen in 5 s
    c.tick(now=T0 + 9.9)
    assert c.state is SessionState.RUNNING
    c.tick(now=T0 + 10.05)
    assert c.state is SessionState.ENDED
    r = c.result()
    assert r.end_reason is SessionEnd.TIME_UP
    assert r.duration_s == pytest.approx(10.0)   # exakt die Frist, nicht 10.05
    assert r.cpm_avg == pytest.approx(120)       # 20 Anschläge / 10 s
    assert len(r.cpm_series) == 10


def test_zeitlimit_anschlag_nach_frist_zaehlt_nicht():
    c = make(time_limit=10)
    c.on_char(c.engine.target[0], now=T0)
    # Kein Tick dazwischen (z. B. UI hing) – der Anschlag kommt zu spät
    assert c.on_char(c.engine.target[1], now=T0 + 10.2) is KeyOutcome.IGNORED
    assert c.result().keystrokes == 1
    assert c.result().end_reason is SessionEnd.TIME_UP


def test_zeitlimit_ergebnis_nur_erreichter_text():
    c = make(time_limit=10)
    target = c.engine.target
    tippe(c, target[:6])
    c.tick(now=T0 + 11)
    r = c.result()
    assert r.target_text == target[:6]
    assert len(r.char_states) == 6


def test_zeitlimit_textnamen_nur_erreichte():
    texts = [RawText("a.txt", "Haus"), RawText("b.txt", "Baum")]
    c = make(time_limit=60, texts=texts, seed=1)
    erster = c.text_names[0]
    tippe(c, "x" * 4)                           # nur der erste Text
    assert c.text_names == [erster]
    tippe(c, "x" * 2, t_start=T0 + 2)           # Enter-Position + erstes Zeichen des zweiten
    assert len(c.text_names) == 2


def test_restzeit():
    c = make(time_limit=30)
    assert c.remaining_time(now=T0) == 30
    c.on_char("H", now=T0)
    assert c.remaining_time(now=T0 + 12) == pytest.approx(18)
    assert make().remaining_time(now=T0) is None
    assert c.progress is None


def test_zeitlimit_mit_death():
    c = make(time_limit=60, death=True)
    c.on_char("#", now=T0)
    assert c.end_reason is SessionEnd.DIED


# --- Abbruch -----------------------------------------------------------------------------

def test_abbruch():
    c = make()
    tippe(c, "Ha")
    c.abort(now=T0 + 3)
    assert c.result().end_reason is SessionEnd.ABORTED


def test_abbruch_vor_start():
    c = make()
    c.abort(now=T0)
    r = c.result()
    assert r.end_reason is SessionEnd.ABORTED
    assert r.keystrokes == 0 and r.cpm_avg == 0


def test_spitze_bei_sehr_kurzer_runde_gleich_durchschnitt():
    c = make()
    tippe(c, "Haus", schritt=0.1)              # < 1 s -> kein Verlaufswert
    r = c.result()
    assert r.cpm_series == []
    assert r.cpm_peak == r.cpm_avg


def test_backspace_zaehlt_nicht_zur_geschwindigkeit():
    c = make(texts=[RawText("a.txt", "Haus")])
    # H a x ⌫ u s  -> 5 Zeichen-Anschläge, das Backspace zählt nicht
    tippe(c, "Hax⌫us", schritt=1.0)
    r = c.result()
    assert r.keystrokes == 5
    assert c.metrics.keystrokes == 5
    assert r.duration_s == pytest.approx(5.0)          # 0 s … 5 s (letztes „s“)
    assert r.cpm_avg == pytest.approx(5 / 5 * 60)


def test_tod_mit_zeitlimit_behaelt_folgetext_fuer_kontext():
    c = make(time_limit=60, death=True)
    target = c.engine.target
    c.on_char(target[0], now=T0)
    c.on_char("#", now=T0 + 0.2)
    r = c.result()
    assert r.target_text == target[:32]          # 2 getippt + 30 Folgezeichen
    assert r.last_error.position == 1
