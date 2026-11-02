"""Verlauf: eine CSV-Zeile pro Runde (nur Kennzahlen, keine Einzelfehler).

Format für das deutsche Excel: UTF-8 mit BOM, Semikolon als Trenner,
Komma als Dezimalzeichen. Der BOM darf nur einmal ganz am Dateianfang
stehen – deshalb wird beim Anhängen ohne BOM geschrieben.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import config
from core.models import SessionEnd, SessionResult
from core.scoring import score

COLUMNS = [
    "datum_zeit", "textquelle", "textnamen", "zeitlimit_s", "eingabemodus",
    "death_by_mistake", "altgr", "ergebnis", "dauer_s", "anschlaege",
    "fehler", "fehler_korrigiert", "fehlerquote_prozent",
    "apm_durchschnitt", "apm_spitze", "apm_netto", "punkte", "profil", "konsistenz_prozent", "tastatur",
]
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _yes(flag: bool) -> str:
    return "ja" if flag else "nein"


def should_save(result: SessionResult) -> bool:
    """Abgebrochene Runden und Runden ohne Anschlag werden nicht gespeichert."""
    return result.end_reason is not SessionEnd.ABORTED and result.keystrokes > 0


def to_row(result: SessionResult, when: datetime,
           penalty: int = config.SCORE_PENALTY) -> dict[str, str]:
    s = result.settings
    return {
        "datum_zeit": when.strftime(DATE_FMT),
        "textquelle": s.source_mode.value,
        "textnamen": ", ".join(result.text_names),
        "zeitlimit_s": "" if s.time_limit_s is None else str(s.time_limit_s),
        "eingabemodus": s.input_mode.value,
        "death_by_mistake": _yes(s.death_by_mistake),
        "altgr": _yes(s.allow_altgr),
        "ergebnis": result.end_reason.value,
        "dauer_s": _num(result.duration_s),
        "anschlaege": str(result.keystrokes),
        "fehler": str(result.errors),
        "fehler_korrigiert": str(result.corrected),
        "fehlerquote_prozent": _num(result.error_rate),
        "apm_durchschnitt": _num(result.cpm_avg),
        "apm_spitze": _num(result.cpm_peak),
        "apm_netto": _num(result.net_cpm),
        "punkte": _num(score(result.keystrokes, result.mistakes, result.duration_s, penalty)),
        "profil": s.profile,
        "konsistenz_prozent": "" if result.consistency is None else _num(result.consistency),
        "tastatur": s.keyboard,
    }


def append(result: SessionResult, path: Path = config.HISTORY_FILE,
           when: datetime | None = None, penalty: int = config.SCORE_PENALTY) -> bool:
    """Runde anhängen. Gibt False zurück, wenn nicht gespeichert werden konnte
    (z. B. Datei in Excel geöffnet und gesperrt)."""
    if not should_save(result):
        return False
    row = to_row(result, when or datetime.now(), penalty)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _migrate_header(path)
        new_file = not path.exists() or path.stat().st_size == 0
        encoding = "utf-8-sig" if new_file else "utf-8"
        with path.open("a", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";")
            if new_file:
                writer.writeheader()
            writer.writerow(row)
        return True
    except OSError:
        return False


def _migrate_header(path: Path) -> None:
    """Ältere Datei mit anderen Spalten auf das aktuelle Format umschreiben
    (fehlende Werte bleiben leer), damit neue Zeilen nicht verrutschen."""
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        if reader.fieldnames == COLUMNS:
            return
        rows = list(reader)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_all(path: Path = config.HISTORY_FILE) -> list[dict[str, str]]:
    """Alle Runden, älteste zuerst. Fehlende/kaputte Datei -> leere Liste."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def load_recent(path: Path = config.HISTORY_FILE, n: int = 10) -> list[dict[str, str]]:
    """Die letzten n Runden, neueste zuerst. Fehlende/kaputte Datei -> leere Liste."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []
    return list(reversed(rows[-n:])) if n > 0 else []


def parse_num(value: str) -> float:
    """'248,0' -> 248.0 (leer/ungültig -> 0.0)."""
    try:
        return float(value.replace(",", "."))
    except (AttributeError, ValueError):
        return 0.0
