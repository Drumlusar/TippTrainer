"""Tippansicht: Live-Leiste + TextDisplay, nimmt alle Tasten entgegen."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import config
from core.session import SessionController, SessionState
from ui import units
from ui.text_display import TextDisplay


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def key_to_input(event: QKeyEvent) -> str | None:
    """Übersetzt ein Tastenereignis in das Eingabezeichen, "BACKSPACE" oder None (ignorieren).

    Modifier-Regeln (Qt auf macOS: Cmd = Control, Ctrl = Meta):
      - Strg/Cmd + Taste -> ignorieren (Kürzel)
      - Strg + Alt       -> AltGr unter Windows -> Zeichen zulassen
      - Alt/Option allein -> zulassen (Mac: Option+L = @)
      - Backspace mit Strg/Alt/Cmd (Wort löschen) -> ignorieren
    """
    mods = event.modifiers()
    ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
    alt = bool(mods & Qt.KeyboardModifier.AltModifier)
    meta = bool(mods & Qt.KeyboardModifier.MetaModifier)
    key = event.key()

    if key == Qt.Key.Key_Backspace:
        return None if (ctrl or alt or meta) else "BACKSPACE"
    if event.isAutoRepeat():
        return None                      # gedrückt gehaltene Zeichentaste zählt nicht mehrfach
    if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        return None if (ctrl or alt or meta) else "\n"
    if meta or (ctrl and not alt):
        return None
    text = event.text()
    if len(text) == 1 and text.isprintable():
        return text
    return None


def caps_from_event(text: str, modifiers) -> bool | None:
    """Feststelltaste aus einem getippten Buchstaben erschließen.
    Groß ohne Shift oder klein mit Shift -> an; passend zu Shift -> aus;
    kein eindeutiger Buchstabe (Ziffer, Satzzeichen, ß) -> None (unbekannt).
    Beispiele: "A" ohne Shift -> True, "a" ohne Shift -> False, "a" mit Shift -> True."""
    if len(text) != 1 or not text.isalpha() or len(text.upper()) != 1 or text.lower() == text.upper():
        return None
    shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
    return text.isupper() != shift


class TypingView(QWidget):
    finished = Signal()      # Runde zu Ende (fertig, Zeit abgelaufen, gestorben)
    aborted = Signal()       # Esc

    def __init__(self, controller: SessionController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("TypingView")

        self.cpm_label = QLabel()
        self.err_label = QLabel()
        self.time_label = QLabel()
        for lbl in (self.cpm_label, self.err_label, self.time_label):
            lbl.setObjectName("LiveValue")
        self.err_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        bar = QHBoxLayout()
        bar.addWidget(self.cpm_label, 1)
        bar.addWidget(self.err_label, 1)
        bar.addWidget(self.time_label, 1)

        # Feststelltaste: Qt kann ihren Zustand nicht direkt abfragen. Er wird aus den
        # getippten Buchstaben erschlossen: Großbuchstabe ohne Shift (oder klein mit Shift)
        # -> Feststelltaste an. Bis zum ersten Buchstaben ist er unbekannt (None).
        self.caps_on: bool | None = None
        self.caps_label = QLabel("FESTSTELLTASTE AKTIV")
        self.caps_label.setObjectName("CapsWarning")
        self.caps_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caps_label.setToolTip("Großbuchstaben ohne Shift erkannt – bitte die Feststelltaste "
                                   "(Caps Lock) ausschalten.")
        sp = self.caps_label.sizePolicy()
        sp.setRetainSizeWhenHidden(True)          # Text springt beim Ein-/Ausblenden nicht
        self.caps_label.setSizePolicy(sp)
        self.caps_label.hide()

        self.display = TextDisplay(controller)
        self.hint = hint = QLabel("Esc = zurück zum Menü")
        hint.setObjectName("Hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 24)
        layout.addLayout(bar)
        layout.addWidget(self.caps_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.display, 1)
        layout.addWidget(hint)

        self.timer = QTimer(self)
        self.timer.setInterval(config.UI_TICK_MS)
        self.timer.timeout.connect(self._on_tick)
        self._ticks = 0
        self._done = False
        # Tempo-Cursor flüssig bewegen: eigener, schnellerer Takt nur fürs Neuzeichnen
        self.pace_timer = QTimer(self)
        self.pace_timer.setInterval(30)
        self.pace_timer.timeout.connect(self.display.update)

    # --- Steuerung --------------------------------------------------------------

    def begin(self) -> None:
        """Nach controller.start()/restart() aufrufen."""
        s = self.controller.settings
        endless_phrases = s.source_mode.name == "PHRASES" and s.repetitions is None
        hint = "Esc = beenden und auswerten" if endless_phrases else "Esc = zurück zum Menü"
        if s.exam_mode:
            hint = "Prüfungsmodus: Fehler und Tempo erst in der Auswertung   ·   " + hint
        self.hint.setText(hint)
        self._ticks = 0
        self._done = False
        self._update_bar()
        self.display.update()
        self.timer.start()
        if self.display.pace_cpm and not s.exam_mode:
            self.pace_timer.start()
        self.setFocus()

    def _on_tick(self) -> None:
        self.controller.tick()
        self._ticks += 1
        if self._check_end():
            return
        refresh_every = max(1, config.LIVE_BAR_REFRESH_MS // config.UI_TICK_MS)
        if self._ticks % refresh_every == 0:
            self._update_bar()

    def _check_end(self) -> bool:
        if self.controller.state is SessionState.ENDED:
            self.timer.stop()
            self.pace_timer.stop()
            self.display.update()
            if not self._done:              # nur einmal melden (sonst doppelt gespeichert)
                self._done = True
                self.finished.emit()
            return True
        return False

    # --- Tasten --------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.controller.can_stop:             # Phrasen „unendlich“: beenden mit Auswertung
                self.controller.stop()
                self._check_end()
                return
            self.timer.stop()
            self.pace_timer.stop()
            self.controller.abort()
            self.aborted.emit()
            return
        self._update_caps(event)
        if self.controller.state is SessionState.ENDED:
            return
        value = key_to_input(event)
        if value is None:
            event.ignore()
            return
        if value == "BACKSPACE":
            self.controller.on_backspace()
        else:
            was_waiting = self.controller.state is SessionState.WAITING
            self.controller.on_char(value)
            if was_waiting:
                self._update_bar()
        self.display.update()
        self.err_label.setText(self._errors_text())
        self._check_end()

    def _update_caps(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_CapsLock:
            if self.caps_on is not None:          # Umschalten nur, wenn der Zustand bekannt ist
                self.caps_on = not self.caps_on
        else:
            caps = caps_from_event(event.text(), event.modifiers())
            if caps is not None:
                self.caps_on = caps
        self.caps_label.setVisible(bool(self.caps_on))

    # --- Live-Leiste ----------------------------------------------------------------

    def _update_bar(self) -> None:
        c = self.controller
        exam = c.settings.exam_mode
        if c.state is SessionState.WAITING:
            self.cpm_label.setText("Beginnen Sie zu tippen …")
        elif exam:
            self.cpm_label.setText("Prüfung läuft")
        else:
            self.cpm_label.setText(units.fmt(c.live_cpm(), with_unit=True))
        self.err_label.setText(self._errors_text())
        limit = c.settings.time_limit_s
        if limit is None:
            text = f"Zeit: {fmt_time(c.elapsed())}"
        else:
            text = f"Zeit: {fmt_time(c.elapsed())} / {fmt_time(limit)}"
        rnd = c.phrase_round
        if rnd is not None:
            current, total = rnd
            text = f"Durchgang {current}/{total if total else '∞'}   ·   {text}"
        self.time_label.setText(text)

    def _errors_text(self) -> str:
        if self.controller.settings.exam_mode:
            return ""                                   # Prüfung: Fehler erst am Ende
        e = self.controller.engine
        # Bei „Phrase neu beginnen“ verschwinden Fehler sofort wieder – dort alle zählen
        if self.controller.settings.restart_phrase_on_error:
            return f"Fehler: {e.mistakes}"
        return f"Fehler: {e.errors}"
