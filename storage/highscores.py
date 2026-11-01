"""Highscores pro Text – berechnet aus `sessions.csv` (also auch rückwirkend).

Es zählen nur Runden ohne Zeitlimit, in denen genau ein Text (zufällig oder
gezielt gewählt) vollständig getippt wurde. Death-by-Mistake-Runden zählen
nur, wenn sie überlebt wurden (Ergebnis „abgeschlossen“). Wörter und Phrasen
zählen nicht.

Die Punkte werden immer frisch aus Anschlägen, Fehlern und Dauer berechnet –
eine geänderte Strafe gilt damit sofort für alle alten Runden.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import config
from core.models import SessionEnd, SessionResult, SourceMode
from core.scoring import score
from storage.history import load_all, parse_num, to_row

ELIGIBLE_SOURCES = {SourceMode.RANDOM_TEXT.value, SourceMode.SPECIFIC_TEXT.value}


@dataclass(frozen=True)
class Attempt:
    when: str            # "2026-11-01 13:20:05" – verbindet CSV-Zeile und gespeicherte Auswertung
    text: str
    keystrokes: int
    mistakes: int        # alle Fehler, auch korrigierte
    errors: int          # stehende Fehler
    duration_s: float
    cpm: float
    net_cpm: float | None
    input_mode: str
    dbm: bool
    profile: str = ""

    def points(self, penalty: int) -> float:
        return score(self.keystrokes, self.mistakes, self.duration_s, penalty)


def from_row(row: dict[str, str]) -> Attempt | None:
    """CSV-Zeile -> Attempt, oder None, wenn die Runde nicht zählt."""
    if (row.get("zeitlimit_s") or row.get("textquelle") not in ELIGIBLE_SOURCES
            or row.get("ergebnis") != SessionEnd.COMPLETED.value):
        return None
    text = row.get("textnamen", "")
    if not text or ", " in text:
        return None
    try:
        errors = int(row.get("fehler") or 0)
        corrected = int(row.get("fehler_korrigiert") or 0)
        keystrokes = int(row.get("anschlaege") or 0)
    except ValueError:
        return None
    net = row.get("apm_netto")
    return Attempt(
        when=row.get("datum_zeit", ""),
        text=text,
        keystrokes=keystrokes,
        mistakes=errors + corrected,
        errors=errors,
        duration_s=parse_num(row.get("dauer_s", "")),
        cpm=parse_num(row.get("apm_durchschnitt", "")),
        net_cpm=parse_num(net) if net else None,
        input_mode=row.get("eingabemodus", ""),
        dbm=row.get("death_by_mistake") == "ja",
        profile=row.get("profil", "") or "",
    )


PROFILE_RESULTS = {SessionEnd.COMPLETED.value, SessionEnd.TIME_UP.value}


def profile_attempt(row: dict[str, str]) -> Attempt | None:
    """CSV-Zeile -> Versuch in der Bestenliste ihres Test-Profils (Feld `text` = Profilname).
    Zählt: Runde mit Profil, fertig oder Zeit abgelaufen (gestorben/abgebrochen nicht)."""
    profile = row.get("profil", "")
    if not profile or row.get("ergebnis") not in PROFILE_RESULTS:
        return None
    try:
        errors = int(row.get("fehler") or 0)
        corrected = int(row.get("fehler_korrigiert") or 0)
        keystrokes = int(row.get("anschlaege") or 0)
    except ValueError:
        return None
    net = row.get("apm_netto")
    return Attempt(row.get("datum_zeit", ""), profile, keystrokes, errors + corrected, errors,
                   parse_num(row.get("dauer_s", "")), parse_num(row.get("apm_durchschnitt", "")),
                   parse_num(net) if net else None, row.get("eingabemodus", ""),
                   row.get("death_by_mistake") == "ja", profile)


def load_profile_attempts(path: Path = config.HISTORY_FILE) -> list[Attempt]:
    return [a for a in (profile_attempt(r) for r in load_all(path)) if a is not None]


def profile_eligible(result: SessionResult) -> bool:
    return profile_attempt(to_row(result, _DUMMY_WHEN)) is not None


def eligible(result: SessionResult) -> bool:
    return from_row(to_row(result, _DUMMY_WHEN)) is not None


def load_attempts(path: Path = config.HISTORY_FILE) -> list[Attempt]:
    return [a for a in (from_row(r) for r in load_all(path)) if a is not None]


def filter_attempts(attempts: list[Attempt], input_mode: str | None = None,
                    dbm: bool | None = None) -> list[Attempt]:
    """input_mode: z. B. "Computer" oder None (alle); dbm: True/False/None (egal)."""
    return [a for a in attempts
            if (input_mode is None or a.input_mode == input_mode)
            and (dbm is None or a.dbm == dbm)]


def ranked(attempts: list[Attempt], penalty: int) -> list[Attempt]:
    """Bester zuerst; bei Gleichstand gewinnt der frühere Versuch."""
    return sorted(attempts, key=lambda a: (-a.points(penalty), a.when))


@dataclass
class TextSummary:
    text: str
    best: Attempt | None
    attempts: int
    last: str | None     # Datum des letzten Versuchs


def summarize(attempts: list[Attempt], penalty: int,
              text_names: list[str] = ()) -> list[TextSummary]:
    """Eine Zeile pro Text – auch für Texte ohne Versuch (Übersicht aller Texte)."""
    by_text: dict[str, list[Attempt]] = defaultdict(list)
    for a in attempts:
        by_text[a.text].append(a)
    names = list(dict.fromkeys(list(text_names) + sorted(by_text)))
    out = []
    for name in names:
        tries = by_text.get(name, [])
        out.append(TextSummary(name, ranked(tries, penalty)[0] if tries else None,
                               len(tries), max((a.when for a in tries), default=None)))
    return out


def top(attempts: list[Attempt], text: str, penalty: int, n: int = 10) -> list[Attempt]:
    return ranked([a for a in attempts if a.text == text], penalty)[:n]


def best_points(attempts: list[Attempt], text: str, penalty: int) -> float | None:
    best = top(attempts, text, penalty, 1)
    return best[0].points(penalty) if best else None


def record_whens(attempts: list[Attempt], penalty: int) -> set[str]:
    """Zeitpunkte der Bestleistung je Text (für das Etikett „REKORD“)."""
    return {top(attempts, t, penalty, 1)[0].when for t in {a.text for a in attempts}}


def protected_whens(attempts: list[Attempt], penalty: int,
                    n: int = config.HIGHSCORE_TOP_N) -> set[str]:
    """Zeitpunkte der Top-n je Text – deren Auswertungen werden nie aufgeräumt."""
    keep: set[str] = set()
    for t in {a.text for a in attempts}:
        keep.update(a.when for a in top(attempts, t, penalty, n))
    return keep


from datetime import datetime  # noqa: E402  (nur für eligible())

_DUMMY_WHEN = datetime(2000, 1, 1)
