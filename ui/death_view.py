"""Deathscreen: erscheint beim ersten Fehler, wenn Death by Mistake aktiv ist."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout

from core.models import SessionResult
from ui import units
from ui import theme
from ui.end_view import LockedEndView, show_char
from ui.result_html import marked_html, snippet_around


class DeathView(LockedEndView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.title = QLabel("Fehler!")
        self.title.setObjectName("DeathTitle")
        self.detail = QLabel()
        self.detail.setObjectName("EndDetail")
        self.snippet = QLabel()
        self.snippet.setTextFormat(Qt.TextFormat.RichText)
        self.snippet.setFont(theme.mono_font(18))
        self.snippet.setObjectName("Snippet")
        self.stats = QLabel()
        self.stats.setObjectName("EndStats")
        for lbl in (self.title, self.detail, self.snippet, self.stats):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        layout.addSpacing(18)
        layout.addWidget(self.snippet)
        layout.addSpacing(18)
        layout.addWidget(self.stats)
        layout.addSpacing(24)
        layout.addLayout(self.make_buttons())
        layout.addLayout(self.make_stats_row())
        layout.addSpacing(10)
        layout.addWidget(self.hint)
        layout.addStretch(1)

    def show_result(self, r: SessionResult) -> None:
        err = r.last_error
        if err:
            self.detail.setText(f"erwartet: {show_char(err.expected)}   –   getippt: {show_char(err.typed)}")
            text, states = snippet_around(r.target_text, r.char_states, err.position)
            self.snippet.setText(marked_html(text, states))
        lines = [
            units.fmt(r.cpm_avg, with_unit=True),
            f"{r.keystrokes} Anschläge in {r.duration_s:.1f} s",
        ]
        if r.progress is not None:
            lines.append(f"Fortschritt: {r.progress * 100:.0f} %")
        self.stats.setText("\n".join(lines))
        self.arm()
