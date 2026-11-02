"""Reiter „Highscores“: Bestenliste pro Text oder pro Test-Profil.

Oben: alle Texte bzw. Profile (auch noch nicht geübte) mit Bestwert, Versuchen,
zuletzt geübt. Unten: Top 10 des gewählten Eintrags. Beide Tabellen per Klick auf die
Spaltenüberschrift sortierbar; Klick auf einen Eintrag unten öffnet dessen Auswertung.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout,
                               QHeaderView, QLabel, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

import config
from storage import highscores as hs
from ui import theme, units
from ui.widgets import ALL_KEYBOARDS, fill_keyboard_combo, fit_combo, plain_spin

INPUT_FILTERS = [("Eingabe: alle", None), ("Computer", "Computer"),
                 ("Schreibmaschine", "Schreibmaschine")]
DBM_FILTERS = [("Death by Mistake: egal", None), ("nur mit Death by Mistake", True),
               ("nur ohne Death by Mistake", False)]
VIEW_TEXTS, VIEW_PROFILES = "Bestenliste: Texte", "Bestenliste: Test-Profile"
HINT_TEXTS = ("Es zählen nur vollständig getippte Einzeltexte ohne Zeitlimit "
              "(Death by Mistake nur überlebt). Klick auf eine Spalte sortiert.")
HINT_PROFILES = ("Es zählen Runden, die mit genau den Einstellungen eines Profils gestartet "
                 "wurden (fertig oder Zeit abgelaufen). Klick auf eine Spalte sortiert.")


def fmt_date(when: str | None) -> str:
    # "2026-11-01 13:20:05" -> "01.11.26 13:20"
    if not when or len(when) < 16:
        return "–"
    return f"{when[8:10]}.{when[5:7]}.{when[2:4]} {when[11:16]}"


class SortItem(QTableWidgetItem):
    """Tabellenzelle mit eigenem Sortierwert (Zahlen numerisch, „–“ immer hinten)."""

    def __init__(self, text: str, key=None, align_right: bool = False) -> None:
        super().__init__(text)
        self.key = key
        if align_right:
            self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other) -> bool:
        a, b = self.key, getattr(other, "key", None)
        if a is None or b is None:
            # fehlende Werte nach hinten – unabhängig von der Sortierrichtung
            order = self.tableWidget().horizontalHeader().sortIndicatorOrder() if self.tableWidget() else 0
            ascending = order == Qt.SortOrder.AscendingOrder
            if a is None and b is None:
                return False
            return (a is not None) if ascending else (a is None)
        return a < b


def make_table(headers: list[str], stretch_col: int) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().hide()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setShowGrid(False)
    t.setSortingEnabled(True)
    t.setObjectName("ScoreTable")
    h = t.horizontalHeader()
    for col in range(len(headers)):
        h.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch if col == stretch_col
                               else QHeaderView.ResizeMode.ResizeToContents)
    return t


class HighscoreTab(QWidget):
    open_attempt = Signal(str, str)          # (Zeitpunkt, Text)
    open_profile_attempt = Signal(str, str)  # (Zeitpunkt, Profil)
    penalty_changed = Signal(int)

    def __init__(self, penalty: int = config.SCORE_PENALTY, parent=None) -> None:
        super().__init__(parent)
        self._attempts: list[hs.Attempt] = []
        self._text_names: list[str] = []
        self._profile_attempts: list[hs.Attempt] = []
        self._profile_names: list[str] = []
        self._selected = {VIEW_TEXTS: None, VIEW_PROFILES: None}
        self.highlight_when: str | None = None      # frischer Rekord -> hervorheben

        # --- Filterzeile -----------------------------------------------------------------
        self.view_combo = QComboBox()
        self.view_combo.addItems([VIEW_TEXTS, VIEW_PROFILES])
        self.view_combo.currentIndexChanged.connect(self._on_view)
        fit_combo(self.view_combo)
        self.input_combo = QComboBox()
        for label, value in INPUT_FILTERS:
            self.input_combo.addItem(label, value)
        self.dbm_combo = QComboBox()
        for label, value in DBM_FILTERS:
            self.dbm_combo.addItem(label, value)
        self.penalty_spin = QSpinBox()
        self.penalty_spin.setRange(0, 100)
        self.penalty_spin.setValue(penalty)
        self.penalty_spin.setSuffix(" Anschläge")
        self.penalty_spin.setToolTip("Punkte = (Anschläge − Strafe × Fehler) / Minuten, nie unter 0.\n"
                                     "Fehler = alle gemachten Fehler, auch korrigierte.")
        self.kb_combo = QComboBox()
        self.kb_combo.addItem(ALL_KEYBOARDS, None)
        for combo in (self.input_combo, self.dbm_combo, self.kb_combo):
            fit_combo(combo)
            combo.currentIndexChanged.connect(self.refresh)
        plain_spin(self.penalty_spin)
        self.penalty_spin.setMinimumWidth(130)
        self.penalty_spin.valueChanged.connect(self._on_penalty)
        pen_label = QLabel("Strafe pro Fehler:")
        pen_label.setObjectName("Hint")
        filters = QHBoxLayout()
        filters.addWidget(self.view_combo)
        filters.addSpacing(10)
        filters.addWidget(self.input_combo)
        filters.addWidget(self.dbm_combo)
        filters.addWidget(self.kb_combo)
        filters.addStretch(1)
        filters.addWidget(pen_label)
        filters.addWidget(self.penalty_spin)

        # --- Tabellen ---------------------------------------------------------------------
        self.texts = make_table(["Text", "Bestwert", "Tempo", "Fehler", "Versuche", "Zuletzt geübt"], 0)
        self.texts.itemSelectionChanged.connect(self._on_text_selected)
        self.top_label = QLabel()
        self.top_label.setObjectName("SectionLabel")
        self.top = make_table(["#", "Punkte", "Tempo", "Netto", "Fehler", "Zeit",
                               "Eingabe", "Death by Mistake", "Datum"], 8)
        self.top.setCursor(Qt.CursorShape.PointingHandCursor)
        self.top.cellClicked.connect(self._on_top_clicked)
        self.top.setToolTip("Klick auf einen Eintrag öffnet seine Auswertung")
        self.hint = hint = QLabel(HINT_TEXTS)
        hint.setObjectName("Hint")
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.texts, 3)
        layout.addWidget(self.top_label)
        layout.addWidget(self.top, 2)
        layout.addWidget(hint)

        self.texts.sortItems(1, Qt.SortOrder.DescendingOrder)   # bester Text oben
        self.top.sortItems(0, Qt.SortOrder.AscendingOrder)      # Platz 1 oben

    # --- Daten --------------------------------------------------------------------------

    @property
    def penalty(self) -> int:
        return self.penalty_spin.value()

    @property
    def profile_view(self) -> bool:
        return self.view_combo.currentText() == VIEW_PROFILES

    @property
    def _selected_text(self) -> str | None:
        return self._selected[self.view_combo.currentText()]

    @_selected_text.setter
    def _selected_text(self, value: str | None) -> None:
        self._selected[self.view_combo.currentText()] = value

    def set_data(self, attempts: list[hs.Attempt], text_names: list[str],
                 profile_attempts: list[hs.Attempt] | None = None,
                 profile_names: list[str] = ()) -> None:
        self._attempts = attempts
        self._text_names = text_names
        if profile_attempts is not None:
            self._profile_attempts = profile_attempts
        self._profile_names = list(profile_names)
        self.refresh()

    def _on_view(self) -> None:
        profiles = self.profile_view
        self.hint.setText(HINT_PROFILES if profiles else HINT_TEXTS)
        self.texts.horizontalHeaderItem(0).setText("Profil" if profiles else "Text")
        self.refresh()

    def _filtered(self) -> list[hs.Attempt]:
        source = self._profile_attempts if self.profile_view else self._attempts
        return hs.filter_attempts(source, self.input_combo.currentData(),
                                  self.dbm_combo.currentData(), self.kb_combo.currentData())

    def set_keyboards(self, keyboards) -> None:
        fill_keyboard_combo(self.kb_combo, keyboards)

    def refresh(self) -> None:
        attempts = self._filtered()
        self.texts.horizontalHeaderItem(2).setText(units.unit())
        self.top.horizontalHeaderItem(2).setText(units.unit())
        names = self._profile_names if self.profile_view else self._text_names
        rows = hs.summarize(attempts, self.penalty, names)
        t = self.texts
        t.blockSignals(True)
        t.setSortingEnabled(False)
        t.setRowCount(len(rows))
        for r, row in enumerate(rows):
            best = row.best
            pts = best.points(self.penalty) if best else None
            cells = [
                SortItem(row.text, row.text.lower()),
                SortItem(f"{pts:.0f}" if best else "–", pts, True),
                SortItem(units.fmt(best.cpm) if best else "–", best.cpm if best else None, True),
                SortItem(str(best.mistakes) if best else "–", best.mistakes if best else None, True),
                SortItem(str(row.attempts), row.attempts, True),
                SortItem(fmt_date(row.last), row.last),
            ]
            if best:
                cells[1].setForeground(theme.color("accent"))
            for c, item in enumerate(cells):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)
        # Auswahl wiederherstellen (sonst ersten Text mit Versuchen wählen)
        target = self._selected_text
        names = [t.item(r, 0).text() for r in range(t.rowCount())]
        if target not in names:
            target = next((n for r, n in enumerate(names) if t.item(r, 4).key), names[0] if names else None)
        if target is not None:
            t.selectRow(names.index(target))
        t.blockSignals(False)
        self._selected_text = target
        self._fill_top()

    def _on_text_selected(self) -> None:
        rows = self.texts.selectionModel().selectedRows()
        if rows:
            self._selected_text = self.texts.item(rows[0].row(), 0).text()
            self._fill_top()

    def _fill_top(self) -> None:
        text = self._selected_text
        entries = hs.top(self._filtered(), text, self.penalty, config.HIGHSCORE_TOP_N) if text else []
        self.top_label.setText(f"Top {config.HIGHSCORE_TOP_N}: {text}" if text else "")
        t = self.top
        t.setSortingEnabled(False)
        t.setRowCount(len(entries))
        for r, a in enumerate(entries):
            pts = a.points(self.penalty)
            cells = [
                SortItem(f"{r + 1}.", r + 1, True),
                SortItem(f"{pts:.0f}", pts, True),
                SortItem(units.fmt(a.cpm), a.cpm, True),
                SortItem(units.fmt(a.net_cpm), a.net_cpm, True),
                SortItem(f"{a.mistakes}", a.mistakes, True),
                SortItem(f"{a.duration_s:.1f} s", a.duration_s, True),
                SortItem(a.input_mode, a.input_mode),
                SortItem("ja" if a.dbm else "–", a.dbm),
                SortItem(fmt_date(a.when) + ("   NEU" if a.when == self.highlight_when else ""), a.when),
            ]
            cells[0].setData(Qt.ItemDataRole.UserRole, a.when)
            if r == 0:                                   # Rekord: goldene Schrift
                for item in cells:
                    item.setForeground(theme.color("accent"))
            if a.when == self.highlight_when:            # frisch getippt: hinterlegt
                for item in cells:
                    item.setBackground(theme.color("accent", 45))
            for c, item in enumerate(cells):
                t.setItem(r, c, item)
        t.setSortingEnabled(True)

    def _on_top_clicked(self, row: int, _col: int) -> None:
        when = self.top.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if when and self._selected_text:
            signal = self.open_profile_attempt if self.profile_view else self.open_attempt
            signal.emit(when, self._selected_text)

    def _on_penalty(self, value: int) -> None:
        self.penalty_changed.emit(value)
        self.refresh()

    def select_text(self, text: str, profile: bool = False) -> None:
        """Eintrag auswählen und die passende Ansicht (Texte/Profile) zeigen."""
        self._selected[VIEW_PROFILES if profile else VIEW_TEXTS] = text
        self.view_combo.blockSignals(True)
        self.view_combo.setCurrentText(VIEW_PROFILES if profile else VIEW_TEXTS)
        self.view_combo.blockSignals(False)
        self._on_view()
