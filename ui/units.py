"""Anzeige-Einheit für Tempo: A/min (Anschläge) oder W/min (Wörter = A/min / 5).

Gespeichert wird intern immer A/min; umgerechnet wird nur bei der Anzeige.
Die Einheit gilt programmweit und wird im Menü umgeschaltet.
"""
from __future__ import annotations

CPM, WPM = "A/min", "W/min"
UNITS = (CPM, WPM)

_unit = CPM


def set_unit(unit: str) -> None:
    global _unit
    _unit = unit if unit in UNITS else CPM


def unit() -> str:
    return _unit


def other() -> str:
    return WPM if _unit == CPM else CPM


def conv(cpm: float, u: str | None = None) -> float:
    """A/min -> Wert in der Einheit u (Standard: aktuelle Einheit)."""
    return cpm / 5 if (u or _unit) == WPM else cpm


def fmt(cpm: float | None, u: str | None = None, with_unit: bool = False) -> str:
    if cpm is None:
        return "–"
    s = f"{conv(cpm, u):.0f}"
    return f"{s} {u or _unit}" if with_unit else s
