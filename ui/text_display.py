"""Eigenes Widget, das den Zieltext im Stil von Monkeytype zeichnet.

- 3 sichtbare Zeilen; die aktuelle Zeile steht oben, sobald es eine
  vorherige gibt, in der Mitte. Der Text rückt zeilenweise nach.
- grau = noch nicht getippt, hell = richtig, rot = falsch.
  Falsches Leerzeichen/Enter: roter Block, da ein rotes Leerzeichen unsichtbar wäre.
- "\\n" erscheint als ↵.
- Balken-Cursor vor dem nächsten erwarteten Zeichen.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFontMetricsF, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from core.models import CharState
from ui import theme
from ui.text_layout import line_of, wrap_lines

VISIBLE_LINES = 3
MAX_COLS = 60          # Lesbarkeit: nicht breiter als 60 Zeichen
LINE_FACTOR = 1.6      # Zeilenabstand relativ zur Schrifthöhe


class TextDisplay(QWidget):
    def __init__(self, controller, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        # Eigene Schrift-Variable: das Stylesheet (font-size für alle QWidgets)
        # würde ein per setFont gesetztes Font sonst überschreiben.
        self._font = theme.mono_font(26)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # Tasten gehen an die TypingView
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._cache_key = None
        self._lines: list[tuple[int, int]] = []

    # --- Geometrie -------------------------------------------------------------

    def _metrics(self):
        fm = QFontMetricsF(self._font)
        char_w = fm.horizontalAdvance("M")
        line_h = fm.height() * LINE_FACTOR
        cols = max(10, min(MAX_COLS, int((self.width() - 40) // char_w)))
        return fm, char_w, line_h, cols

    def _layout(self, text: str, cols: int) -> list[tuple[int, int]]:
        key = (id(self.controller.engine), len(text), cols)
        if key != self._cache_key:
            self._lines = wrap_lines(text, cols)
            self._cache_key = key
        return self._lines

    def minimumSizeHint(self):
        fm = QFontMetricsF(self._font)
        from PySide6.QtCore import QSize
        return QSize(int(fm.horizontalAdvance("M") * 30), int(fm.height() * LINE_FACTOR * VISIBLE_LINES))

    # --- Zeichnen -----------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        engine = self.controller.engine
        if engine is None:
            return
        fm, char_w, line_h, cols = self._metrics()
        text, states, pos = engine.target, engine.states, engine.pos
        lines = self._layout(text, cols)
        cur = line_of(lines, pos)
        first = max(0, cur - 1)

        block_w = cols * char_w
        left = (self.width() - block_w) / 2
        top = (self.height() - VISIBLE_LINES * line_h) / 2
        ascent_offset = (line_h - fm.height()) / 2 + fm.ascent()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self._font)
        # Prüfungsmodus: Fehler nicht live zeigen – falsche Zeichen sehen aus wie richtige
        exam = self.controller.settings.exam_mode

        for row in range(VISIBLE_LINES):
            li = first + row
            if li >= len(lines):
                break
            start, end = lines[li]
            y = top + row * line_h
            for i in range(start, end):
                x = left + (i - start) * char_w
                ch = text[i]
                state = states[i]
                glyph = "↵" if ch == "\n" else ch
                if exam and state is CharState.WRONG:
                    state = CharState.CORRECT
                if state is CharState.WRONG and ch in " \n":
                    p.fillRect(QRectF(x + 1, y + (line_h - fm.height()) / 2,
                                      char_w - 2, fm.height()), theme.WRONG_BG)
                if state is CharState.PENDING:
                    p.setPen(theme.PENDING)
                elif state is CharState.WRONG:
                    p.setPen(theme.WRONG)
                else:                                   # CORRECT / CORRECTED
                    p.setPen(theme.CORRECT)
                if glyph != " ":
                    p.drawText(QPointF(x, y + ascent_offset), glyph)

        # Cursor
        if first <= cur < first + VISIBLE_LINES:
            start, _ = lines[cur] if lines else (0, 0)
            x = left + (pos - start) * char_w
            y = top + (cur - first) * line_h + (line_h - fm.height()) / 2
            p.fillRect(QRectF(x - 1, y, 2.5, fm.height()), theme.CURSOR)
        p.end()
