"""Kleine Programmeinstellungen, die über einen Neustart hinweg erhalten bleiben
(`daten/einstellungen.json`)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import config


class AppSettings:
    def __init__(self, path: Path = config.SETTINGS_FILE) -> None:
        self.path = path

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def get(self, key: str, default=None):
        return self._read().get(key, default)

    def set(self, key: str, value) -> bool:
        data = self._read()
        data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    # bequeme Zugriffe
    @property
    def penalty(self) -> int:
        try:
            return max(0, int(self.get("strafe_pro_fehler", config.SCORE_PENALTY)))
        except (TypeError, ValueError):
            return config.SCORE_PENALTY

    @penalty.setter
    def penalty(self, value: int) -> None:
        self.set("strafe_pro_fehler", int(value))

    @property
    def unit(self) -> str:
        """Anzeige-Einheit: "A/min" oder "W/min"."""
        u = self.get("einheit", "A/min")
        return u if u in ("A/min", "W/min") else "A/min"

    @unit.setter
    def unit(self, value: str) -> None:
        self.set("einheit", value)
