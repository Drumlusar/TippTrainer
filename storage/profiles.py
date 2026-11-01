"""Test-Profile: feste Einstellungen mit einem Namen (`daten/profile.json`).

Damit lassen sich Messläufe immer unter gleichen Bedingungen wiederholen – Grundlage
für Highscores und Fortschrittskurve je Profil. Beim ersten Start werden einige
Standardprofile angelegt (Online-Stil und Textprüfungen, je Deutsch und Englisch); alle
lassen sich ändern oder löschen.

Kommen in einer neuen Programmversion Standardprofile hinzu, werden sie einmalig in eine
bestehende `profile.json` übernommen. Welche schon angeboten wurden, steht unter
„standard_angeboten“ – ein gelöschtes Standardprofil kommt daher nicht zurück.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import config
from core.models import InputMode, SessionSettings, SourceMode, settings_from_dict, settings_to_dict

# Felder, die zu einer Runde gehören, nicht zum Profil
_RUN_ONLY = ("seed", "profile")


def _online(seconds: int, wordlist: str = "englisch_200.txt") -> SessionSettings:
    return SessionSettings(SourceMode.RANDOM_WORDS, seconds, 50, None, InputMode.COMPUTER,
                           False, False, 0, wordlist=wordlist, words_lowercase=True,
                           word_min_len=2, word_max_len=6, space_skips_word=True)


def _text(group: str, seconds: int) -> SessionSettings:
    return SessionSettings(SourceMode.RANDOM_TEXT, seconds, 50, None, InputMode.COMPUTER,
                           False, False, 0, text_group=group, exam_mode=True)


DEFAULT_PROFILES: list[tuple[str, SessionSettings]] = [
    ("Online: Englisch 15 s", _online(15)),
    ("Online: Englisch 30 s", _online(30)),
    ("Online: Englisch 60 s", _online(60)),
    ("Online: Deutsch 15 s", _online(15, "deutsch_200.txt")),
    ("Online: Deutsch 30 s", _online(30, "deutsch_200.txt")),
    ("Online: Deutsch 60 s", _online(60, "deutsch_200.txt")),
    ("Text: Deutsch 5 min (Prüfung)", _text("lang_de", 300)),
    ("Text: Deutsch 10 min (Prüfung)", _text("lang_de", 600)),
    ("Text: Englisch 5 min (Prüfung)", _text("lang_en", 300)),
    ("Text: Englisch 10 min (Prüfung)", _text("lang_en", 600)),
]
# Standardprofile der ersten Version (für Dateien ohne „standard_angeboten“)
_FIRST_DEFAULTS = ["Online: Englisch 15 s", "Online: Englisch 30 s", "Online: Englisch 60 s",
                   "Text: Deutsch 5 min (Prüfung)", "Text: Deutsch 10 min (Prüfung)",
                   "Text: Englisch 5 min (Prüfung)"]


def profile_dict(s: SessionSettings) -> dict:
    d = settings_to_dict(s)
    for k in _RUN_ONLY:
        d.pop(k, None)
    return d


class ProfileStore:
    def __init__(self, path: Path = config.PROFILES_FILE) -> None:
        self.path = path

    def _read(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {"profile": [], "standard_angeboten": []}      # erster Start
        except (OSError, ValueError):
            return []
        if not isinstance(data, dict):
            return []
        profiles = data.get("profile", [])
        offered = data.get("standard_angeboten")
        if offered is None:                     # Datei aus der ersten Version
            offered = list(_FIRST_DEFAULTS)
        missing = [(n, st) for n, st in DEFAULT_PROFILES if n not in offered]
        if missing:
            names = {p.get("name") for p in profiles}
            for n, st in missing:
                if n not in names:              # gleichnamiges eigenes Profil nie überschreiben
                    profiles.append({"name": n, "einstellungen": profile_dict(st)})
                offered.append(n)
            self._write(profiles, offered)
        self._offered = offered
        return profiles

    def _write(self, profiles: list[dict], offered: list[str] | None = None) -> bool:
        if offered is None:      # save()/delete() lesen vorher, damit ist _offered gesetzt
            offered = getattr(self, "_offered", None) or [n for n, _ in DEFAULT_PROFILES]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"profile": profiles, "standard_angeboten": offered},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False

    def names(self) -> list[str]:
        return [p["name"] for p in self._read() if "name" in p]

    def get(self, name: str) -> SessionSettings | None:
        for p in self._read():
            if p.get("name") == name:
                try:
                    return settings_from_dict({**p["einstellungen"], "seed": 0})
                except (KeyError, TypeError, ValueError):
                    return None
        return None

    def save(self, name: str, settings: SessionSettings) -> bool:
        profiles = self._read()
        entry = {"name": name, "einstellungen": profile_dict(settings)}
        for i, p in enumerate(profiles):
            if p.get("name") == name:
                profiles[i] = entry
                break
        else:
            profiles.append(entry)
        return self._write(profiles)

    def delete(self, name: str) -> bool:
        return self._write([p for p in self._read() if p.get("name") != name])

    def matching(self, settings: SessionSettings) -> str:
        """Name des Profils, dessen Einstellungen exakt passen (sonst "")."""
        want = profile_dict(settings)
        for p in self._read():
            if p.get("einstellungen") == want:
                return p.get("name", "")
        return ""
