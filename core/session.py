"""SessionController: steuert den Ablauf einer Runde.

Verbindet TextSource, TypingEngine und Metrics und entscheidet über
Start, Ende (fertig / Zeit abgelaufen / gestorben / abgebrochen),
Nachladen und Neustart. Qt-frei: Alle Methoden nehmen optional `now`
entgegen, damit Tests mit künstlicher Zeit arbeiten können. Ohne `now`
wird die übergebene Uhr (Standard: time.perf_counter) gefragt.
"""
from __future__ import annotations

import random
import time
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable

import config
from core.char_stats import Stats, collect, words_with_mistakes
from core.metrics import Metrics
from core.models import (InputMode, KeyOutcome, PhraseStat, SessionEnd,
                         SessionResult, SessionSettings, SourceMode)
from core.text_source import TextChunk, TextLibrary, TextSource, build_source
from core.typing_engine import ErrorInfo, TypingEngine


class SessionState(Enum):
    WAITING = "waiting"   # Text steht, Zeit läuft noch nicht
    RUNNING = "running"
    ENDED = "ended"


@dataclass(frozen=True)
class Segment:
    """Ein Vorkommen einer Phrase im Zieltext; das Enter danach gehört dazu."""
    start: int
    end: int          # exklusiv
    phrase: int       # Index in source.phrases
    round: int        # Durchgang (0-basiert)


def new_seed() -> int:
    return random.randrange(2**32)


