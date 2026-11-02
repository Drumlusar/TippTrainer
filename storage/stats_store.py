"""Tagesweise Tippstatistik je Tastatur in `daten/verlauf/statistik.json`.

Format (Version 2):
    {"version": 2, "tastaturen": {"standard": {"2026-11-01": {"zeichen": …, …}}, …}}
Version 1 (ohne Tastaturen: {"version": 1, "tage": {…}}) wird beim Lesen der
Tastatur „standard“ zugeordnet und beim nächsten Schreiben umgestellt.
Gespeichert werden nur Summen pro Tag – kein Protokoll einzelner Anschläge.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import config
from core.char_stats import Stats

DEFAULT_KEYBOARD = "standard"


class StatsStore:
    def __init__(self, path: Path = config.STATS_FILE) -> None:
        self.path = path

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _keyboards(self) -> dict[str, dict]:
        """{Tastatur-ID: {Tag: Summen}} – auch aus einer Datei im alten Format."""
        data = self._read()
        kbs = data.get("tastaturen")
        if isinstance(kbs, dict):
            return {k: v for k, v in kbs.items() if isinstance(v, dict)}
        old = data.get("tage")
        return {DEFAULT_KEYBOARD: old} if isinstance(old, dict) else {}

    def add(self, day: date, stats: Stats, sign: int = 1, keyboard: str = "") -> bool:
        """Runde zur Tagessumme ihrer Tastatur addieren (sign = −1: wieder herausrechnen)."""
        kbs = self._keyboards()
        days = kbs.setdefault(keyboard or DEFAULT_KEYBOARD, {})
        key = day.isoformat()
        merged = Stats.from_json(days.get(key, {})).merge(stats.scaled(sign)).drop_empty()
        days[key] = merged.to_json()
        data = {"version": 2, "tastaturen": kbs}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    def load(self, last_days: int | None = None, today: date | None = None,
             keyboard: str | None = None) -> Stats:
        """Summe über die letzten `last_days` Tage (inkl. heute) oder alles (None);
        nur eine Tastatur (ID) oder alle (None)."""
        today = today or date.today()
        first = None if last_days is None else (today - timedelta(days=last_days - 1)).isoformat()
        total = Stats()
        for kb, days in self._keyboards().items():
            if keyboard is not None and kb != (keyboard or DEFAULT_KEYBOARD):
                continue
            for day, d in days.items():
                if first is None or day >= first:
                    total.merge(Stats.from_json(d))
        return total

    def keyboards_with_data(self) -> set[str]:
        return {kb for kb, days in self._keyboards().items() if days}
