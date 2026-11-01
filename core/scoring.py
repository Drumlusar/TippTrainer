"""Punktewertung: Geschwindigkeit mit Strafe für Fehler.

    Punkte = (Anschläge − Strafe × Fehler) / Minuten,   nie unter 0

„Fehler“ sind alle gemachten Fehler, auch korrigierte – sonst würde sich
hektisches Tippen mit viel Backspace lohnen.

Beispiel: 300 Anschläge, 10 Fehler, 1 Minute, Strafe 10
          -> (300 − 100) / 1 = 200 Punkte   (statt 300 A/min)
"""
from __future__ import annotations

import config


def score(keystrokes: int, mistakes: int, duration_s: float,
          penalty: int = config.SCORE_PENALTY) -> float:
    if keystrokes <= 0:
        return 0.0
    minutes = max(duration_s, config.MIN_DIVISOR_S) / 60
    return max(0.0, (keystrokes - penalty * mistakes) / minutes)
