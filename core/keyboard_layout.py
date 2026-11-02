"""Tastaturlayouts für Bildschirmtastatur und Tastaturansicht der Statistik – ohne Qt, testbar.

Drei Layouts: "qwertz" (deutsch, ISO), "qwerty" (US, ANSI), "dvorak" (US-Dvorak, ANSI).
Wichtig: Das Layout hier bestimmt nur die *Anzeige*. Welches Zeichen eine Taste wirklich
erzeugt, legt das Betriebssystem fest (macOS: Systemeinstellungen → Tastatur → Eingabequellen).

`layout.keys_for_char(ch)` liefert die Tasten, die für ein Zeichen gedrückt werden müssen:
    QWERTZ: "A" -> {"a", "shift_r"}   "?" -> {"ß", "shift_l"}   "@" -> {"l", "altgr"} (Mac)
    QWERTY: "A" -> {"a", "shift_r"}   "?" -> {"/", "shift_l"}
    Dvorak: "A" -> {"a", "shift_r"}   "?" -> {"/", "shift_l"}   (Dvorak: / liegt oben rechts)
Shift kommt nach dem Zehnfingersystem auf die Seite der anderen Hand.
Zeichen, die es im Layout nicht gibt (z. B. ä auf QWERTY), liefern eine leere Menge.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

IS_MAC = sys.platform == "darwin"
ALT_LABEL = "⌥" if IS_MAC else "AltGr"
WIDTH_UNITS = 15.0
HEIGHT_UNITS = 5.0
MODIFIERS = frozenset({"backspace", "tab", "caps", "shift_l", "shift_r", "alt_l", "altgr"})


@dataclass(frozen=True)
class Key:
    id: str           # eindeutiger Name, bei Zeichentasten das Grundzeichen
    label: str        # Beschriftung unten (Grundzeichen bzw. Symbol)
    shift_label: str  # Beschriftung oben (Zeichen mit Shift), "" wenn keine
    x: float          # Position und Größe in Tasteneinheiten
    y: float
    w: float = 1.0
    h: float = 1.0
    left_hand: bool = True


@dataclass
class Layout:
    id: str
    name: str
    keys: list[Key]
    home_marks: tuple[str, str]                         # Tasten mit Tastmarke
    char_map: dict[str, tuple[str, bool]] = field(default_factory=dict)   # Zeichen -> (Taste, Shift)
    alt_map: dict[str, tuple[str, bool]] = field(default_factory=dict)    # Zeichen -> (Taste, Shift)

    def __post_init__(self) -> None:
        self.key_by_id = {k.id: k for k in self.keys}

    def _shift_for(self, key_id: str) -> str:
        return "shift_r" if self.key_by_id[key_id].left_hand else "shift_l"

    def keys_for_char(self, ch: str) -> set[str]:
        if ch in self.char_map:
            key_id, shift = self.char_map[ch]
            return {key_id, self._shift_for(key_id)} if shift else {key_id}
        if ch in self.alt_map:
            key_id, shift = self.alt_map[ch]
            out = {key_id, "altgr"}
            if shift:
                out.add(self._shift_for(key_id))
            return out
        return set()

    def key_of(self, ch: str) -> str | None:
        """Taste eines Zeichens ohne Modifikatoren (für die Statistik: Groß/Klein und
        Shift-Zeichen zusammen); None, wenn es das Zeichen im Layout nicht gibt."""
        hit = self.char_map.get(ch)
        return hit[0] if hit else None


def _make(id_: str, name: str, rows, iso: bool, left_counts, home, alt_map=None) -> Layout:
    """rows: 4 × (Grundzeichen, Shift-Zeichen). ISO: Enter über zwei Reihen, kurze linke
    Shift-Taste; ANSI: Backslash-Taste oben rechts, einreihiges Enter, lange linke Shift-Taste."""
    starts = [0.0, 1.5, 1.75, 1.25 if iso else 2.25]
    keys: list[Key] = []
    char_map: dict[str, tuple[str, bool]] = {}
    for r, ((base, shifted), x0) in enumerate(zip(rows, starts)):
        for i, (b, s) in enumerate(zip(base, shifted)):
            label = b.upper() if b.isalpha() and len(b.upper()) == 1 else b
            shift_label = "" if b.isalpha() and s == b.upper() else s
            keys.append(Key(b, label, shift_label, x0 + i, r, left_hand=i < left_counts[r]))
            char_map.setdefault(b, (b, False))
            char_map.setdefault(s, (b, True))
    keys += [Key("backspace", "⌫", "", 13, 0, 2, left_hand=False),
             Key("tab", "⇥", "", 0, 1, 1.5),
             Key("caps", "⇪", "", 0, 2, 1.75),
             Key("shift_l", "⇧", "", 0, 3, starts[3]),
             Key("shift_r", "⇧", "", 12.25, 3, 2.75, left_hand=False),
             Key("alt_l", "⌥" if IS_MAC else "Alt", "", 2.5, 4, 1.25),
             Key("space", "", "", 3.75, 4, 6.25),
             Key("altgr", ALT_LABEL if alt_map else ("⌥" if IS_MAC else "Alt"), "", 10.0, 4, 1.25,
                 left_hand=False)]
    if iso:
        keys.append(Key("enter", "↵", "", 13.75, 1, 1.25, 2, left_hand=False))
    else:
        keys.append(Key("enter", "↵", "", 12.75, 2, 2.25, left_hand=False))
    char_map[" "] = ("space", False)
    char_map["\n"] = ("enter", False)
    return Layout(id_, name, keys, home, char_map, alt_map or {})


_ALT_WIN = {"@": ("q", False), "€": ("e", False), "{": ("7", False), "[": ("8", False),
            "]": ("9", False), "}": ("0", False), "\\": ("ß", False), "~": ("+", False),
            "|": ("<", False), "µ": ("m", False), "²": ("2", False), "³": ("3", False)}
_ALT_MAC = {"@": ("l", False), "€": ("e", False), "{": ("8", False), "}": ("9", False),
            "[": ("5", False), "]": ("6", False), "|": ("7", False), "\\": ("7", True),
            "~": ("n", False), "µ": ("m", False)}

QWERTZ = _make("qwertz", "QWERTZ (deutsch)", [
    ("^1234567890ß´", "°!\"§$%&/()=?`"),
    ("qwertzuiopü+", "QWERTZUIOPÜ*"),
    ("asdfghjklöä#", "ASDFGHJKLÖÄ'"),
    ("<yxcvbnm,.-", ">YXCVBNM;:_"),
], iso=True, left_counts=[6, 5, 5, 6], home=("f", "j"), alt_map=_ALT_MAC if IS_MAC else _ALT_WIN)

QWERTY = _make("qwerty", "QWERTY (US)", [
    ("`1234567890-=", "~!@#$%^&*()_+"),
    ("qwertyuiop[]\\", "QWERTYUIOP{}|"),
    ("asdfghjkl;'", "ASDFGHJKL:\""),
    ("zxcvbnm,./", "ZXCVBNM<>?"),
], iso=False, left_counts=[6, 5, 5, 5], home=("f", "j"))

DVORAK = _make("dvorak", "Dvorak (US)", [
    ("`1234567890[]", "~!@#$%^&*(){}"),
    ("',.pyfgcrl/=\\", "\"<>PYFGCRL?+|"),
    ("aoeuidhtns-", "AOEUIDHTNS_"),
    (";qjkxbmwvz", ":QJKXBMWVZ"),
], iso=False, left_counts=[6, 5, 5, 5], home=("u", "h"))

LAYOUTS: dict[str, Layout] = {lay.id: lay for lay in (QWERTZ, QWERTY, DVORAK)}


def get_layout(layout_id: str) -> Layout:
    return LAYOUTS.get(layout_id, QWERTZ)


# Bequemer Zugriff für das deutsche Standardlayout
KEYS = QWERTZ.keys


def keys_for_char(ch: str, layout_id: str = "qwertz") -> set[str]:
    return get_layout(layout_id).keys_for_char(ch)
