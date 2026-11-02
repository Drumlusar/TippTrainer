"""Statistik je Zeichen, Verwechslung und Wort – reines Python (testbar).

Erfasst wird pro Runde ein Anschlags-Protokoll (erwartet, getippt, Abstand zum
vorigen Anschlag); daraus entsteht eine kompakte Tagesstatistik:

  zeichen        "a" -> [Anschläge, Fehler, Zeitsumme_ms, Anzahl_Zeitmessungen]
  verwechslungen "e" -> {"r": 3, ...}          (erwartet -> getippt)
  woerter        "Haus" -> [Vorkommen, davon mit Fehler]

Tempo: nur richtig getippte Zeichen; Pausen über `PAUSE_S` zählen nicht (Nachdenken).
Groß-/Kleinschreibung wird getrennt erfasst („A“ ≠ „a“), weil oft Shift das Problem ist.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

import config

KeyEvent = tuple[str, str, float | None]          # (erwartet, getippt, Abstand in s)

WORD_EDGE = ".,;:!?\"'()[]{}<>-_/*+#&%$§="
_TOKEN = re.compile(r"\S+")

# Tastatur: Zeichen -> Taste (deutsches QWERTZ), für die Tastaturansicht
SHIFT_TO_KEY = {"!": "1", '"': "2", "§": "3", "$": "4", "%": "5", "&": "6", "/": "7",
                "(": "8", ")": "9", "=": "0", "?": "ß", "*": "+", "'": "#", ">": "<",
                ";": ",", ":": ".", "_": "-", "°": "^"}


def key_of(ch: str) -> str:
    if ch in SHIFT_TO_KEY:
        return SHIFT_TO_KEY[ch]
    return ch.lower()


def char_label(ch: str, short: bool = False) -> str:
    if short:
        return {" ": "Leer", "\n": "Enter"}.get(ch, ch)
    return {" ": "Leerzeichen", "\n": "Enter"}.get(ch, ch)


@dataclass
class Stats:
    chars: dict[str, list[int]] = field(default_factory=dict)
    confusions: dict[str, dict[str, int]] = field(default_factory=dict)
    words: dict[str, list[int]] = field(default_factory=dict)

    def merge(self, other: "Stats") -> "Stats":
        for ch, v in other.chars.items():
            mine = self.chars.setdefault(ch, [0, 0, 0, 0])
            for i in range(4):
                mine[i] += v[i]
        for exp, typed in other.confusions.items():
            mine = self.confusions.setdefault(exp, {})
            for t, n in typed.items():
                mine[t] = mine.get(t, 0) + n
        for w, v in other.words.items():
            mine = self.words.setdefault(w, [0, 0])
            mine[0] += v[0]
            mine[1] += v[1]
        return self

    def scaled(self, k: int) -> "Stats":
        """Alle Zähler mal k – mit k = −1 lässt sich eine Runde wieder herausrechnen."""
        return Stats({c: [x * k for x in v] for c, v in self.chars.items()},
                     {e: {t: n * k for t, n in typed.items()} for e, typed in self.confusions.items()},
                     {w: [x * k for x in v] for w, v in self.words.items()})

    def drop_empty(self) -> "Stats":
        """Einträge entfernen, die (nach dem Herausrechnen) nur noch Nullen enthalten."""
        self.chars = {c: v for c, v in self.chars.items() if any(v)}
        self.confusions = {e: {t: n for t, n in typed.items() if n}
                           for e, typed in self.confusions.items()}
        self.confusions = {e: typed for e, typed in self.confusions.items() if typed}
        self.words = {w: v for w, v in self.words.items() if any(v)}
        return self

    def to_json(self) -> dict:
        return {"zeichen": self.chars, "verwechslungen": self.confusions, "woerter": self.words}

    @classmethod
    def from_json(cls, d: dict) -> "Stats":
        return cls({k: list(v) for k, v in d.get("zeichen", {}).items()},
                   {k: dict(v) for k, v in d.get("verwechslungen", {}).items()},
                   {k: list(v) for k, v in d.get("woerter", {}).items()})


# --- Erfassen ---------------------------------------------------------------------------

def words_with_mistakes(text: str, upto: int,
                        pos_mistakes: Mapping[int, int]) -> list[tuple[str, bool]]:
    """Vollständig getippte Wörter bis `upto` und ob darin ein Fehler passiert ist.
    Satzzeichen am Wortrand zählen nicht zum Wort: „Haus,“ -> „Haus“."""
    out = []
    for m in _TOKEN.finditer(text, 0, upto):
        s, e = m.span()
        if e == upto and upto < len(text) and not text[upto].isspace():
            continue                                   # Wort beim Ende abgeschnitten
        raw = m.group()
        left = len(raw) - len(raw.lstrip(WORD_EDGE))
        right = len(raw.rstrip(WORD_EDGE))
        word = raw[left:right]
        if not word or not any(c.isalpha() for c in word):
            continue
        had = any(pos_mistakes.get(i, 0) for i in range(s + left, s + right))
        out.append((word, had))
    return out


def collect(keylog: list[KeyEvent], words: list[tuple[str, bool]],
            pause_s: float = config.STATS_PAUSE_S) -> Stats:
    st = Stats()
    for expected, typed, dt in keylog:
        c = st.chars.setdefault(expected, [0, 0, 0, 0])
        c[0] += 1
        if typed != expected:
            c[1] += 1
            conf = st.confusions.setdefault(expected, {})
            conf[typed] = conf.get(typed, 0) + 1
        elif dt is not None and dt <= pause_s:
            c[2] += round(dt * 1000)
            c[3] += 1
    for word, had in words:
        w = st.words.setdefault(word, [0, 0])
        w[0] += 1
        w[1] += int(had)
    return st


# --- Auswerten ------------------------------------------------------------------------------

@dataclass(frozen=True)
class CharRow:
    char: str
    keys: int
    mistakes: int
    avg_ms: float | None

    @property
    def error_rate(self) -> float:
        return self.mistakes / self.keys * 100 if self.keys else 0.0


def overall_avg_ms(st: Stats) -> float | None:
    total = sum(v[2] for v in st.chars.values())
    n = sum(v[3] for v in st.chars.values())
    return total / n if n else None


def char_rows(st: Stats, min_keys: int = config.STATS_MIN_KEYS) -> list[CharRow]:
    rows = [CharRow(ch, v[0], v[1], v[2] / v[3] if v[3] else None)
            for ch, v in st.chars.items() if v[0] >= min_keys]
    return sorted(rows, key=lambda r: (-r.error_rate, -r.keys))


def slower_pct(row: CharRow, avg: float | None) -> float | None:
    """+45 = 45 % langsamer als der Durchschnitt, −10 = 10 % schneller."""
    if row.avg_ms is None or not avg:
        return None
    return (row.avg_ms / avg - 1) * 100


def confusion_rows(st: Stats) -> list[tuple[str, str, int]]:
    rows = [(e, t, n) for e, typed in st.confusions.items() for t, n in typed.items()]
    return sorted(rows, key=lambda r: -r[2])


def word_rows(st: Stats) -> list[tuple[str, int, int]]:
    """(Wort, Vorkommen, mit Fehler) – nur Wörter mit mindestens einem Fehler."""
    rows = [(w, v[0], v[1]) for w, v in st.words.items() if v[1] > 0]
    return sorted(rows, key=lambda r: (-r[2], -r[2] / r[1]))


@dataclass(frozen=True)
class Group:
    keys: int
    mistakes: int
    avg_ms: float | None

    @property
    def error_rate(self) -> float:
        return self.mistakes / self.keys * 100 if self.keys else 0.0


def _group(st: Stats, pick) -> Group:
    vals = [v for ch, v in st.chars.items() if pick(ch)]
    keys = sum(v[0] for v in vals)
    n = sum(v[3] for v in vals)
    return Group(keys, sum(v[1] for v in vals), sum(v[2] for v in vals) / n if n else None)


def case_summary(st: Stats) -> tuple[Group, Group]:
    """(Großbuchstaben, Kleinbuchstaben) – zeigt, ob Shift bremst oder Fehler macht."""
    return (_group(st, lambda c: c.isalpha() and c.isupper()),
            _group(st, lambda c: c.isalpha() and c.islower()))


def key_rows(st: Stats, layout=None) -> dict[str, Group]:
    """Je Taste (Groß/Klein und Shift-Zeichen zusammengefasst) – für die Tastaturansicht.
    layout: core.keyboard_layout.Layout (Standard: deutsches QWERTZ). Schlüssel sind die
    Tasten-IDs des Layouts ("space", "enter" für Leertaste und Enter)."""
    if layout is None:
        from core.keyboard_layout import QWERTZ as layout
    keys: dict[str, list[int]] = {}
    for ch, v in st.chars.items():
        key = layout.key_of(ch)
        if key is None:
            continue                       # Zeichen gibt es in diesem Layout nicht
        k = keys.setdefault(key, [0, 0, 0, 0])
        for i in range(4):
            k[i] += v[i]
    return {k: Group(v[0], v[1], v[2] / v[3] if v[3] else None) for k, v in keys.items()}
