import pytest

from core.models import CharState, InputMode, KeyOutcome
from core.typing_engine import TypingEngine

C, W, K, P = CharState.CORRECT, CharState.WRONG, CharState.CORRECTED, CharState.PENDING
BS = "⌫"   # Platzhalter für Backspace in den Tests


def tippe(engine, eingabe):
    """Zeichenfolge eintippen; ⌫ steht für Backspace."""
    for ch in eingabe:
        if ch == BS:
            engine.backspace()
        else:
            engine.type_char(ch)
    return engine


def computer(text):
    return TypingEngine(text, InputMode.COMPUTER)


def schreibmaschine(text):
    return TypingEngine(text, InputMode.TYPEWRITER)


# --- Beispiele aus dem Architekturplan (Abschnitt 4) -------------------------

def test_plan_computer_modus():
    e = tippe(computer("Haus"), "Hai⌫us")
    assert e.errors == 0              # Fehler wurde gelöscht -> zählt nicht mehr
    assert e.mistakes == 1            # ... ist aber als gemachter Fehler bekannt
    assert e.corrected == 1
    assert e.keystrokes == 5          # Backspace zählt nicht
    assert e.states == [C, C, K, C]   # das „u“ ist als korrigiert markiert
    assert e.finished


def test_plan_schreibmaschine():
    e = tippe(schreibmaschine("Haus"), "Haius")
    assert e.errors == 2
    assert e.mistakes == 2 and e.corrected == 0
    assert e.states == [C, C, W, W]
    assert e.finished
    assert e.keystrokes == 4          # das „s“ kam nach Textende und wird ignoriert


# --- Grundverhalten -------------------------------------------------------------

def test_alles_richtig():
    e = tippe(computer("Haus"), "Haus")
    assert (e.errors, e.keystrokes, e.states, e.finished) == (0, 4, [C, C, C, C], True)


def test_rueckgabewerte():
    e = computer("ab")
    assert e.type_char("a") is KeyOutcome.CORRECT
    assert e.type_char("x") is KeyOutcome.WRONG
    assert e.type_char("b") is KeyOutcome.IGNORED   # Text ist schon zu Ende


def test_nach_textende_kein_anschlag():
    e = tippe(computer("ab"), "abcd")
    assert e.keystrokes == 2


def test_enter_als_zeilenumbruch():
    e = tippe(computer("a\nb"), "a\nb")
    assert e.errors == 0
    e2 = tippe(computer("a\nb"), "a b")   # Leerzeichen statt Enter
    assert e2.errors == 1


def test_nur_ein_zeichen_erlaubt():
    with pytest.raises(ValueError):
        computer("ab").type_char("ab")


def test_leerer_text_nicht_erlaubt():
    with pytest.raises(ValueError):
        computer("")


# --- Backspace -------------------------------------------------------------------

def test_selbe_position_zweimal_falsch():
    e = tippe(computer("Haus"), "Hx⌫y⌫a")
    assert e.errors == 0
    assert e.mistakes == 2
    assert e.keystrokes == 4
    assert e.states[:2] == [C, K]


def test_backspace_setzt_auf_pending():
    e = tippe(computer("Haus"), "Ha⌫")
    assert e.pos == 1
    assert e.states == [C, P, P, P]


def test_backspace_am_anfang():
    e = computer("Haus")
    assert e.backspace() is False
    assert e.pos == 0


def test_korrigierter_fehler_bleibt_markiert_nach_erneutem_loeschen():
    # Fehler, korrigiert, dann nochmal gelöscht und richtig getippt -> weiterhin CORRECTED
    e = tippe(computer("ab"), "x⌫a⌫a")
    assert e.states[0] is K
    assert (e.errors, e.mistakes) == (0, 1)


def test_schreibmaschine_ignoriert_backspace():
    e = schreibmaschine("Haus")
    tippe(e, "Hx")
    assert e.backspace() is False
    assert e.pos == 2
    assert e.states[:2] == [C, W]


# --- Fehlerinfo, Nachladen, Fortschritt ----------------------------------------

def test_letzter_fehler():
    e = tippe(computer("Tee"), "Tr")
    assert e.last_error.position == 1
    assert e.last_error.expected == "e"
    assert e.last_error.typed == "r"


def test_text_nachladen():
    e = tippe(computer("ab"), "ab")
    assert e.finished
    e.append_text(" cd")
    assert not e.finished
    assert e.remaining == 3
    tippe(e, " cd")
    assert e.finished and e.errors == 0
    assert len(e.states) == 5


def test_fortschritt():
    e = tippe(computer("abcd"), "ab")
    assert e.progress == 0.5


# --- Fehlerzähler im Computer-Modus (sinkt beim Löschen) --------------------------

def test_fehlerzaehler_live():
    e = computer("Haus")
    verlauf = []
    for ch in "Hxy⌫⌫au":
        e.backspace() if ch == BS else e.type_char(ch)
        verlauf.append(e.errors)
    #            H  x  y  ⌫  ⌫  a  u
    assert verlauf == [0, 1, 2, 1, 0, 0, 0]
    assert e.mistakes == 2


def test_backspace_ueber_richtiges_zeichen_aendert_fehler_nicht():
    e = tippe(computer("Haus"), "Hx⌫a")    # 0 Fehler stehend
    tippe(e, "⌫⌫")                          # löscht "a" und "H" (beide richtig)
    assert e.errors == 0


def test_nicht_geloeschter_fehler_bleibt():
    e = tippe(computer("Haus"), "Hxus")
    assert e.errors == 1
