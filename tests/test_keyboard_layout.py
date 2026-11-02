"""Tastaturlayouts: welche Tasten für ein Zeichen leuchten, Geometrie ohne Überlappung."""
import pytest

from core.keyboard_layout import IS_MAC, LAYOUTS, keys_for_char


@pytest.mark.parametrize("layout, ch, tasten", [
    ("qwertz", "a", {"a"}),
    ("qwertz", "A", {"a", "shift_r"}),          # linke Hand -> rechte Shift-Taste
    ("qwertz", "P", {"p", "shift_l"}),          # rechte Hand -> linke Shift-Taste
    ("qwertz", "?", {"ß", "shift_l"}),
    ("qwertz", "!", {"1", "shift_r"}),
    ("qwertz", "Ü", {"ü", "shift_l"}),
    ("qwertz", "_", {"-", "shift_l"}),
    ("qwertz", "y", {"y"}),
    ("qwertz", " ", {"space"}),
    ("qwertz", "\n", {"enter"}),
    ("qwertz", "☺", set()),
    ("qwerty", "?", {"/", "shift_l"}),
    ("qwerty", "@", {"2", "shift_r"}),          # US: @ = Shift + 2
    ("qwerty", "Z", {"z", "shift_r"}),          # Z unten links
    ("qwerty", "ä", set()),                     # gibt es auf US-Tastatur nicht
    ("qwerty", '"', {"'", "shift_l"}),
    ("dvorak", "e", {"e"}),
    ("dvorak", "S", {"s", "shift_l"}),          # Dvorak: s rechts auf der Grundreihe
    ("dvorak", "?", {"/", "shift_l"}),
    ("dvorak", ":", {";", "shift_r"}),
    ("dvorak", "<", {",", "shift_r"}),
])
def test_tasten_fuer_zeichen(layout, ch, tasten):
    assert keys_for_char(ch, layout) == tasten


def test_altgr_nur_bei_qwertz():
    assert keys_for_char("@", "qwertz") == ({"l", "altgr"} if IS_MAC else {"q", "altgr"})
    assert "altgr" in keys_for_char("€", "qwertz")
    assert keys_for_char("€", "qwerty") == set()


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_geometrie(layout):
    keys = LAYOUTS[layout].keys
    ids = [k.id for k in keys]
    assert len(ids) == len(set(ids))                       # jede Taste nur einmal
    for a in keys:
        assert a.x >= 0 and a.x + a.w <= 15 + 1e-9         # passt in 15 Einheiten
        for b in keys:
            if a is not b:
                assert (a.x + a.w <= b.x + 1e-9 or b.x + b.w <= a.x + 1e-9
                        or a.y + a.h <= b.y or b.y + b.h <= a.y), (layout, a.id, b.id)


@pytest.mark.parametrize("layout", list(LAYOUTS))
def test_alle_ascii_buchstaben_vorhanden(layout):
    import string
    for ch in string.ascii_letters + string.digits + " .,":
        assert keys_for_char(ch, layout), (layout, ch)
