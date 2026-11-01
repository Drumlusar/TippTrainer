"""Reiter „Statistik“: Problemzeichen, Verwechslungen, Problemwörter, Tastaturansicht.

Datenbasis: Texte und Zufällige Wörter (keine Phrasen, keine per Esc abgebrochenen
Runden), tageweise summiert in `daten/verlauf/statistik.json`.
Häkchen in den Tabellen + „Auswahl als Phrasen-Preset …“ legt ein Übungs-Preset an.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QInputDialog, QLabel,
                               QMessageBox, QPushButton, QToolTip, QVBoxLayout,
                               QWidget)

import config
from core import char_stats as cs
from storage.presets import PresetStore
from storage.stats_store import StatsStore
from ui.highscore_tab import SortItem, make_table
from ui.widgets import fit_combo

PERIODS = [("Letzte 7 Tage", 7), ("Letzte 30 Tage", 30), ("Gesamt", None)]
KEY_MODES = ["Tastatur: Fehlerquote", "Tastatur: Tempo"]

KEY_BASE = QColor("#2d2f35")
KEY_NODATA = QColor("#232428")
ERR_HIGH = QColor("#f2545b")
SLOW_HIGH = QColor("#e2b714")
INK = QColor("#e8e6e1")
INK_DIM = QColor("#6c6f78")

ROWS = [
    (0.0, "^1234567890ß"),
    (0.5, "qwertzuiopü+"),
    (0.75, "asdfghjklöä#"),
    (0.25, "<yxcvbnm,.-"),
]


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


class KeyboardHeatmap(QWidget):
    """QWERTZ-Tastatur; Tasten nach Fehlerquote bzw. Verlangsamung eingefärbt
    (eine Farbe, dunkel = unauffällig, kräftig = auffällig). Tooltip mit Zahlen."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(150)
        self.setMaximumHeight(190)
        self.mode = 0
        self.keys: dict[str, cs.Group] = {}
        self.avg_ms: float | None = None
        self._rects: dict[str, QRectF] = {}

    def set_data(self, keys: dict[str, cs.Group], avg_ms: float | None, mode: int) -> None:
        self.keys, self.avg_ms, self.mode = keys, avg_ms, mode
        self.update()

    def _value(self, g: cs.Group | None) -> tuple[float | None, str]:
        """(Intensität 0–1 oder None = zu wenig Daten, kurzer Text auf der Taste)."""
        if g is None or g.keys < config.STATS_MIN_KEYS:
            return None, ""
        if self.mode == 0:
            return g.error_rate / 15, f"{g.error_rate:.0f}%"          # 15 % = volle Farbe
        if g.avg_ms is None or not self.avg_ms:
            return None, ""
        pct = (g.avg_ms / self.avg_ms - 1) * 100
        return pct / 60, f"{pct:+.0f}%"                               # +60 % = volle Farbe

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        units = 13.0
        size = min((self.width() - 10) / units, (self.height() - 10) / 5.2)
        gap = size * 0.1
        left = (self.width() - units * size) / 2
        top = (self.height() - 5 * size) / 2
        label_font = QFont(self.font())
        label_font.setPixelSize(max(10, int(size * 0.36)))
        small = QFont(self.font())
        small.setPixelSize(max(8, int(size * 0.24)))
        high = ERR_HIGH if self.mode == 0 else SLOW_HIGH
        self._rects = {}

        def draw(key: str, rect: QRectF, label: str) -> None:
            self._rects[key] = rect
            intensity, text = self._value(self.keys.get(key))
            color = KEY_NODATA if intensity is None else _mix(KEY_BASE, high, intensity)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(rect, 4, 4)
            dark_text = intensity is not None and intensity > 0.6
            p.setPen(QColor("#26272c") if dark_text else (INK if intensity is not None else INK_DIM))
            p.setFont(label_font)
            p.drawText(rect.adjusted(5, 2, -3, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, label)
            if text:
                p.setFont(small)
                p.drawText(rect.adjusted(3, 2, -4, -3), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, text)

        for row, (offset, chars) in enumerate(ROWS):
            for i, ch in enumerate(chars):
                x = left + (offset + i) * size
                y = top + row * size
                draw(ch, QRectF(x + gap / 2, y + gap / 2, size - gap, size - gap), ch.upper() if ch.isalpha() and len(ch.upper()) == 1 else ch)
        # Enter rechts neben der zweiten Reihe, Leertaste unten
        x = left + (0.75 + 12) * size
        draw("\n", QRectF(x + gap / 2, top + 1 * size + gap / 2, size * 1.25 - gap, size * 2 - gap), "Enter")
        draw(" ", QRectF(left + 3.5 * size + gap / 2, top + 4 * size + gap / 2, size * 6 - gap, size - gap), "Leertaste")
        p.end()

    def mouseMoveEvent(self, event) -> None:
        pos = QPointF(event.position())
        for key, rect in self._rects.items():
            if rect.contains(pos):
                g = self.keys.get(key)
                name = cs.char_label(key)
                if g is None or g.keys == 0:
                    tip = f"{name}: noch keine Daten"
                else:
                    tempo = f"{g.avg_ms:.0f} ms" if g.avg_ms else "–"
                    tip = (f"{name}  (Groß/Klein und Shift-Zeichen zusammen)\n"
                           f"{g.keys} Anschläge · {g.mistakes} Fehler ({g.error_rate:.1f} %) · {tempo}")
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()


class StatsTab(QWidget):
    preset_saved = Signal(str)

    def __init__(self, store: StatsStore, presets: PresetStore, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.presets = presets

        self.period_combo = QComboBox()
        for label, days in PERIODS:
            self.period_combo.addItem(label, days)
        self.key_combo = QComboBox()
        self.key_combo.addItems(KEY_MODES)
        for combo in (self.period_combo, self.key_combo):
            fit_combo(combo)
            combo.currentIndexChanged.connect(self.refresh)
        self.summary = QLabel()
        self.summary.setObjectName("Hint")
        self.summary.setWordWrap(True)
        top = QHBoxLayout()
        top.addWidget(self.period_combo)
        top.addWidget(self.key_combo)
        top.addSpacing(12)
        top.addWidget(self.summary, 1)

        self.keyboard = KeyboardHeatmap()

        self.chars = make_table(["", "Zeichen", "Anz.", "Fehler", "Tempo", "vs. Ø"], 4)
        self.chars.setToolTip(f"Zeichen erscheinen ab {config.STATS_MIN_KEYS} Anschlägen. "
                              "Tempo = Zeit seit dem vorigen Anschlag (Pausen über "
                              f"{config.STATS_PAUSE_S:.0f} s zählen nicht).")
        self.confusions = make_table(["Soll", "Ist", "Anz."], 1)
        self.words = make_table(["", "Wort", "Anz.", "Fehler", "Quote"], 1)
        self.words.setToolTip("Anz. = Vorkommen, Fehler = davon mit mindestens einem Fehler "
                              "(auch korrigiert)")
        self.confusions.setToolTip("Soll = erwartetes Zeichen, Ist = stattdessen getippt")
        for t in (self.chars, self.confusions, self.words):
            t.setSelectionMode(t.SelectionMode.NoSelection)
            t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            t.setWordWrap(False)
            t.horizontalHeader().setMinimumSectionSize(30)

        def column(title: str, table) -> QVBoxLayout:
            lay = QVBoxLayout()
            lbl = QLabel(title)
            lbl.setObjectName("SectionLabel")
            lay.addWidget(lbl)
            lay.addWidget(table, 1)
            return lay

        tables = QHBoxLayout()
        tables.addLayout(column("Problemzeichen", self.chars), 9)
        tables.addLayout(column("Verwechslungen", self.confusions), 5)
        tables.addLayout(column("Problemwörter", self.words), 9)

        self.preset_btn = QPushButton("Auswahl als Phrasen-Preset …")
        self.preset_btn.clicked.connect(self._save_preset)
        self.clear_btn = QPushButton("Auswahl aufheben")
        self.clear_btn.clicked.connect(self._clear_checks)
        hint = QLabel("Häkchen bei Zeichen und Wörtern setzen, dann als Preset speichern "
                      "(Reiter Phrasen). Gezählt werden Texte und Zufällige Wörter, keine Phrasen.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        bottom = QHBoxLayout()
        bottom.addWidget(hint, 1)
        bottom.addWidget(self.clear_btn)
        bottom.addWidget(self.preset_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.keyboard)
        layout.addLayout(tables, 1)
        layout.addLayout(bottom)

        self.chars.sortItems(3, Qt.SortOrder.DescendingOrder)
        self.words.sortItems(3, Qt.SortOrder.DescendingOrder)
        self.confusions.sortItems(2, Qt.SortOrder.DescendingOrder)

    # --- Daten ------------------------------------------------------------------------

    def refresh(self) -> None:
        st = self.store.load(self.period_combo.currentData())
        avg = cs.overall_avg_ms(st)
        self.keyboard.set_data(cs.key_rows(st), avg, self.key_combo.currentIndex())

        total = sum(v[0] for v in st.chars.values())
        if total == 0:
            self.summary.setText("Noch keine Daten in diesem Zeitraum – einfach ein paar Texte "
                                 "oder Zufällige Wörter tippen.")
        else:
            mistakes = sum(v[1] for v in st.chars.values())
            upper, lower = cs.case_summary(st)

            def grp(g: cs.Group) -> str:
                ms = f", {g.avg_ms:.0f} ms" if g.avg_ms else ""
                return f"{g.error_rate:.1f} % Fehler{ms}" if g.keys else "–"
            self.summary.setText(
                f"{total} Anschläge · {mistakes / total * 100:.1f} % Fehler · "
                f"Ø {avg:.0f} ms pro Zeichen\n" if avg else f"{total} Anschläge\n")
            self.summary.setText(self.summary.text() +
                                 f"Großbuchstaben: {grp(upper)}   ·   Kleinbuchstaben: {grp(lower)}")

        self._fill_chars(st, avg)
        self._fill_confusions(st)
        self._fill_words(st)

    def _check_item(self, value: str) -> SortItem:
        item = SortItem("", None)
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, value)
        return item

    def _fill_chars(self, st: cs.Stats, avg: float | None) -> None:
        t = self.chars
        rows = cs.char_rows(st)
        t.setSortingEnabled(False)
        t.setRowCount(len(rows))
        for r, row in enumerate(rows):
            slower = cs.slower_pct(row, avg)
            cells = [
                self._check_item(row.char),
                SortItem(cs.char_label(row.char, short=True), row.char),
                SortItem(str(row.keys), row.keys, True),
                SortItem(f"{row.error_rate:.1f} %", row.error_rate, True),
                SortItem(f"{row.avg_ms:.0f} ms" if row.avg_ms else "–", row.avg_ms, True),
                SortItem(f"{slower:+.0f} %" if slower is not None else "–", slower, True),
            ]
            if slower is not None and slower >= 25:
                cells[5].setForeground(SLOW_HIGH)
            if row.error_rate >= 5:
                cells[3].setForeground(ERR_HIGH)
            for c, item in enumerate(cells):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)

    def _fill_confusions(self, st: cs.Stats) -> None:
        t = self.confusions
        rows = cs.confusion_rows(st)[:50]
        t.setSortingEnabled(False)
        t.setRowCount(len(rows))
        for r, (exp, typed, n) in enumerate(rows):
            for c, item in enumerate([SortItem(cs.char_label(exp, short=True), exp),
                                      SortItem(cs.char_label(typed, short=True), typed),
                                      SortItem(str(n), n, True)]):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)

    def _fill_words(self, st: cs.Stats) -> None:
        t = self.words
        rows = cs.word_rows(st)
        t.setSortingEnabled(False)
        t.setRowCount(len(rows))
        for r, (word, occ, bad) in enumerate(rows):
            rate = bad / occ * 100
            cells = [self._check_item(word), SortItem(word, word.lower()),
                     SortItem(str(occ), occ, True), SortItem(str(bad), bad, True),
                     SortItem(f"{rate:.0f} %", rate, True)]
            for c, item in enumerate(cells):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)

    # --- Auswahl -> Preset ------------------------------------------------------------------

    def _checked(self) -> list[str]:
        out = []
        for t in (self.chars, self.words):
            for r in range(t.rowCount()):
                item = t.item(r, 0)
                if item and item.checkState() == Qt.CheckState.Checked:
                    value = item.data(Qt.ItemDataRole.UserRole)
                    if value not in (" ", "\n") and value not in out:
                        out.append(value)
        return out

    def _clear_checks(self) -> None:
        for t in (self.chars, self.words):
            for r in range(t.rowCount()):
                if t.item(r, 0):
                    t.item(r, 0).setCheckState(Qt.CheckState.Unchecked)

    def _save_preset(self) -> None:
        items = self._checked()
        if not items:
            QMessageBox.information(self, "Nichts ausgewählt",
                                    "Bitte zuerst Häkchen bei Zeichen oder Wörtern setzen.")
            return
        name, ok = QInputDialog.getText(self, "Phrasen-Preset speichern", "Name des Presets:",
                                        text="Problemstellen")
        name = name.strip()
        if not ok or not name:
            return
        if name in self.presets.names():
            answer = QMessageBox.question(self, "Preset überschreiben?",
                                          f"„{name}“ gibt es schon. Überschreiben?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        if self.presets.save(name, "\n".join(items)):
            self.preset_saved.emit(name)
            QMessageBox.information(self, "Gespeichert",
                                    f"Preset „{name}“ mit {len(items)} Einträgen gespeichert.\n"
                                    "Sie finden es im Reiter Phrasen.")
