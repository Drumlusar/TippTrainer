"""Tipplogik: Cursor, Fehler und Zustand jedes Zeichens.

Die Engine kennt keine Zeit. Wann ein Anschlag passiert ist, verwaltet
`Metrics`; der SessionController reicht jeden Anschlag an beide weiter.
"""
from __future__ import annotations

from core.models import CharState, ErrorInfo, InputMode, KeyOutcome

__all__ = ["TypingEngine", "ErrorInfo"]


class TypingEngine:
    def __init__(self, target: str, input_mode: InputMode) -> None:
        if not target:
            raise ValueError("Zieltext darf nicht leer sein.")
        self.target = target
        self.input_mode = input_mode
        self.pos = 0
        self.states: list[CharState] = [CharState.PENDING] * len(target)
        self.errors = 0          # aktuell stehende (nicht korrigierte) Fehler
        self.mistakes = 0        # alle jemals falsch getippten Anschläge
        self.keystrokes = 0
        self.ever_wrong: set[int] = set()   # Positionen, die jemals falsch waren
        self.last_error: ErrorInfo | None = None

    # --- Eingabe -----------------------------------------------------------

    def type_char(self, ch: str) -> KeyOutcome:
        """Ein getipptes Zeichen verarbeiten. Enter wird als "\\n" übergeben."""
        if len(ch) != 1:
            raise ValueError(f"Genau ein Zeichen erwartet, bekommen: {ch!r}")
        if self.finished:
            return KeyOutcome.IGNORED

        expected = self.target[self.pos]
        self.keystrokes += 1
        if ch == expected:
            self.states[self.pos] = (
                CharState.CORRECTED if self.pos in self.ever_wrong else CharState.CORRECT
            )
            outcome = KeyOutcome.CORRECT
        else:
            self.states[self.pos] = CharState.WRONG
            self.ever_wrong.add(self.pos)
            self.errors += 1
            self.mistakes += 1
            self.last_error = ErrorInfo(self.pos, expected, ch)
            outcome = KeyOutcome.WRONG
        self.pos += 1
        return outcome

    def skip_word(self) -> int:
        """Leertaste mitten im Wort (Online-Verhalten): Rest des Wortes gilt als
        verpasst (falsch), der Cursor springt hinter das nächste Leerzeichen.
        Gibt die Zahl der verpassten Zeichen zurück."""
        n = len(self.target)
        j = self.pos
        while j < n and self.target[j] not in " \n":
            j += 1
        missed = j - self.pos
        if missed:
            self.last_error = ErrorInfo(self.pos, self.target[self.pos], " ")
        for i in range(self.pos, j):
            self.states[i] = CharState.WRONG
            self.ever_wrong.add(i)
        self.errors += missed
        self.mistakes += missed
        self.keystrokes += 1
        if j < n:                                  # das Leerzeichen selbst ist richtig
            self.states[j] = CharState.CORRECT
            j += 1
        self.pos = j
        return missed

    def backspace(self) -> bool:
        """Ein Zeichen zurück. Gibt False zurück, wenn nichts passiert ist."""
        if self.input_mode is InputMode.TYPEWRITER or self.pos == 0:
            return False
        self.pos -= 1
        if self.states[self.pos] is CharState.WRONG:
            self.errors -= 1                         # gelöschter Fehler zählt nicht mehr
        self.states[self.pos] = CharState.PENDING   # ever_wrong bleibt erhalten!
        return True

    @property
    def corrected(self) -> int:
        """Anzahl Fehler, die per Backspace korrigiert wurden."""
        return self.mistakes - self.errors

    def rewind_to(self, position: int) -> None:
        """Cursor auf eine frühere Position zurücksetzen (Phrase neu beginnen).
        Alles dahinter wird wieder „noch zu tippen“; stehende Fehler dort werden
        abgezogen, bleiben aber als gemachte Fehler (mistakes) gezählt."""
        position = max(0, min(position, self.pos))
        for i in range(position, self.pos):
            if self.states[i] is CharState.WRONG:
                self.errors -= 1
            self.states[i] = CharState.PENDING
        self.pos = position

    def append_text(self, more: str) -> None:
        """Text hinten anhängen (Nachladen im Zeitlimit-Modus)."""
        self.target += more
        self.states.extend([CharState.PENDING] * len(more))

    # --- Abfragen ----------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self.pos >= len(self.target)

    @property
    def remaining(self) -> int:
        return len(self.target) - self.pos

    @property
    def progress(self) -> float:
        """Fortschritt 0.0–1.0."""
        return self.pos / len(self.target)
