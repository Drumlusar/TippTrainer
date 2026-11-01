"""Tagesweise Tippstatistik in `daten/verlauf/statistik.json`.

Format: {"version": 1, "tage": {"2026-11-01": {"zeichen": …, "verwechslungen": …, "woerter": …}}}
Gespeichert werden nur Summen pro Tag – kein Protokoll einzelner Anschläge.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import config
from core.char_stats import Stats


class StatsStore:
    def __init__(self, path: Path = config.STATS_FILE) -> None:
        self.path = path

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def add(self, day: date, stats: Stats, sign: int = 1) -> bool:
        """Runde zur Tagessumme addieren (sign = −1: wieder herausrechnen)."""
        data = self._read()
        days = data.setdefault("tage", {})
        key = day.isoformat()
        merged = Stats.from_json(days.get(key, {})).merge(stats.scaled(sign)).drop_empty()
        days[key] = merged.to_json()
        data["version"] = 1
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    def load(self, last_days: int | None = None, today: date | None = None) -> Stats:
        """Summe über die letzten `last_days` Tage (inkl. heute) oder alles (None)."""
        today = today or date.today()
        first = None if last_days is None else (today - timedelta(days=last_days - 1)).isoformat()
        total = Stats()
        for day, d in self._read().get("tage", {}).items():
            if first is None or day >= first:
                total.merge(Stats.from_json(d))
        return total
