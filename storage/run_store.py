"""Einzelne Runden mit allen Daten für den Endbildschirm speichern.

Eine kompakte JSON-Datei pro Runde in `daten/verlauf/runs/`:
Einstellungen, Text, Zustand jedes Zeichens (als ein Buchstabe pro Zeichen),
A/min-Verlauf und Fehlerzeitpunkte – typischerweise wenige KB.

Aufbewahrung: Die letzten `KEEP_RECENT_RUNS` Runden bleiben erhalten,
ältere werden beim Speichern einer neuen Runde gelöscht – außer sie sind
mit ★ markiert („dauerhaft speichern“). Die CSV `sessions.csv` mit den
Kennzahlen aller Runden bleibt davon unberührt.
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import config
from core.models import (CharState, ErrorInfo, PhraseStat, SessionEnd, SessionResult,
                         settings_from_dict, settings_to_dict)
from core.char_stats import Stats
from storage.history import should_save

FORMAT_VERSION = 1
DATE_FMT = "%Y-%m-%d %H:%M:%S"

STATE_TO_CODE = {CharState.CORRECT: "c", CharState.WRONG: "w",
                 CharState.CORRECTED: "k", CharState.PENDING: "p"}
CODE_TO_STATE = {v: k for k, v in STATE_TO_CODE.items()}


@dataclass
class StoredRun:
    id: str
    when: datetime
    pinned: bool
    result: SessionResult
    stats: Stats | None = None     # Beitrag dieser Runde zur Statistik (None = zählt nie)
    in_stats: bool = False         # aktuell in der Statistik enthalten?


# --- (De-)Serialisierung ------------------------------------------------------------

def to_dict(result: SessionResult, when: datetime, pinned: bool = False) -> dict:
    s = result.settings
    err = result.last_error
    return {
        "version": FORMAT_VERSION,
        "datum_zeit": when.strftime(DATE_FMT),
        "pinned": pinned,
        "settings": settings_to_dict(s),
        "end_reason": result.end_reason.name,
        "text_names": result.text_names,
        "text": result.target_text,
        "states": "".join(STATE_TO_CODE[st] for st in result.char_states),
        "duration_s": round(result.duration_s, 3),
        "keystrokes": result.keystrokes,
        "errors": result.errors,
        "mistakes": result.mistakes,
        "typed_chars": result.typed_chars,
        "cpm_avg": round(result.cpm_avg, 2),
        "cpm_peak": round(result.cpm_peak, 2),
        "cpm_series": [round(v, 1) for v in result.cpm_series],
        "error_times_s": [round(t, 2) for t in result.error_times_s],
        "progress": result.progress,
        "last_error": None if err is None else
            {"position": err.position, "expected": err.expected, "typed": err.typed},
        "phrase_stats": [
            {"phrase": p.phrase, "reps": p.reps, "keystrokes": p.keystrokes,
             "duration_s": round(p.duration_s, 3), "mistakes": p.mistakes}
            for p in result.phrase_stats],
        "consistency": None if result.consistency is None else round(result.consistency, 1),
        "thirds": [[round(c, 1), round(e, 2)] for c, e in result.thirds],
    }


def from_dict(d: dict) -> tuple[datetime, bool, SessionResult]:
    settings = settings_from_dict(d["settings"])
    err = d.get("last_error")
    result = SessionResult(
        settings=settings,
        end_reason=SessionEnd[d["end_reason"]],
        text_names=list(d["text_names"]),
        target_text=d["text"],
        char_states=[CODE_TO_STATE[c] for c in d["states"]],
        duration_s=d["duration_s"],
        keystrokes=d["keystrokes"],
        errors=d["errors"],
        mistakes=d["mistakes"],
        cpm_avg=d["cpm_avg"],
        cpm_peak=d["cpm_peak"],
        typed_chars=d["typed_chars"],
        progress=d.get("progress"),
        last_error=ErrorInfo(**err) if err else None,
        cpm_series=list(d["cpm_series"]),
        error_times_s=list(d["error_times_s"]),
        phrase_stats=[PhraseStat(**p) for p in d.get("phrase_stats", [])],
        consistency=d.get("consistency"),
        thirds=[tuple(x) for x in d.get("thirds", [])],
    )
    return datetime.strptime(d["datum_zeit"], DATE_FMT), bool(d.get("pinned")), result


# --- Speicher -----------------------------------------------------------------------

class RunStore:
    def __init__(self, directory: Path = config.RUNS_DIR,
                 keep_recent: int = config.KEEP_RECENT_RUNS) -> None:
        self.dir = directory
        self.keep_recent = keep_recent

    def _path(self, run_id: str) -> Path:
        return self.dir / f"{run_id}.json"

    def _write(self, run_id: str, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f".{run_id}.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, self._path(run_id))   # erst komplett schreiben, dann umbenennen

    def save(self, result: SessionResult, when: datetime | None = None,
             protected: set[str] = frozenset(), stats: Stats | None = None) -> str | None:
        """Runde speichern und alte, nicht markierte Runden aufräumen.
        `protected`: Zeitpunkte („JJJJ-MM-TT hh:mm:ss“), die nie gelöscht werden
        (z. B. Highscore-Runden). Gibt die ID zurück oder None."""
        if not should_save(result):
            return None
        when = when or datetime.now()
        run_id = f"{when:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        try:
            data = to_dict(result, when)
            if stats is not None:
                data["statistik"] = stats.to_json()
                data["in_statistik"] = True
            self._write(run_id, data)
            self.prune(protected)
        except OSError:
            return None
        return run_id

    def load(self, run_id: str) -> StoredRun | None:
        try:
            d = json.loads(self._path(run_id).read_text("utf-8"))
            when, pinned, result = from_dict(d)
            stats = Stats.from_json(d["statistik"]) if d.get("statistik") is not None else None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        return StoredRun(run_id, when, pinned, result, stats, bool(d.get("in_statistik")))

    def set_in_stats(self, run_id: str, include: bool) -> bool:
        try:
            data = json.loads(self._path(run_id).read_text("utf-8"))
            data["in_statistik"] = include
            self._write(run_id, data)
            return True
        except (OSError, ValueError):
            return False

    def list_runs(self) -> list[StoredRun]:
        """Alle lesbaren Runden, neueste zuerst. Kaputte Dateien werden übersprungen."""
        if not self.dir.is_dir():
            return []
        runs = [self.load(p.stem) for p in self.dir.glob("*.json")]
        return sorted((r for r in runs if r), key=lambda r: (r.when, r.id), reverse=True)

    def set_pinned(self, run_id: str, pinned: bool) -> bool:
        try:
            data = json.loads(self._path(run_id).read_text("utf-8"))
            data["pinned"] = pinned
            self._write(run_id, data)
            return True
        except (OSError, ValueError):
            return False

    def find_by_when(self, when: str, text: str | None = None) -> StoredRun | None:
        for run in self.list_runs():
            if run.when.strftime(DATE_FMT) == when and (
                    text is None or run.result.text_names == [text]):
                return run
        return None

    def prune(self, protected: set[str] = frozenset()) -> None:
        """Nicht markierte Runden über `keep_recent` hinaus löschen (älteste zuerst).
        Markierte (★) und geschützte (Highscore) Runden bleiben immer."""
        unpinned = [r for r in self.list_runs()
                    if not r.pinned and r.when.strftime(DATE_FMT) not in protected]
        for run in unpinned[self.keep_recent:]:
            try:
                self._path(run.id).unlink()
            except OSError:
                pass
