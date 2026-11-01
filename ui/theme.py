"""Farben und Schriften an einer Stelle – Design „Dunkel“ und „Hell“.

Alle Farben werden über ihren Namen abgefragt (`color("accent")`, `hexc("accent")`),
und zwar erst beim Zeichnen. So wirkt ein Wechsel des Designs sofort, ohne Neustart.
style.qss enthält Platzhalter wie `@accent`, die beim Laden ersetzt werden.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase

UI_DIR = Path(__file__).resolve().parent

DARK, LIGHT = "Dunkel", "Hell"
THEMES = (DARK, LIGHT)

PALETTES: dict[str, dict[str, str]] = {
    DARK: {
        "bg": "#26272c",             # Fensterhintergrund
        "field": "#1f2024",          # Eingabefelder, Tabellen, Textkästen
        "surface": "#2d2f35",        # Kacheln, Listenzeilen
        "surface_hover": "#363840",
        "button": "#33353b",
        "button_hover": "#3d3f46",
        "border": "#3a3c43",
        "border_strong": "#44464e",
        "disabled": "#5a5d65",
        "dim": "#6c6f78",            # noch nicht getippter Text, Hinweise
        "muted": "#8a8d96",          # Beschriftungen
        "ink_soft": "#d8d6d0",       # normaler Text
        "ink": "#e8e6e1",            # betonter / getippter Text
        "accent": "#e2b714",         # Gold: Cursor, Titel, Auswahl
        "accent_hover": "#f0c62a",
        "accent_dim": "#6b5a1a",
        "accent_ink": "#26272c",     # Text auf Gold
        "start_disabled": "#4a4a40",
        "error": "#f2545b",
        "dbm_bg": "#322a2d",
        "dbm_hover": "#3d3236",
        "warn": "#d8a24a",
        "ok": "#7cc47f",
        "grid": "#34363c",           # Diagramm-Gitter
        "chart_ink": "#b8b6b0",      # Diagramm-Legende
        "dot": "#8a7a3a",            # Tageswerte im Fortschritt
        "err_dot": "#8f4a4e",
        "key_nodata": "#232428",     # Tastatur ohne Daten
        "pace": "#8a8d96",           # Tempo-Cursor
        "arrow": "#b8b6b0",          # Pfeile in Auswahllisten
        "arrow_disabled": "#5a5d65",
    },
    LIGHT: {
        "bg": "#f4f2ee",
        "field": "#ffffff",
        "surface": "#e9e6e0",
        "surface_hover": "#dfdbd3",
        "button": "#e4e1db",
        "button_hover": "#d8d4cc",
        "border": "#d2cec6",
        "border_strong": "#bdb8ae",
        "disabled": "#aaa59c",
        "dim": "#a19c93",
        "muted": "#6b675f",
        "ink_soft": "#3a3936",
        "ink": "#1f1f22",
        "accent": "#b88a00",
        "accent_hover": "#a37a00",
        "accent_dim": "#dccb8f",
        "accent_ink": "#1f1f22",
        "start_disabled": "#ddd7c4",
        "error": "#d63c43",
        "dbm_bg": "#f5e4e4",
        "dbm_hover": "#efd8d8",
        "warn": "#a8650c",
        "ok": "#2f8a3b",
        "grid": "#e2ded6",
        "chart_ink": "#4a4844",
        "dot": "#d6bd6a",
        "err_dot": "#eaa3a6",
        "key_nodata": "#efede8",
        "pace": "#8f8a80",
        "arrow": "#5f5b54",
        "arrow_disabled": "#bdb8ae",
    },
}

_current = DARK


def set_theme(name: str) -> None:
    global _current
    _current = name if name in PALETTES else DARK
    from ui import result_html                      # Qt-freies Modul mit eigenen Farben
    result_html.set_colors(text=hexc("ink"), pending=hexc("dim"), wrong=hexc("error"),
                           on_wrong=hexc("bg"))


def current() -> str:
    return _current


def hexc(name: str) -> str:
    """Farbe als "#rrggbb" (für matplotlib und HTML)."""
    return PALETTES[_current][name]


def color(name: str, alpha: int | None = None) -> QColor:
    c = QColor(hexc(name))
    if alpha is not None:
        c.setAlpha(alpha)
    return c


MONO_CANDIDATES = ("JetBrains Mono", "SF Mono", "Menlo", "Consolas",
                   "DejaVu Sans Mono", "Liberation Mono")


def mono_font(point_size: int = 26) -> QFont:
    families = set(QFontDatabase.families())
    for name in MONO_CANDIDATES:
        if name in families:
            font = QFont(name, point_size)
            break
    else:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(point_size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font


def _arrow_svg(path: str, stroke: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6" viewBox="0 0 10 6">'
            f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _arrow_dir() -> Path:
    """Pfeil-Grafiken in der Farbe des aktuellen Designs (Qt-Stylesheets können
    SVG-Farben nicht umfärben, deshalb je Design eigene Dateien)."""
    folder = UI_DIR / "pfeile" / ("hell" if _current == LIGHT else "dunkel")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for name, path in (("arrow_up", "M1 5l4-4 4 4"), ("arrow_down", "M1 1l4 4 4-4")):
            for suffix, key in (("", "arrow"), ("_disabled", "arrow_disabled")):
                f = folder / f"{name}{suffix}.svg"
                svg = _arrow_svg(path, hexc(key))
                if not f.exists() or f.read_text(encoding="utf-8") != svg:
                    f.write_text(svg, encoding="utf-8")
        return folder
    except OSError:
        return UI_DIR            # Ordner nicht beschreibbar: mitgelieferte (dunkle) Pfeile


def load_stylesheet(ui_scale: float = 1.0) -> str:
    """style.qss laden: Farb-Platzhalter (@name) durch das aktuelle Design ersetzen,
    {UI_DIR} durch den Pfeil-Ordner, alle Schriftgrößen mit ui_scale skalieren."""
    path = UI_DIR / "style.qss"
    if not path.exists():
        return ""
    qss = path.read_text(encoding="utf-8")
    palette = PALETTES[_current]
    for name in sorted(palette, key=len, reverse=True):     # längste zuerst (ink_soft vor ink)
        qss = qss.replace("@" + name, palette[name])
    qss = qss.replace("{UI_DIR}", _arrow_dir().as_posix())
    if ui_scale != 1.0:
        qss = re.sub(r"font-size:\s*(\d+)px",
                     lambda m: f"font-size: {max(8, round(int(m.group(1)) * ui_scale))}px", qss)
    return qss
