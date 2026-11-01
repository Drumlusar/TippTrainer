"""Textdateien laden und auf tippbare Zeichen der deutschen Tastatur normalisieren.

Aufruf zum Ausprobieren:
    python -m core.text_normalizer daten/texte/beispiel.txt
    python -m core.text_normalizer daten/texte/beispiel.txt --altgr
"""
from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# --- Zeichensätze ----------------------------------------------------------

# Alles, was ohne AltGr und ohne Tottaste auf der deutschen Tastatur erreichbar ist.
BASE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "äöüÄÖÜß"
    "0123456789"
    "!\"§$%&/()=?'*+#-_.:,;<>°"
    " \n"
)

# Zeichen, die nur über AltGr erreichbar sind.
ALTGR_CHARS = frozenset("@€{}[]\\~|²³µ")

# Ersatz für AltGr-Zeichen, wenn AltGr deaktiviert ist.
ALTGR_REPLACEMENTS = {
    "€": "EUR",
    "@": "at",
    "[": "(", "]": ")",
    "{": "(", "}": ")",
    "\\": "/",
    "~": "-",
    "|": "/",
    "²": "2", "³": "3",
    "µ": "u",
}

# Typografische Zeichen, Tottasten und Sonderleerzeichen (gilt immer).
TYPOGRAPHIC_REPLACEMENTS = {
    # doppelte Anführungszeichen
    "„": '"', "“": '"', "”": '"', "«": '"', "»": '"', "‹": '"', "›": '"', "″": '"',
    # einfache Anführungszeichen / Apostrophe / Akzente als Einzelzeichen
    "‚": "'", "‘": "'", "’": "'", "´": "'", "`": "'", "′": "'",
    # Striche
    "–": "-", "—": "-", "‒": "-", "−": "-", "‐": "-", "‑": "-",
    # Sonstiges
    "…": "...",
    "·": "-", "•": "-",
    "×": "x",
    "ẞ": "ß",            # großes Eszett ist nicht direkt tippbar
    "^": "",
    # Leerraum
    "\t": " ", " ": " ", " ": " ", " ": " ", " ": " ",
}

_LINE_BREAKS = re.compile(r"\r\n|\r| | |\f|\v")
_MULTI_SPACE = re.compile(r" {2,}")
_MULTI_NEWLINE = re.compile(r"\n{2,}")


class TextLoadError(Exception):
    """Datei konnte nicht gelesen oder dekodiert werden."""


@dataclass
class NormalizeResult:
    text: str
    removed: Counter = field(default_factory=Counter)  # Zeichen, die ersatzlos entfernt wurden


# --- Laden -----------------------------------------------------------------

def read_text_file(path: Path) -> str:
    """Liest eine Textdatei: zuerst UTF-8 (mit/ohne BOM), dann Windows-1252."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise TextLoadError(f"Datei nicht lesbar: {path} ({exc})") from exc
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise TextLoadError(f"Unbekannte Kodierung: {path}")


def load_text(path: Path, allow_altgr: bool = False) -> NormalizeResult:
    """Datei lesen und normalisieren."""
    return normalize(read_text_file(path), allow_altgr=allow_altgr)


# --- Normalisierung --------------------------------------------------------

def _map_char(ch: str, allowed: frozenset[str], allow_altgr: bool) -> str | None:
    """Ein Zeichen auf tippbare Zeichen abbilden. None = unbekannt (wird entfernt)."""
    if ch in allowed:
        return ch
    if ch in TYPOGRAPHIC_REPLACEMENTS:
        return TYPOGRAPHIC_REPLACEMENTS[ch]
    if not allow_altgr and ch in ALTGR_REPLACEMENTS:
        return ALTGR_REPLACEMENTS[ch]
    # Akzente entfernen: "é" -> "e" + Kombinationszeichen -> "e"; Ligatur "ﬁ" -> "fi"
    decomposed = unicodedata.normalize("NFKD", ch)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    if stripped and all(c in allowed for c in stripped):
        return stripped
    return None


def normalize(text: str, allow_altgr: bool = False) -> NormalizeResult:
    allowed = BASE_CHARS | ALTGR_CHARS if allow_altgr else BASE_CHARS
    removed: Counter = Counter()

    # 1. Zeilenenden vereinheitlichen
    text = _LINE_BREAKS.sub("\n", text)

    # 2. Zeichen für Zeichen abbilden
    parts: list[str] = []
    for ch in text:
        mapped = _map_char(ch, allowed, allow_altgr)
        if mapped is None:
            removed[ch] += 1
        else:
            parts.append(mapped)
    text = "".join(parts)

    # 3. Leerraum aufräumen: pro Zeile Mehrfach-Leerzeichen zusammenfassen,
    #    Leerzeichen am Zeilenanfang und -ende entfernen (nicht sichtbar, aber zu tippen)
    lines = [_MULTI_SPACE.sub(" ", line).strip(" ") for line in text.split("\n")]
    text = "\n".join(lines)

    # 4. Leerzeilen zusammenfassen, Anfang/Ende säubern
    text = _MULTI_NEWLINE.sub("\n", text).strip(" \n")

    return NormalizeResult(text=text, removed=removed)


# --- Kommandozeile zum Ausprobieren ---------------------------------------

def _main(argv: list[str]) -> int:
    if not argv:
        print("Aufruf: python -m core.text_normalizer DATEI [--altgr]")
        return 1
    path = Path(argv[0])
    try:
        result = load_text(path, allow_altgr="--altgr" in argv)
    except TextLoadError as exc:
        print(f"Fehler: {exc}")
        return 1
    print(result.text.replace("\n", "↵\n"))
    if result.removed:
        print("\nEntfernte Zeichen:", dict(result.removed))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
