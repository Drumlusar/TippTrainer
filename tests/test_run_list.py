"""Beschriftung und Filter der Verlaufsliste. Übersprungen, wenn PySide6 fehlt."""
from datetime import datetime

import pytest

pytest.importorskip("PySide6")

from core.models import (CharState, InputMode, SessionEnd, SessionResult,  # noqa: E402
                         SessionSettings, SourceMode)
from storage.run_store import StoredRun                                     # noqa: E402
from ui.run_list import (FILTER_ALL, FILTER_DEATH, FILTER_NORMAL,           # noqa: E402
                         matches_filter, result_label)


def run(dbm, end):
    s = SessionSettings(SourceMode.RANDOM_TEXT, None, 50, None, InputMode.COMPUTER, dbm, False, 1)
    r = SessionResult(s, end, ["a.txt"], "x", [CharState.CORRECT], 1.0, 1, 0, 0, 60.0, 60.0)
    return StoredRun("id", datetime(2026, 11, 1), False, r)


def test_beschriftung():
    assert result_label(run(True, SessionEnd.DIED))[0] == "gestorben"
    assert result_label(run(True, SessionEnd.COMPLETED))[0] == "überlebt"
    assert result_label(run(True, SessionEnd.TIME_UP))[0] == "überlebt"
    assert result_label(run(False, SessionEnd.COMPLETED)) == ("fertig", None)


def test_filter():
    normal, death = run(False, SessionEnd.COMPLETED), run(True, SessionEnd.DIED)
    assert matches_filter(normal, FILTER_ALL) and matches_filter(death, FILTER_ALL)
    assert matches_filter(normal, FILTER_NORMAL) and not matches_filter(death, FILTER_NORMAL)
    assert matches_filter(death, FILTER_DEATH) and not matches_filter(normal, FILTER_DEATH)
