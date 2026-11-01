"""Tastenzuordnung der Tippansicht. Wird übersprungen, wenn PySide6 fehlt."""
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt          # noqa: E402
from PySide6.QtGui import QKeyEvent            # noqa: E402

from ui.typing_view import key_to_input       # noqa: E402

K, M = Qt.Key, Qt.KeyboardModifier


def ev(key, text="", mods=M.NoModifier, repeat=False):
    return QKeyEvent(QEvent.Type.KeyPress, key, mods, text, repeat)


@pytest.mark.parametrize("event, erwartet", [
    (ev(K.Key_A, "a"), "a"),
    (ev(K.Key_A, "A", M.ShiftModifier), "A"),
    (ev(K.Key_A, "ä"), "ä"),
    (ev(K.Key_Space, " "), " "),
    (ev(K.Key_Return), "\n"),
    (ev(K.Key_Enter), "\n"),
    (ev(K.Key_Backspace), "BACKSPACE"),
    (ev(K.Key_Backspace, mods=M.AltModifier), None),             # Mac: Wort löschen
    (ev(K.Key_Backspace, mods=M.ControlModifier), None),         # Win: Wort löschen
    (ev(K.Key_A, "a", M.ControlModifier), None),                 # Strg/Cmd+A
    (ev(K.Key_Q, "@", M.ControlModifier | M.AltModifier), "@"),  # Windows-AltGr
    (ev(K.Key_L, "@", M.AltModifier), "@"),                      # Mac: Option+L
    (ev(K.Key_A, "a", M.MetaModifier), None),                    # Mac: Ctrl+A
    (ev(K.Key_A, "a", repeat=True), None),                       # gehaltene Taste
    (ev(K.Key_Backspace, repeat=True), "BACKSPACE"),             # gehaltenes Backspace ok
    (ev(K.Key_Tab, "\t"), None),
    (ev(K.Key_Shift), None),
])
def test_tastenzuordnung(event, erwartet):
    assert key_to_input(event) == erwartet
