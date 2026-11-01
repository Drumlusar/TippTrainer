"""Farben und Schriften an einer Stelle."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase

UI_DIR = Path(__file__).resolve().parent

BG = QColor("#26272c")
PENDING = QColor("#6c6f78")
CORRECT = QColor("#e8e6e1")
WRONG = QColor("#f2545b")
WRONG_BG = QColor(242, 84, 91, 90)    # roter Block hinter falschem Leerzeichen / Enter
CURSOR = QColor("#e2b714")

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


def load_stylesheet() -> str:
    """style.qss laden; {UI_DIR} wird durch den absoluten Pfad ersetzt (für die Pfeil-Grafiken)."""
    path = UI_DIR / "style.qss"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").replace("{UI_DIR}", UI_DIR.as_posix())
