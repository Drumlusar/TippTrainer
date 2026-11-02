"""Fortschrittskurve je Test-Profil – berechnet aus `sessions.csv`.

Pro Tag: Mittelwert von Netto-Tempo, Fehlerquote und Konsistenz aller gezählten
Runden des Profils (gleiche Regeln wie die Profil-Bestenliste: fertig oder Zeit
abgelaufen). Dazu ein gleitender 7-Tage-Schnitt: Mittel aller Runden der letzten
sieben Kalendertage (einschließlich des Tages selbst) – Tage mit vielen Runden
wiegen also stärker, Tage ohne Übung zählen nicht als null.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from storage.highscores import profile_attempt
from storage.history import DATE_FMT, load_all, parse_num


@dataclass(frozen=True)
class Run:
    day: date
    net_cpm: float
    error_rate: float
    consistency: float | None


@dataclass(frozen=True)
class DayPoint:
    day: date
    runs: int
    net_cpm: float              # Tagesmittel
    error_rate: float           # Tagesmittel, Prozent
    consistency: float | None   # Tagesmittel (nur Runden mit Wert)
    net_cpm_7d: float           # gleitender 7-Tage-Schnitt
    error_rate_7d: float


def load_runs(profile: str, path: Path = config.HISTORY_FILE,
              keyboard: str | None = None) -> list[Run]:
    out = []
    for row in load_all(path):
        a = profile_attempt(row)
        if a is None or a.text != profile or (keyboard is not None and a.keyboard != keyboard):
            continue
        try:
            day = datetime.strptime(a.when, DATE_FMT).date()
        except ValueError:
            continue
        cons = row.get("konsistenz_prozent")
        out.append(Run(day, a.net_cpm if a.net_cpm is not None else a.cpm,
                       parse_num(row.get("fehlerquote_prozent", "") or "0"),
                       parse_num(cons) if cons else None))
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def daily(runs: list[Run], window_days: int = 7) -> list[DayPoint]:
    by_day: dict[date, list[Run]] = defaultdict(list)
    for r in runs:
        by_day[r.day].append(r)
    points = []
    for day in sorted(by_day):
        today = by_day[day]
        window = [r for r in runs if day - timedelta(days=window_days - 1) <= r.day <= day]
        cons = [r.consistency for r in today if r.consistency is not None]
        points.append(DayPoint(
            day=day,
            runs=len(today),
            net_cpm=_mean([r.net_cpm for r in today]),
            error_rate=_mean([r.error_rate for r in today]),
            consistency=_mean(cons) if cons else None,
            net_cpm_7d=_mean([r.net_cpm for r in window]),
            error_rate_7d=_mean([r.error_rate for r in window]),
        ))
    return points


def profile_progress(profile: str, path: Path = config.HISTORY_FILE,
                     keyboard: str | None = None) -> list[DayPoint]:
    """keyboard: Tastatur-ID oder None (alle Tastaturen)."""
    return daily(load_runs(profile, path, keyboard))
