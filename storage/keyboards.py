"""Benannte Tastaturen (z. B. „MacBook“ mit QWERTZ, „Keychron“ mit Dvorak).

Gespeichert in `daten/einstellungen.json`:
    "tastaturen": [{"id": "standard", "name": "Standard", "layout": "qwertz"}, …],
    "aktive_tastatur": "standard"
Jede Runde merkt sich die *ID* der aktiven Tastatur (CSV-Spalte „tastatur“, Statistik,
gespeicherte Auswertung). Umbenennen ändert nur den Namen – die Zuordnung alter Runden
bleibt. Runden aus der Zeit vor dieser Funktion haben keine ID und zählen zur ersten
Tastatur „standard“; diese lässt sich deshalb umbenennen, aber nicht löschen.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.keyboard_layout import LAYOUTS
from storage.app_settings import AppSettings

DEFAULT_ID = "standard"
DELETED_NAME = "gelöschte Tastatur"


def kb_id(value: str | None) -> str:
    """Gespeicherte Tastatur-ID; ältere Runden ohne Angabe gehören zu „standard“."""
    return value or DEFAULT_ID


@dataclass(frozen=True)
class Keyboard:
    id: str
    name: str
    layout: str


class KeyboardStore:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def all(self) -> list[Keyboard]:
        raw = self.settings.get("tastaturen")
        out: list[Keyboard] = []
        if isinstance(raw, list):
            for d in raw:
                try:
                    lay = d.get("layout", "qwertz")
                    out.append(Keyboard(str(d["id"]), str(d["name"]),
                                        lay if lay in LAYOUTS else "qwertz"))
                except (AttributeError, KeyError, TypeError):
                    continue
        if not any(k.id == DEFAULT_ID for k in out):
            # erster Start bzw. Datei ohne Tastaturen: Standard-Tastatur mit dem bisher
            # eingestellten Layout anlegen
            out.insert(0, Keyboard(DEFAULT_ID, "Standard", self.settings.keyboard_layout))
        return out

    def _save(self, keyboards: list[Keyboard]) -> bool:
        return self.settings.set("tastaturen", [{"id": k.id, "name": k.name, "layout": k.layout}
                                               for k in keyboards])

    def get(self, keyboard_id: str) -> Keyboard | None:
        return next((k for k in self.all() if k.id == keyboard_id), None)

    def name_of(self, keyboard_id: str | None) -> str:
        k = self.get(kb_id(keyboard_id))
        return k.name if k else DELETED_NAME

    def active(self) -> Keyboard:
        wanted = self.settings.get("aktive_tastatur", DEFAULT_ID)
        keyboards = self.all()
        return next((k for k in keyboards if k.id == wanted), keyboards[0])

    def set_active(self, keyboard_id: str) -> bool:
        return self.get(keyboard_id) is not None and self.settings.set("aktive_tastatur", keyboard_id)

    def add(self, name: str, layout: str) -> str:
        keyboards = self.all()
        used = {k.id for k in keyboards}
        n = 1
        while f"tastatur{n}" in used:
            n += 1
        new_id = f"tastatur{n}"
        keyboards.append(Keyboard(new_id, name, layout if layout in LAYOUTS else "qwertz"))
        self._save(keyboards)
        return new_id

    def update(self, keyboard_id: str, name: str | None = None, layout: str | None = None) -> bool:
        keyboards = self.all()
        for i, k in enumerate(keyboards):
            if k.id == keyboard_id:
                keyboards[i] = Keyboard(k.id, name or k.name,
                                        layout if layout in LAYOUTS else k.layout)
                return self._save(keyboards)
        return False

    def can_delete(self, keyboard_id: str) -> bool:
        return keyboard_id != DEFAULT_ID and self.get(keyboard_id) is not None

    def delete(self, keyboard_id: str) -> bool:
        """Tastatur entfernen; ihre Runden bleiben gespeichert (Filter „Alle Tastaturen“)."""
        if not self.can_delete(keyboard_id):
            return False
        ok = self._save([k for k in self.all() if k.id != keyboard_id])
        if self.settings.get("aktive_tastatur") == keyboard_id:
            self.settings.set("aktive_tastatur", DEFAULT_ID)
        return ok

    def name_taken(self, name: str, except_id: str | None = None) -> bool:
        return any(k.name.casefold() == name.casefold() and k.id != except_id for k in self.all())