class SessionController:
    def __init__(self, library: TextLibrary,
                 clock: Callable[[], float] = time.perf_counter) -> None:
        self.library = library
        self.clock = clock
        self.settings: SessionSettings | None = None
        self.state = SessionState.ENDED
        self.end_reason: SessionEnd | None = None
        self.engine: TypingEngine | None = None
        self.metrics = Metrics()
        self._source: TextSource | None = None
        self._chunk_starts: list[tuple[int, str]] = []   # (Startposition, Name) je Chunk
        self._segments: list[Segment] = []                # nur Phrasen-Modus
        self._chunk_count = 0
        # pro Zeichenposition: Zeitpunkt des letzten Anschlags, Anzahl Anschläge/Fehler
        self._pos_time: dict[int, float] = {}
        self._pos_keys: Counter = Counter()
        self._pos_mistakes: Counter = Counter()
        self._keylog: list[tuple[str, str, float | None]] = []   # (erwartet, getippt, Abstand s)
        self._last_event: float | None = None

    # --- Start / Neustart -------------------------------------------------

    def start(self, settings: SessionSettings) -> None:
        """Neue Runde mit diesen Einstellungen (inkl. Seed) vorbereiten."""
        self.settings = settings
        self._source = build_source(settings, self.library)
        self.engine = None
        self._chunk_starts, self._segments, self._chunk_count = [], [], 0
        self._pos_time, self._pos_keys, self._pos_mistakes = {}, Counter(), Counter()
        self._keylog, self._last_event = [], None
        self._append_chunk(self._source.next_chunk())
        if settings.source_mode is SourceMode.PHRASES and settings.repetitions:
            for _ in range(settings.repetitions - 1):        # feste Anzahl Durchgänge
                self._append_chunk(self._source.next_chunk())
        self.metrics = Metrics()
        self.state = SessionState.WAITING
        self.end_reason = None
        self._refill_if_needed()

    def restart(self) -> None:
        """Gleiche Einstellungen, gleicher Seed -> exakt gleicher Text."""
        self._require_settings()
        self.start(self.settings)

    def new_text(self) -> None:
        """Gleiche Einstellungen, neuer Seed -> neuer Text."""
        self._require_settings()
        self.start(replace(self.settings, seed=new_seed()))

    # --- Eingabe ------------------------------------------------------------

    def on_char(self, ch: str, now: float | None = None) -> KeyOutcome:
        now = self._now(now)
        if self.state is SessionState.ENDED or self._check_time_up(now):
            return KeyOutcome.IGNORED

        idx = self.engine.pos
        target = self.engine.target
        expected = target[idx] if idx < len(target) else None
        if (self.settings.space_skips_word and ch == " " and expected is not None
                and expected not in " \n"):
            if idx == 0 or target[idx - 1] in " \n":
                return KeyOutcome.IGNORED          # Wort noch nicht begonnen: wie online ignorieren
            missed = self.engine.skip_word()
            outcome = KeyOutcome.WRONG if missed else KeyOutcome.CORRECT
        else:
            outcome = self.engine.type_char(ch)
        if outcome is KeyOutcome.IGNORED:
            return outcome
        dt = None if self._last_event is None else now - self._last_event
        self._keylog.append((expected, ch, dt))
        self._last_event = now

        wrong = outcome is KeyOutcome.WRONG
        self.metrics.record_keystroke(now, is_error=wrong)
        self._pos_time[idx] = now
        self._pos_keys[idx] += 1
        if wrong:
            self._pos_mistakes[idx] += 1
        self.state = SessionState.RUNNING

        if wrong and self.settings.death_by_mistake:
            self._end(SessionEnd.DIED, now)
            return outcome
        if wrong and self.settings.restart_phrase_on_error:
            seg = self._segment_at(idx)
            if seg is not None:
                self.engine.rewind_to(seg.start)          # Phrase von vorne
        if self.engine.finished and not self.settings.endless:
            self._end(SessionEnd.COMPLETED, now)
        else:
            self._refill_if_needed()
        return outcome

    def on_backspace(self, now: float | None = None) -> bool:
        now = self._now(now)
        if self.state is not SessionState.RUNNING or self._check_time_up(now):
            return False
        if self.settings.input_mode is InputMode.TYPEWRITER:
            return False
        done = self.engine.backspace()
        if done:
            self._last_event = now    # Tempo des nächsten Zeichens ab dem Backspace messen
        return done

    def tick(self, now: float | None = None) -> None:
        """Regelmäßig von der UI aufgerufen: Zeitlimit prüfen, Verlauf füllen."""
        now = self._now(now)
        if self.state is SessionState.RUNNING and not self._check_time_up(now):
            self.metrics.sample(now)

    @property
    def can_stop(self) -> bool:
        """Esc beendet mit Auswertung statt abzubrechen (Phrasen, unendlich, schon getippt)."""
        s = self.settings
        return (s is not None and self.state is SessionState.RUNNING
                and s.source_mode is SourceMode.PHRASES and s.repetitions is None)

    def stop(self, now: float | None = None) -> None:
        if self.can_stop:
            self._end(SessionEnd.STOPPED, self._now(now))

    def abort(self, now: float | None = None) -> None:
        """Esc: Runde abbrechen (wird später nicht gespeichert)."""
        if self.state is not SessionState.ENDED:
            self._end(SessionEnd.ABORTED, self._now(now))

    # --- Live-Werte für die Anzeige -----------------------------------------

    def live_cpm(self, now: float | None = None) -> float:
        if self.state is not SessionState.RUNNING:
            return 0.0
        return self.metrics.live_cpm(self._now(now))

    def elapsed(self, now: float | None = None) -> float:
        if not self.metrics.started:
            return 0.0
        return self.metrics.duration(self._now(now))

    def remaining_time(self, now: float | None = None) -> float | None:
        """Restzeit in s, None ohne Zeitlimit."""
        if self.settings is None or self.settings.time_limit_s is None:
            return None
        return max(0.0, self.settings.time_limit_s - self.elapsed(now))

    @property
    def progress(self) -> float | None:
        """Fortschritt 0–1; None mit Zeitlimit (Text ist dort endlos)."""
        if self.engine is None or self.settings.endless:
            return None
        return self.engine.progress

    @property
    def phrase_round(self) -> tuple[int, int | None] | None:
        """(aktueller Durchgang, Gesamtzahl oder None) – nur Phrasen-Modus."""
        if not self._segments:
            return None
        seg = self._segment_at(min(self.engine.pos, len(self.engine.target) - 1))
        current = (seg.round if seg else 0) + 1
        return current, self.settings.repetitions

    @property
    def last_error(self) -> ErrorInfo | None:
        return self.engine.last_error if self.engine else None

    @property
    def text_names(self) -> list[str]:
        """Namen der Texte, von denen mindestens ein Zeichen getippt wurde
        (der erste immer), ohne Doppelungen."""
        pos = self.engine.pos if self.engine else 0
        names: list[str] = []
        for i, (start, name) in enumerate(self._chunk_starts):
            if (i == 0 or start < pos) and name not in names:
                names.append(name)
        return names

    # --- Ergebnis -------------------------------------------------------------

    def result(self) -> SessionResult:
        if self.state is not SessionState.ENDED:
            raise RuntimeError("Runde läuft noch.")
        e, m = self.engine, self.metrics
        if self.settings.endless:
            # Bei nachgeladenem Text nur den erreichten Teil zeigen, nicht den Puffer.
            # Beim Tod etwas Folgetext behalten, damit der Deathscreen Kontext zeigt.
            cut = e.pos + 30 if self.end_reason is SessionEnd.DIED else e.pos
            text, states = e.target[:cut], e.states[:cut]
        else:
            text, states = e.target, list(e.states)
        avg = m.average_cpm()
        return SessionResult(
            settings=self.settings,
            end_reason=self.end_reason,
            text_names=self.text_names,
            target_text=text,
            char_states=states,
            duration_s=m.duration(),
            keystrokes=e.keystrokes,
            errors=e.errors,
            mistakes=e.mistakes,
            cpm_avg=avg,
            cpm_peak=m.peak_cpm() if m.series else avg,
            typed_chars=e.pos,
            progress=self.progress,
            last_error=e.last_error,
            cpm_series=list(m.series),
            error_times_s=list(m.error_times),
            phrase_stats=self._phrase_stats(),
            consistency=self._consistency(),
            thirds=self._thirds(),
        )

    def _consistency(self) -> float | None:
        """Gleichmäßigkeit des Tempos in % (100 = völlig gleichmäßig).
        Anschläge je 2-Sekunden-Abschnitt; 100 × (1 − Streuung / Mittelwert)."""
        m = self.metrics
        if not m.started:
            return None
        bucket = config.CONSISTENCY_BUCKET_S
        n = int(m.duration() // bucket)
        if n < 4:
            return None
        counts = [0] * n
        for t in m.keystroke_times:
            k = int((t - m.start_time) // bucket)
            if k < n:
                counts[k] += 1
        mean = sum(counts) / n
        if mean == 0:
            return None
        std = (sum((c - mean) ** 2 for c in counts) / n) ** 0.5
        return max(0.0, min(100.0, 100 * (1 - std / mean)))

    def _thirds(self) -> list[tuple[float, float]]:
        """Ausdauer: A/min und Fehlerquote im 1., 2. und 3. Drittel (ab 30 s Dauer)."""
        m = self.metrics
        if not m.started or m.duration() < config.THIRDS_MIN_S:
            return []
        third = m.duration() / 3
        keys, errs = [0, 0, 0], [0, 0, 0]
        for t in m.keystroke_times:
            keys[min(2, int((t - m.start_time) // third))] += 1
        for t in m.error_times:
            errs[min(2, int(t // third))] += 1
        return [(keys[i] / third * 60, errs[i] / keys[i] * 100 if keys[i] else 0.0)
                for i in range(3)]

    def typing_stats(self) -> Stats:
        """Zeichen-/Wortstatistik dieser Runde (für den Reiter „Statistik“)."""
        words = words_with_mistakes(self.engine.target, self.engine.pos, self._pos_mistakes)
        return collect(self._keylog, words)

    def _phrase_stats(self) -> list[PhraseStat]:
        """Je Phrase: vollständige Durchgänge, deren Anschläge und Zeit, alle Fehler."""
        if not self._segments:
            return []
        phrases = self._source.phrases
        reps = [0] * len(phrases)
        keys = [0] * len(phrases)
        dur = [0.0] * len(phrases)
        mistakes = [0] * len(phrases)
        pos = self.engine.pos
        for seg in self._segments:
            rng = range(seg.start, seg.end)
            mistakes[seg.phrase] += sum(self._pos_mistakes[i] for i in rng)
            if seg.end > pos:                       # nicht vollständig getippt
                continue
            begin = (self._pos_time.get(seg.start - 1, self.metrics.start_time)
                     if seg.start > 0 else self.metrics.start_time)
            end = self._pos_time.get(seg.end - 1, begin)
            reps[seg.phrase] += 1
            keys[seg.phrase] += sum(self._pos_keys[i] for i in rng)
            dur[seg.phrase] += max(0.0, end - begin)
        return [PhraseStat(phrases[i], reps[i], keys[i], dur[i], mistakes[i])
                for i in range(len(phrases)) if reps[i] or mistakes[i]]

    # --- intern ----------------------------------------------------------------

    def _now(self, now: float | None) -> float:
        return self.clock() if now is None else now

    def _require_settings(self) -> None:
        if self.settings is None:
            raise RuntimeError("Noch keine Runde gestartet.")

    def _deadline(self) -> float | None:
        if self.settings.time_limit_s is None or not self.metrics.started:
            return None
        return self.metrics.start_time + self.settings.time_limit_s

    def _check_time_up(self, now: float) -> bool:
        """Beendet die Runde, wenn die Zeit abgelaufen ist. Endzeit = exakt die Frist."""
        deadline = self._deadline()
        if deadline is not None and now >= deadline:
            self._end(SessionEnd.TIME_UP, deadline)
            return True
        return False

    def _append_chunk(self, chunk: TextChunk) -> None:
        sep = self._source.separator
        if self.engine is None:
            offset = 0
            self.engine = TypingEngine(chunk.text, self.settings.input_mode)
        else:
            offset = len(self.engine.target) + len(sep)
            self.engine.append_text(sep + chunk.text)
            if self._segments:                       # Trennzeichen gehört zur vorigen Phrase
                last = self._segments[-1]
                self._segments[-1] = replace(last, end=last.end + len(sep))
        self._chunk_starts.append((offset, chunk.name))
        if chunk.parts:
            cursor = offset
            for n, idx in enumerate(chunk.parts):
                length = len(self._source.phrases[idx])
                gap = len(sep) if n < len(chunk.parts) - 1 else 0
                self._segments.append(Segment(cursor, cursor + length + gap, idx,
                                              self._chunk_count))
                cursor += length + gap
        self._chunk_count += 1

    def line_breaks(self) -> list[int]:
        """Positionen, an denen die Anzeige eine neue Zeile beginnt: im Phrasen-Modus
        nach jeder Phrase (samt ihrem Trenn-Leerzeichen), sonst keine."""
        return [s.end for s in self._segments]

    def _segment_at(self, pos: int) -> Segment | None:
        if not self._segments:
            return None
        i = bisect_right([s.start for s in self._segments], pos) - 1
        return self._segments[i] if i >= 0 else None

    def _refill_if_needed(self) -> None:
        if not self.settings.endless:
            return
        while self.engine.remaining < config.REFILL_THRESHOLD_CHARS:
            self._append_chunk(self._source.next_chunk())

    def _end(self, reason: SessionEnd, t: float) -> None:
        self.metrics.finish(t)
        self.state = SessionState.ENDED
        self.end_reason = reason
