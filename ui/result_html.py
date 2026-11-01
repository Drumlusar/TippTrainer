"""Text mit Fehlermarkierung als HTML (für QTextBrowser / QLabel) – ohne Qt, testbar.

Darstellung:
  richtig        -> normale Textfarbe
  falsch         -> roter Block (dunkle Schrift auf Rot), auch für Leerzeichen/Enter sichtbar
  korrigiert     -> rot und unterstrichen
  nicht getippt  -> grau
"""
from __future__ import annotations

from html import escape

from core.models import CharState

COLOR_TEXT = "#e8e6e1"
COLOR_PENDING = "#6c6f78"
COLOR_WRONG = "#f2545b"
COLOR_ON_WRONG = "#26272c"

STYLES = {
    CharState.CORRECT: f"color:{COLOR_TEXT};",
    CharState.CORRECTED: f"color:{COLOR_WRONG}; text-decoration:underline;",
    CharState.WRONG: f"color:{COLOR_ON_WRONG}; background-color:{COLOR_WRONG};",
    CharState.PENDING: f"color:{COLOR_PENDING};",
}


def _glyph(ch: str, state: CharState) -> str:
    if ch == "\n":
        return "↵<br>"
    if ch == " " and state is CharState.WRONG:
        return "&nbsp;"
    return escape(ch)


def marked_html(text: str, states: list[CharState]) -> str:
    """Folgen gleicher Zustände werden zu einem <span> zusammengefasst."""
    parts: list[str] = []
    i, n = 0, len(text)
    while i < n:
        state = states[i]
        j = i
        chunk: list[str] = []
        while j < n and states[j] is state:
            chunk.append(_glyph(text[j], state))
            j += 1
        parts.append(f'<span style="{STYLES[state]}">{"".join(chunk)}</span>')
        i = j
    return "".join(parts)


def snippet_around(text: str, states: list[CharState], pos: int,
                   radius: int = 25) -> tuple[str, list[CharState]]:
    """Ausschnitt rund um eine Position (für den Deathscreen), Umbrüche als Leerzeichen."""
    start, end = max(0, pos - radius), min(len(text), pos + radius + 1)
    part = text[start:end].replace("\n", " ")
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    st = list(states[start:end])
    return (prefix + part + suffix,
            ([CharState.PENDING] if prefix else []) + st + ([CharState.PENDING] if suffix else []))
