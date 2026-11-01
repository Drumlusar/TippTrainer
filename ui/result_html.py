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

# Farben des aktuellen Designs; ui/theme.py setzt sie beim Wechsel über set_colors().
# (Dieses Modul bleibt ohne Qt und damit ohne PySide6 testbar.)
COLORS = {"text": "#e8e6e1", "pending": "#6c6f78", "wrong": "#f2545b", "on_wrong": "#26272c"}


def set_colors(**colors: str) -> None:
    COLORS.update(colors)


def style_for(state: CharState) -> str:
    c = COLORS
    return {
        CharState.CORRECT: f"color:{c['text']};",
        CharState.CORRECTED: f"color:{c['wrong']}; text-decoration:underline;",
        CharState.WRONG: f"color:{c['on_wrong']}; background-color:{c['wrong']};",
        CharState.PENDING: f"color:{c['pending']};",
    }[state]


def legend_html() -> str:
    """Legende unter dem Ergebnistext: Beispiel für Fehler und korrigiert."""
    c = COLORS
    return (f'<span style="color:{c["on_wrong"]}; background-color:{c["wrong"]};">&nbsp;a&nbsp;</span>'
            f'&nbsp;Fehler&nbsp;&nbsp;&nbsp;&nbsp;'
            f'<span style="color:{c["wrong"]}; text-decoration:underline;">a</span>&nbsp;korrigiert')


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
        parts.append(f'<span style="{style_for(state)}">{"".join(chunk)}</span>')
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
