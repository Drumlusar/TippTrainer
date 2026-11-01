"""Ergebnisansicht: Kennzahlen, Text mit Fehlermarkierung, Tempo-Graph."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem, QTextBrowser, QVBoxLayout)

from core.models import PhraseStat, SessionEnd, SessionResult, SessionSettings, SourceMode
import config
from core.scoring import score
from ui import theme, units
from ui.cpm_chart import CpmChart
from ui.end_view import LockedEndView
from ui.result_html import COLOR_ON_WRONG, COLOR_WRONG, marked_html

TITLES = {
    SessionEnd.COMPLETED: "Geschafft!",
    SessionEnd.TIME_UP: "Zeit abgelaufen",
    SessionEnd.STOPPED: "Beendet",
}


def fatigue_text(thirds: list[tuple[float, float]]) -> str:
    """Ausdauer: erstes gegen letztes Drittel der Runde (Tempo und Fehlerquote)."""
    if len(thirds) != 3:
        return ""
    (c1, e1), _, (c3, e3) = thirds
    parts = [f"Ausdauer – 1. Drittel {units.fmt(c1, with_unit=True)}, {e1:.1f} % Fehler",
             f"3. Drittel {units.fmt(c3, with_unit=True)}, {e3:.1f} % Fehler"]
    if c1 > 0:
        change = (c3 / c1 - 1) * 100
        verdict = ("gleichmäßig" if abs(change) < 5 else
                   "zum Ende schneller" if change > 0 else "zum Ende langsamer")
        parts.append(f"Tempo {change:+.0f} % ({verdict})")
    return "   ·   ".join(parts)


def fmt_duration(s: float) -> str:
    return f"{s:.1f} s" if s < 60 else f"{int(s) // 60}:{int(s) % 60:02d} min"


def settings_summary(s: SessionSettings) -> str:
    parts = [f"Profil: {s.profile}"] if s.profile else []
    parts.append(s.source_mode.value)
    if s.source_mode is SourceMode.RANDOM_WORDS:
        if s.words_lowercase:
            parts.append("klein, ohne Satzzeichen")
        if s.word_min_len or s.word_max_len:
            lo = s.word_min_len or 1
            parts.append(f"{lo}–{s.word_max_len} Buchst." if s.word_max_len else f"ab {lo} Buchst.")
    if s.source_mode is SourceMode.RANDOM_TEXT and s.text_group:
        parts.append(f"Gruppe {s.text_group}")
    if s.time_limit_s is not None:
        lim = s.time_limit_s
        parts.append(f"Zeitlimit {lim} s" if lim < 60 or lim % 60 else f"Zeitlimit {lim // 60} min")
    if s.source_mode is SourceMode.PHRASES:
        parts.append(f"{s.repetitions}× Durchgänge" if s.repetitions else "Endlos")
        if s.shuffle:
            parts.append("gemischt")
        if s.restart_phrase_on_error:
            parts.append("Bei Fehler Phrase neu")
    parts.append(s.input_mode.value)
    if s.death_by_mistake:
        parts.append("Death by Mistake")
    if s.allow_altgr:
        parts.append("AltGr")
    if s.space_skips_word:
        parts.append("Leertaste springt")
    if s.exam_mode:
        parts.append("Prüfungsmodus")
    return "   ·   ".join(parts)


class Tile(QFrame):
    def __init__(self, caption: str) -> None:
        super().__init__()
        self.setObjectName("Tile")
        self.value = QLabel()
        self.value.setObjectName("TileValue")
        self.sub = QLabel()
        self.sub.setObjectName("TileSub")
        cap = QLabel(caption)
        cap.setObjectName("TileCaption")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(0)
        lay.addWidget(cap)
        lay.addWidget(self.value)
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        self.sub.setText(sub)


class ResultView(LockedEndView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.title = QLabel()
        self.title.setObjectName("ResultTitle")
        self.summary = QLabel()
        self.summary.setObjectName("Hint")
        self.summary.setWordWrap(True)
        self.names = QLabel()
        self.names.setObjectName("Hint")
        self.names.setWordWrap(True)

        self.t_avg = Tile("Ø Tempo brutto")
        self.t_net = Tile("Netto")
        self.t_score = Tile("Punkte")
        self.t_peak = Tile("Spitze")
        self.t_err = Tile("Fehler")
        self.t_cons = Tile("Konsistenz")
        self.t_cons.setToolTip("Wie gleichmäßig das Tempo war: 100 % minus Schwankung des "
                               "Tempos (2-s-Abschnitte) relativ zum Mittel. Höher = gleichmäßiger.")
        self.t_time = Tile("Zeit")
        self.t_keys = Tile("Anschläge")
        tiles = QHBoxLayout()
        for t in (self.t_score, self.t_avg, self.t_net, self.t_peak, self.t_err, self.t_cons,
                  self.t_time, self.t_keys):
            tiles.addWidget(t)

        self.text = QTextBrowser()
        self.text.setObjectName("ResultText")
        self.text.setFont(theme.mono_font(14))
        self.text.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        legend = QLabel(
            f'<span style="color:{COLOR_ON_WRONG}; background-color:{COLOR_WRONG};">&nbsp;a&nbsp;</span>'
            f'&nbsp;Fehler&nbsp;&nbsp;&nbsp;&nbsp;'
            f'<span style="color:{COLOR_WRONG}; text-decoration:underline;">a</span>&nbsp;korrigiert')
        legend.setObjectName("Hint")
        self.phrase_table = QTableWidget(0, 4)
        self.phrase_table.setObjectName("PhraseTable")
        self.phrase_table.setHorizontalHeaderLabels(["Phrase", "Durchgänge", "Ø Tempo", "Fehler gesamt"])
        self.phrase_table.verticalHeader().hide()
        self.phrase_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.phrase_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.phrase_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.phrase_table.setShowGrid(False)
        self.phrase_table.setSortingEnabled(True)
        self.phrase_table.setToolTip("Klick auf eine Spaltenüberschrift sortiert. "
                                     "Fehler = alle in dieser Phrase, auch korrigierte.")
        header = self.phrase_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.phrase_table.setMaximumHeight(190)

        text_col = QVBoxLayout()
        text_col.addWidget(self.text, 1)
        text_col.addWidget(legend)
        text_col.addWidget(self.phrase_table)

        self.chart = CpmChart()
        self.chart.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        middle = QHBoxLayout()
        middle.addLayout(text_col, 1)
        middle.addWidget(self.chart, 1)

        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addSpacing(16)
        header.addWidget(self.summary, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 14)
        layout.addLayout(header)
        layout.addWidget(self.names)
        self.banner = QLabel()
        self.banner.setObjectName("RecordBanner")
        self.banner.hide()
        layout.addWidget(self.banner)
        layout.addSpacing(6)
        layout.addLayout(tiles)
        self.fatigue = QLabel()
        self.fatigue.setObjectName("Hint")
        self.fatigue.setToolTip("Vergleich erstes gegen letztes Drittel der Runde "
                                f"(ab {config.THIRDS_MIN_S:.0f} s Dauer). Fehler hier = alle "
                                "gemachten Fehler je Anschlag, auch korrigierte.")
        layout.addWidget(self.fatigue)
        layout.addSpacing(4)
        layout.addLayout(middle, 1)
        layout.addSpacing(8)
        layout.addLayout(self.make_buttons())
        layout.addLayout(self.make_stats_row())
        layout.addWidget(self.hint)

    def show_result(self, r: SessionResult, penalty: int = config.SCORE_PENALTY,
                    banner: str | None = None) -> None:
        self.t_score.set(f"{score(r.keystrokes, r.mistakes, r.duration_s, penalty):.0f}",
                         f"−{penalty} je Fehler")
        self.banner.setText(banner or "")
        self.banner.setVisible(bool(banner))
        self.title.setText(TITLES.get(r.end_reason, "Ergebnis"))
        self.summary.setText(settings_summary(r.settings))
        self.names.setText("Text: " + ", ".join(r.text_names))
        # Hauptwert in der gewählten Einheit, die andere klein darunter (W/min = A/min / 5)
        u, o = units.unit(), units.other()
        self.t_avg.set(units.fmt(r.cpm_avg), f"{u} · {units.fmt(r.cpm_avg, o, True)}")
        self.t_net.set(units.fmt(r.net_cpm), f"{u} · {units.fmt(r.net_cpm, o, True)}")
        self.t_peak.set(units.fmt(r.cpm_peak), u)
        err_sub = f"{r.error_rate:.1f} %"
        if r.corrected:
            err_sub += f" · {r.corrected} korrigiert"
        self.t_err.set(str(r.errors), err_sub)
        self.t_cons.set(f"{r.consistency:.0f} %" if r.consistency is not None else "–",
                        "" if r.consistency is not None else "Runde zu kurz")
        self.fatigue.setText(fatigue_text(r.thirds))
        self.fatigue.setVisible(bool(self.fatigue.text()))
        self.t_time.set(fmt_duration(r.duration_s))
        self.t_keys.set(str(r.keystrokes))
        family = theme.mono_font(14).family()
        self.text.setHtml(
            f'<div style="font-family:\'{family}\'; font-size:14pt; line-height:150%;">'
            f'{marked_html(r.target_text, r.char_states)}</div>')
        self.chart.plot([units.conv(v) for v in r.cpm_series], units.conv(r.cpm_avg),
                        r.error_times_s, units.unit())
        self._fill_phrase_table(r.phrase_stats)
        self.arm()

    def _fill_phrase_table(self, stats: list[PhraseStat]) -> None:
        t = self.phrase_table
        t.setSortingEnabled(False)
        t.setRowCount(len(stats))
        for row, st in enumerate(stats):
            values = [st.phrase, st.reps, round(units.conv(st.cpm)) if st.reps else None, st.mistakes]
            for col, value in enumerate(values):
                item = QTableWidgetItem()
                if col == 0:
                    item.setText(value.replace("\n", "↵"))
                elif value is None:
                    item.setText("–")
                else:
                    item.setData(Qt.ItemDataRole.DisplayRole, value)   # numerisch sortierbar
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                t.setItem(row, col, item)
        t.setSortingEnabled(True)
        t.setVisible(bool(stats))
