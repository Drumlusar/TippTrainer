"""Gemeinsame Datentypen (Enums und Dataclasses)."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path


class SourceMode(Enum):
    RANDOM_WORDS = "Zufällige Wörter"
    RANDOM_TEXT = "Zufälliger Text"
    SPECIFIC_TEXT = "Spezifischer Text"
    PHRASES = "Phrasen"


class InputMode(Enum):
    COMPUTER = "Computer"            # Backspace erlaubt
    TYPEWRITER = "Schreibmaschine"   # kein Backspace


class CharState(Enum):
    PENDING = "pending"      # noch nicht getippt
    CORRECT = "correct"      # richtig getippt
    WRONG = "wrong"          # falsch getippt (steht aktuell falsch da)
    CORRECTED = "corrected"  # war einmal falsch, steht jetzt richtig da


class KeyOutcome(Enum):
    CORRECT = "correct"
    WRONG = "wrong"
    IGNORED = "ignored"      # z. B. Anschlag nach Textende


class SessionEnd(Enum):
    COMPLETED = "abgeschlossen"
    TIME_UP = "zeit_abgelaufen"
    DIED = "gestorben"
    STOPPED = "beendet"          # Phrasen-Endlosmodus per Esc beendet (mit Auswertung)
    ABORTED = "abgebrochen"


@dataclass(frozen=True)
class ErrorInfo:
    """Letzter Fehler, z. B. für den Deathscreen: erwartet „e“ – getippt „r“."""
    position: int
    expected: str
    typed: str


@dataclass(frozen=True)
class SessionSettings:
    source_mode: SourceMode
    time_limit_s: int | None          # None = kein Zeitlimit
    word_count: int                   # nur RANDOM_WORDS ohne Zeitlimit
    specific_file: Path | None
    input_mode: InputMode
    death_by_mistake: bool
    allow_altgr: bool
    seed: int                         # gleicher Seed -> gleicher Text beim Neustart
    wordlist: str = ""                # nur Zufällige Wörter: Dateiname der Liste ("" = Standard)
    words_lowercase: bool = False     # Wörter: nur Kleinbuchstaben, ohne Satzzeichen/Ziffern
    word_min_len: int = 0             # Wörter: Mindestlänge (0 = egal)
    word_max_len: int = 0             # Wörter: Höchstlänge (0 = egal)
    text_group: str = ""              # Zufälliger Text: nur Dateien dieser Gruppe ("" = alle)
    space_skips_word: bool = False    # Leertaste mitten im Wort springt zum nächsten (wie online)
    exam_mode: bool = False           # Prüfungsmodus: keine Live-Fehler, kein Live-Tempo
    profile: str = ""                 # Name des Test-Profils, falls mit einem gestartet
    keyboard: str = ""            # ID der Tastatur, auf der getippt wurde ("" = ältere Runde)
    # --- nur Phrasen-Modus ---
    phrases: tuple[str, ...] = ()
    repetitions: int | None = None    # Durchgänge; None = unendlich (Esc beendet)
    shuffle: bool = False             # Reihenfolge je Durchgang zufällig
    restart_phrase_on_error: bool = False
    phrase_set_name: str = ""         # Name des Presets (für Anzeige/Verlauf)

    @property
    def endless(self) -> bool:
        """Text wird nachgeladen (Zeitlimit oder unendliche Phrasen)."""
        return self.time_limit_s is not None or (
            self.source_mode is SourceMode.PHRASES and self.repetitions is None)


@dataclass
class PhraseStat:
    """Auswertung einer Phrase über alle ihre Durchgänge."""
    phrase: str
    reps: int            # vollständig getippte Durchgänge
    keystrokes: int      # Anschläge in vollständigen Durchgängen
    duration_s: float    # Zeit für vollständige Durchgänge
    mistakes: int        # alle Fehler in dieser Phrase (auch korrigierte)

    @property
    def cpm(self) -> float:
        return self.keystrokes / self.duration_s * 60 if self.duration_s > 0 else 0.0


@dataclass
class SessionResult:
    settings: SessionSettings
    end_reason: SessionEnd
    text_names: list[str]
    target_text: str
    char_states: list[CharState]
    duration_s: float
    keystrokes: int
    errors: int                       # stehende Fehler (im Computer-Modus ohne gelöschte)
    mistakes: int                     # alle falschen Anschläge, auch korrigierte
    cpm_avg: float
    cpm_peak: float
    typed_chars: int = 0              # Zeichen im Ergebnistext, die getippt wurden
    progress: float | None = None     # 0–1, None bei Zeitlimit
    last_error: ErrorInfo | None = None
    cpm_series: list[float] = field(default_factory=list)
    error_times_s: list[float] = field(default_factory=list)
    phrase_stats: list[PhraseStat] = field(default_factory=list)
    consistency: float | None = None              # 0–100 %, gleichmäßiges Tempo = hoch
    thirds: list[tuple[float, float]] = field(default_factory=list)   # je Drittel (A/min, Fehler-%)

    @property
    def corrected(self) -> int:
        return self.mistakes - self.errors

    @property
    def net_cpm(self) -> float:
        """Netto: nur richtig stehende Zeichen pro Minute."""
        correct = max(0, self.typed_chars - self.errors)
        return correct / max(self.duration_s, 1.0) * 60 if self.typed_chars else 0.0

    @property
    def error_rate(self) -> float:
        """Anteil falscher Zeichen im getippten Text, in Prozent."""
        return self.errors / self.typed_chars * 100 if self.typed_chars else 0.0


# --- (De-)Serialisierung der Einstellungen (Verlauf, Profile) -------------------------------

def settings_to_dict(s: SessionSettings) -> dict:
    out = {}
    for f in fields(s):
        v = getattr(s, f.name)
        if isinstance(v, Enum):
            v = v.name
        elif isinstance(v, Path):
            v = str(v)
        elif isinstance(v, tuple):
            v = list(v)
        out[f.name] = v
    return out


def settings_from_dict(d: dict) -> SessionSettings:
    """Fehlende (neuere) Felder bekommen ihren Standardwert."""
    kwargs = {}
    for f in fields(SessionSettings):
        if f.name not in d:
            continue
        v = d[f.name]
        if f.name == "source_mode":
            v = SourceMode[v]
        elif f.name == "input_mode":
            v = InputMode[v]
        elif f.name == "specific_file":
            v = Path(v) if v else None
        elif f.name == "phrases":
            v = tuple(v or ())
        kwargs[f.name] = v
    return SessionSettings(**kwargs)
