"""Phrasen-Presets: benannte Phrasenlisten in `daten/phrasen_presets.json`.

Zusätzlich wird der zuletzt verwendete Inhalt des Textfelds gemerkt, damit er
nach einem Neustart des Programms wieder da ist.
Format: {"presets": [{"name": ..., "text": ...}, ...], "zuletzt": "..."}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import config


class PresetStore:
    def __init__(self, path: Path = config.PRESETS_FILE) -> None:
        self.path = path

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {}

    def _write(self, data: dict) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    # --- Presets ---------------------------------------------------------------

    def names(self) -> list[str]:
        return [p["name"] for p in self._read().get("presets", []) if "name" in p]

    def get(self, name: str) -> str | None:
        for p in self._read().get("presets", []):
            if p.get("name") == name:
                return p.get("text", "")
        return None

    def save(self, name: str, text: str) -> bool:
        """Neu anlegen oder überschreiben (Position bleibt beim Überschreiben erhalten)."""
        data = self._read()
        presets = data.setdefault("presets", [])
        for p in presets:
            if p.get("name") == name:
                p["text"] = text
                break
        else:
            presets.append({"name": name, "text": text})
        return self._write(data)

    def delete(self, name: str) -> bool:
        data = self._read()
        data["presets"] = [p for p in data.get("presets", []) if p.get("name") != name]
        return self._write(data)

    # --- zuletzt verwendet --------------------------------------------------------

    def last_text(self) -> str:
        return self._read().get("zuletzt", "")

    def set_last_text(self, text: str) -> bool:
        data = self._read()
        if data.get("zuletzt") == text:
            return True
        data["zuletzt"] = text
        return self._write(data)
