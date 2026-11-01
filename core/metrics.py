"""Messung: Live-A/min, Verlauf pro Sekunde, Durchschnitt und Spitze.

Alle Zeitstempel kommen von außen (z. B. time.perf_counter()), damit die
Klasse mit künstlichen Zeiten testbar ist.

Warum eine Liste + bisect statt einer deque mit Abschneiden alter Werte?
Der Verlaufswert für Sekunde 7 wird evtl. erst bei t = 7.08 berechnet
(UI-Tick). Hätte man alte Zeitstempel schon verworfen, könnte man einen
zurückliegenden Zeitpunkt nicht mehr exakt auswerten. Bei 10 Minuten und
10 Anschlägen/s sind das nur 6000 Floats.
"""
from __future__ import annotations

from bisect import bisect_right

import config


class Metrics:
    def __init__(self, window_s: float = config.CPM_WINDOW_S,
                 min_divisor_s: float = config.MIN_DIVISOR_S) -> None:
        self.window_s = window_s
        self.min_divisor_s = min_divisor_s
        self.start_time: float | None = None
        self.end_time: float | None = None
        self._times: list[float] = []
        self.error_times: list[float] = []   # Sekunden seit Start
        self.series: list[float] = []        # A/min pro voller Sekunde

    # --- Erfassen ----------------------------------------------------------

    def record_keystroke(self, t: float, is_error: bool = False) -> None:
        """Anschlag zum Zeitpunkt t erfassen. Der erste Anschlag startet die Zeit."""
        if self.end_time is not None:
            return
        if self.start_time is None:
            self.start_time = t
        if self._times and t < self._times[-1]:
            raise ValueError("Zeitstempel müssen aufsteigend sein.")
        self._times.append(t)
        if is_error:
            self.error_times.append(t - self.start_time)

    def sample(self, now: float) -> None:
        """Für jede seit dem Start vollendete Sekunde einen Verlaufswert anlegen."""
        if self.start_time is None:
            return
        limit = now if self.end_time is None else min(now, self.end_time)
        while self.start_time + len(self.series) + 1 <= limit:
            second = len(self.series) + 1
            self.series.append(self.live_cpm(self.start_time + second))

    def finish(self, t: float) -> None:
        """Messung beenden. Spätere Anschläge werden ignoriert."""
        if self.end_time is not None:
            return
        if self.start_time is None:
            self.start_time = t
        self.end_time = t
        self.sample(t)

    # --- Auswerten ---------------------------------------------------------

    @property
    def started(self) -> bool:
        return self.start_time is not None

    @property
    def keystroke_times(self) -> list[float]:
        return list(self._times)

    @property
    def keystrokes(self) -> int:
        return len(self._times)

    def live_cpm(self, at: float) -> float:
        """A/min im gleitenden Fenster (at - window, at].

        In den ersten `window_s` Sekunden wird durch die bisher vergangene Zeit
        geteilt (mindestens `min_divisor_s`), sonst wären die Werte zu niedrig.
        """
        if self.start_time is None or at < self.start_time:
            return 0.0
        elapsed = at - self.start_time
        upto = bisect_right(self._times, at)
        if elapsed <= self.window_s:
            count = upto
            divisor = max(elapsed, self.min_divisor_s)
        else:
            count = upto - bisect_right(self._times, at - self.window_s)
            divisor = self.window_s
        return count / divisor * 60.0

    def duration(self, now: float | None = None) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else now
        if end is None:
            raise ValueError("Laufende Messung: 'now' muss angegeben werden.")
        return end - self.start_time

    def average_cpm(self, now: float | None = None) -> float:
        if self.start_time is None:
            return 0.0
        return self.keystrokes / max(self.duration(now), self.min_divisor_s) * 60.0

    def peak_cpm(self) -> float:
        return max(self.series, default=0.0)
