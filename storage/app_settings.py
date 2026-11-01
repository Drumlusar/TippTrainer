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

    # --- Darstellung ---------------------------------------------------------------

    def _num(self, key: str, default, lo, hi, cast=int):
        try:
            return min(hi, max(lo, cast(self.get(key, default))))
        except (TypeError, ValueError):
            return default

    @property
    def design(self) -> str:
        """ "Dunkel" oder "Hell" """
        d = self.get("design", "Dunkel")
        return d if d in ("Dunkel", "Hell") else "Dunkel"

    @design.setter
    def design(self, value: str) -> None:
        self.set("design", value)

    @property
    def text_size(self) -> int:
        """Schriftgröße des Tipptexts in Punkt."""
        return self._num("schrift_tipptext", 26, 12, 60)

    @text_size.setter
    def text_size(self, value: int) -> None:
        self.set("schrift_tipptext", int(value))

    @property
    def ui_scale(self) -> int:
        """Schriftgröße der Oberfläche in Prozent."""
        return self._num("schrift_oberflaeche", 100, 80, 160)

    @ui_scale.setter
    def ui_scale(self, value: int) -> None:
        self.set("schrift_oberflaeche", int(value))

    @property
    def pace_on(self) -> bool:
        return bool(self.get("tempo_cursor", False))

    @pace_on.setter
    def pace_on(self, value: bool) -> None:
        self.set("tempo_cursor", bool(value))

    @property
    def pace_cpm(self) -> float:
        """Zieltempo des Tempo-Cursors, immer in A/min gespeichert (100 W/min = 500 A/min)."""
        return self._num("tempo_cursor_apm", 500.0, 25.0, 2000.0, float)

    @pace_cpm.setter
    def pace_cpm(self, value: float) -> None:
        self.set("tempo_cursor_apm", float(value))
