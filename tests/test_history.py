from datetime import datetime

from core.models import (CharState, InputMode, SessionEnd, SessionResult,
                         SessionSettings, SourceMode)
from storage import history

WHEN = datetime(2026, 10, 31, 22, 41, 5)


def result(end=SessionEnd.TIME_UP, keystrokes=248, errors=4, mistakes=6, avg=248.0):
    s = SessionSettings(SourceMode.RANDOM_TEXT, 60, 50, None, InputMode.COMPUTER, True, False, 1)
    return SessionResult(s, end, ["fuchs.txt", "artikel_01.txt"], "x", [CharState.CORRECT],
                         60.0, keystrokes, errors, mistakes, avg, 291.0, typed_chars=250)


def test_zeile_wie_im_plan():
    row = history.to_row(result(), WHEN)
    assert row == {
        "datum_zeit": "2026-10-31 22:41:05",
        "textquelle": "Zufälliger Text",
        "textnamen": "fuchs.txt, artikel_01.txt",
        "zeitlimit_s": "60",
        "eingabemodus": "Computer",
        "death_by_mistake": "ja",
        "altgr": "nein",
        "ergebnis": "zeit_abgelaufen",
        "dauer_s": "60,0",
        "anschlaege": "248",
        "fehler": "4",
        "fehler_korrigiert": "2",
        "fehlerquote_prozent": "1,6",          # 4 / 250 Zeichen
        "apm_durchschnitt": "248,0",
        "apm_spitze": "291,0",
        "apm_netto": "246,0",                  # (250 Zeichen - 4 Fehler) / 1 min
        "punkte": "188,0",                     # (248 - 10 × 6 Fehler gesamt) / 1 min
        "profil": "",
        "konsistenz_prozent": "",
    }


def test_bom_nur_einmal_und_semikolon(tmp_path):
    p = tmp_path / "verlauf" / "sessions.csv"
    assert history.append(result(), p, WHEN)
    assert history.append(result(avg=300.0), p, WHEN)
    raw = p.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.count(b"\xef\xbb\xbf") == 1
    lines = raw.decode("utf-8-sig").splitlines()
    assert len(lines) == 3                         # Kopf + 2 Runden
    assert lines[0].startswith("datum_zeit;textquelle;")


def test_neueste_zuerst(tmp_path):
    p = tmp_path / "s.csv"
    for avg in (100.0, 200.0, 300.0):
        history.append(result(avg=avg), p, WHEN)
    recent = history.load_recent(p, n=2)
    assert [history.parse_num(r["apm_durchschnitt"]) for r in recent] == [300.0, 200.0]


def test_abgebrochen_und_leer_nicht_gespeichert(tmp_path):
    p = tmp_path / "s.csv"
    assert not history.append(result(end=SessionEnd.ABORTED), p, WHEN)
    assert not history.append(result(keystrokes=0), p, WHEN)
    assert not p.exists()


def test_gestorben_wird_gespeichert(tmp_path):
    p = tmp_path / "s.csv"
    assert history.append(result(end=SessionEnd.DIED), p, WHEN)
    assert history.load_recent(p)[0]["ergebnis"] == "gestorben"


def test_fehlende_datei_leere_liste(tmp_path):
    assert history.load_recent(tmp_path / "gibtsnicht.csv") == []


def test_nicht_schreibbar(tmp_path):
    ordner = tmp_path / "s.csv"
    ordner.mkdir()                                 # ein Ordner statt einer Datei -> Fehler
    assert history.append(result(), ordner, WHEN) is False


def test_alte_datei_wird_auf_neue_spalten_umgestellt(tmp_path):
    p = tmp_path / "s.csv"
    alt = history.COLUMNS[:-4]                       # älteres Format ohne die letzten Spalten
    p.write_bytes(("﻿" + ";".join(alt) + "\n" + ";".join(["x"] * len(alt)) + "\n").encode("utf-8"))
    assert history.append(result(), p, WHEN)
    rows = history.load_recent(p, n=10)
    assert len(rows) == 2
    assert list(rows[0].keys()) == history.COLUMNS
    assert rows[1]["apm_netto"] == "" and rows[1]["punkte"] == ""   # alte Zeile: leer, nicht verrutscht
    assert rows[1]["apm_spitze"] == "x"
    assert p.read_bytes().count(b"\xef\xbb\xbf") == 1
