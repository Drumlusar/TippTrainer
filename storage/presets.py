"""Phrasen-Presets: benannte Phrasenlisten in `daten/phrasen_presets.json`.

Zusätzlich wird der zuletzt verwendete Inhalt des Textfelds gemerkt, damit er
nach einem Neustart des Programms wieder da ist.
Format: {"presets": [{"name": ..., "text": ...}, ...], "zuletzt": "..."}

Vorlagen: Jede .txt-Datei in `daten/phrasen_vorlagen/` ist ein mitgeliefertes Preset
(Name = Dateiname ohne .txt, Zeilen mit # sind Kommentare). Vorlagen lassen sich laden,
aber nicht überschreiben oder löschen; ein eigenes Preset gleichen Namens hat Vorrang.
"""
from __future__ import annotations

import json
import os
import unicodedata
from pathlib import Path

import config


class PresetStore:
    def __init__(self, path: Path = config.PRESETS_FILE,
                 template_dir: Path | None = None) -> None:
        self.path = path
        # Vorlagen standardmäßig nur zur echten Preset-Datei (Tests mit eigener Datei: keine)
        if template_dir is None and path == config.PRESETS_FILE:
            template_dir = config.PRESET_TEMPLATE_DIR
        self.template_dir = template_dir

    # --- Vorlagen ---------------------------------------------------------------

    def _templates(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.template_dir is None:
            return out
        try:
            files = sorted(self.template_dir.glob("*.txt"))
            key = tuple((f.name, f.stat().st_mtime_ns) for f in files)
        except OSError:
            return out
        # Zwischenspeicher: das Phrasen-Textfeld fragt bei jeder Änderung nach
        if key == getattr(self, "_tpl_key", None):
            return dict(self._tpl_cache)
        for f in files:
            try:
                raw = f.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            lines = [l for l in raw.splitlines() if not l.lstrip().startswith("#")]
            # macOS speichert Dateinamen zerlegt (o + ¨) – für Vergleiche zusammensetzen
            out[unicodedata.normalize("NFC", f.stem)] = "\n".join(lines).strip("\n")
        self._tpl_key, self._tpl_cache = key, out
        return dict(out)

    def template_names(self) -> list[str]:
        """Vorlagen, die nicht von einem eigenen Preset gleichen Namens verdeckt werden."""
        own = set(self.own_names())
        return [n for n in self._templates() if n not in own]

    def is_template(self, name: str) -> bool:
        return name in self.template_names()

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

    def own_names(self) -> list[str]:
        return [p["name"] for p in self._read().get("presets", []) if "name" in p]

    def names(self) -> list[str]:
        """Eigene Presets, danach die Vorlagen."""
        return self.own_names() + self.template_names()

    def get(self, name: str) -> str | None:
        for p in self._read().get("presets", []):
            if p.get("name") == name:
                return p.get("text", "")
        return self._templates().get(name)

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
