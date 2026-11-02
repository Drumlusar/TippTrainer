"""Bildschirmtastatur unter dem Tipptext.

Modi (Einstellung „Bildschirmtastatur“):
  "aus"      – nicht sichtbar
  "naechste" – die Taste(n) für das nächste Zeichen leuchten (inkl. Shift / AltGr bzw. ⌥)
  "live"     – jede gedrückte Taste blinkt kurz auf: Grün = richtig, Rot = falsch
  "beides"   – beides zusammen
Im Prüfungsmodus blinken falsche Tasten nicht rot (Fehler erst in der Auswertung).
"""
from __future__ import annotations

import time

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui import theme
from core.keyboard_layout import HEIGHT_UNITS, WIDTH_UNITS, get_layout

MODES = {"aus": "Aus", "naechste": "Nächste Taste zeigen",
         "live": "Gedrückte Tasten (live)", "beides": "Beides"}
FLASH_S = 0.35          # so lange blinkt eine gedrückte Taste nach


def mode_shows_next(mode: str) -> bool:
    return mode in ("naechste", "beides")


def mode_shows_live(mode: str) -> bool:
    return mode in ("live", "beides")


class KeyboardView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.mode = "aus"
        self.layout = get_layout("qwertz")
        self.next_keys: set[str] = set()
        self._flashes: dict[str, tuple[float, bool]] = {}   # Taste -> (Zeitpunkt, richtig?)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(150)
        self.setMaximumHeight(240)
        self._fade = QTimer(self)
        self._fade.setInterval(30)
        self._fade.timeout.connect(self._on_fade)

    def sizeHint(self) -> QSize:
        return QSize(720, 210)

    # --- von außen ----------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        self.mode = mode if mode in MODES else "aus"
        self.setVisible(self.mode != "aus")
        self.update()

    def set_layout(self, layout_id: str) -> None:
        self.layout = get_layout(layout_id)
        self.update()

    def show_next(self, ch: str | None) -> None:
        """Nächstes erwartetes Zeichen (None = keins, z. B. Runde zu Ende)."""
        self.next_keys = self.layout.keys_for_char(ch) if ch is not None and mode_shows_next(self.mode) else set()
        self.update()

    def flash(self, ch: str, correct: bool) -> None:
        """Gedrückte Taste kurz aufleuchten lassen ("BACKSPACE" für die Rücktaste)."""
        if not mode_shows_live(self.mode):
            return
        keys = {"backspace"} if ch == "BACKSPACE" else self.layout.keys_for_char(ch)
        now = time.monotonic()
        for k in keys:
            self._flashes[k] = (now, correct)
        if keys and not self._fade.isActive():
            self._fade.start()
        self.update()

    def clear(self) -> None:
        self._flashes.clear()
        self._fade.stop()
        self.next_keys = set()
        self.update()

    def _on_fade(self) -> None:
        now = time.monotonic()
        self._flashes = {k: v for k, v in self._flashes.items() if now - v[0] < FLASH_S}
        if not self._flashes:
            self._fade.stop()
        self.update()

    # --- Zeichnen -----------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        unit = min((self.width() - 4) / WIDTH_UNITS, (self.height() - 4) / HEIGHT_UNITS)
        left = (self.width() - WIDTH_UNITS * unit) / 2
        top = (self.height() - HEIGHT_UNITS * unit) / 2
        gap = max(2.0, unit * 0.08)
        big, small = QFont(self.font()), QFont(self.font())
        big.setPixelSize(max(9, int(unit * 0.36)))
        small.setPixelSize(max(7, int(unit * 0.24)))
        now = time.monotonic()

        for k in self.layout.keys:
            rect = QRectF(left + k.x * unit + gap / 2, top + k.y * unit + gap / 2,
                          k.w * unit - gap, k.h * unit - gap)
            fill, ink = theme.color("surface"), theme.color("muted")
            if k.id in self.next_keys:
                fill, ink = theme.color("accent"), theme.color("accent_ink")
            flash = self._flashes.get(k.id)
            if flash is not None:
                t = (now - flash[0]) / FLASH_S
                if t < 1:
                    c = theme.color("ok" if flash[1] else "error")
                    c.setAlphaF(0.85 * (1 - t))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(fill)
                    p.drawRoundedRect(rect, 4, 4)
                    fill = c
                    if t < 0.5:
                        ink = theme.color("accent_ink")
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(rect, 4, 4)

            p.setPen(ink)
            if k.shift_label:
                p.setFont(small)
                p.drawText(rect.adjusted(5, 2, -3, -2),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, k.shift_label)
                p.setFont(big)
                p.drawText(rect.adjusted(5, 2, -3, -3),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, k.label)
            else:
                p.setFont(big if len(k.label) <= 2 else small)
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, k.label)
            if k.id in self.layout.home_marks:          # Tastmarken der Grundstellung
                y = rect.bottom() - unit * 0.16
                p.drawLine(int(rect.center().x() - unit * 0.12), int(y),
                           int(rect.center().x() + unit * 0.12), int(y))
        p.end()
