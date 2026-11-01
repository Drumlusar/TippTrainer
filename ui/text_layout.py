"""Zeilenumbruch für die Tippansicht – reines Python, ohne Qt (testbar).

Ergebnis ist eine Liste von (start, ende)-Indizes in den Text. Ein
Zeilenumbruch "\\n" gehört als letztes Zeichen zu seiner Zeile (er wird
als ↵ angezeigt und belegt eine Spalte). Ein Leerzeichen an einer weichen
Umbruchstelle bleibt am Zeilenende stehen, damit jede Position im Text
genau einer Zeile gehört.
"""
from __future__ import annotations

from bisect import bisect_right

Line = tuple[int, int]


def wrap_lines(text: str, cols: int, breaks: list[int] = ()) -> list[Line]:
    """breaks: aufsteigende Positionen, an denen zusätzlich eine neue Zeile beginnt
    (Phrasen-Modus: Phrasen sind durch Leerzeichen getrennt, stehen aber je in eigener Zeile)."""
    if cols < 1:
        raise ValueError("cols muss >= 1 sein")
    lines: list[Line] = []
    start, n = 0, len(text)
    while start < n:
        nl = text.find("\n", start)
        hard_end = n if nl == -1 else nl + 1
        k = bisect_right(breaks, start)
        if k < len(breaks) and breaks[k] < hard_end:
            hard_end = breaks[k]
        if hard_end - start <= cols:
            end = hard_end
        else:
            space = text.rfind(" ", start, start + cols)
            end = start + cols if space == -1 else space + 1   # Wort zu lang -> hart trennen
        lines.append((start, end))
        start = end
    return lines


def line_of(lines: list[Line], pos: int) -> int:
    """Index der Zeile, in der Position `pos` liegt (am Textende: letzte Zeile)."""
    if not lines:
        return 0
    starts = [s for s, _ in lines]
    return max(0, min(bisect_right(starts, pos) - 1, len(lines) - 1))
