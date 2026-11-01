from datetime import datetime, timedelta
from pathlib import Path

from core.models import (CharState, ErrorInfo, InputMode, SessionEnd,
                         SessionResult, SessionSettings, SourceMode)
from storage.run_store import RunStore

T = datetime(2026, 10, 31, 23, 0, 0)
C, W, K = CharState.CORRECT, CharState.WRONG, CharState.CORRECTED


def result(avg=250.0, end=SessionEnd.COMPLETED, keystrokes=5):
    s = SessionSettings(SourceMode.SPECIFIC_TEXT, None, 50, Path("/x/fuchs.txt"),
                        InputMode.COMPUTER, True, False, 4242)
    return SessionResult(s, end, ["fuchs.txt"], "Haus\nx", [C, W, K, C, C, C],
                         4.2, keystrokes, 1, 2, avg, 300.0, typed_chars=6, progress=1.0,
                         last_error=ErrorInfo(1, "a", "q"),
                         cpm_series=[200.0, 250.5, 301.5], error_times_s=[0.5, 1.25])


def test_speichern_und_laden_identisch(tmp_path):
    store = RunStore(tmp_path)
    r = result()
    run_id = store.save(r, T)
    loaded = store.load(run_id)
    assert loaded.when == T and loaded.pinned is False
    assert loaded.result == r            # alle Felder inkl. Zeichenzustände und Seed


def test_neueste_zuerst(tmp_path):
    store = RunStore(tmp_path)
    for i in range(3):
        store.save(result(avg=100.0 * i), T + timedelta(minutes=i))
    assert [r.result.cpm_avg for r in store.list_runs()] == [200.0, 100.0, 0.0]


def test_aufraeumen_behaelt_markierte(tmp_path):
    store = RunStore(tmp_path, keep_recent=3)
    first = store.save(result(avg=1.0), T)
    store.set_pinned(first, True)
    for i in range(1, 6):
        store.save(result(avg=float(i + 1)), T + timedelta(minutes=i))
    runs = store.list_runs()
    # 3 neueste + die alte markierte
    assert [r.result.cpm_avg for r in runs] == [6.0, 5.0, 4.0, 1.0]
    assert runs[-1].pinned


def test_markierung_aufheben(tmp_path):
    store = RunStore(tmp_path)
    run_id = store.save(result(), T)
    store.set_pinned(run_id, True)
    assert store.load(run_id).pinned
    store.set_pinned(run_id, False)
    assert not store.load(run_id).pinned


def test_abgebrochen_nicht_gespeichert(tmp_path):
    store = RunStore(tmp_path)
    assert store.save(result(end=SessionEnd.ABORTED), T) is None
    assert store.save(result(keystrokes=0), T) is None
    assert store.list_runs() == []


def test_kaputte_datei_wird_uebersprungen(tmp_path):
    store = RunStore(tmp_path)
    store.save(result(), T)
    (tmp_path / "kaputt.json").write_text("{nicht json", encoding="utf-8")
    assert len(store.list_runs()) == 1


def test_fehlender_ordner(tmp_path):
    assert RunStore(tmp_path / "gibtsnicht").list_runs() == []


def test_phrasen_runde_speichern_und_laden(tmp_path):
    from core.models import PhraseStat
    s = SessionSettings(SourceMode.PHRASES, None, 0, None, InputMode.COMPUTER, False, False, 7,
                        phrases=("ab", "ß"), repetitions=None, shuffle=True,
                        restart_phrase_on_error=True, phrase_set_name="Umlaute")
    r = SessionResult(s, SessionEnd.STOPPED, ["Umlaute"], "ab\nß", [C, C, C, C],
                      3.0, 4, 0, 1, 80.0, 90.0, typed_chars=4,
                      phrase_stats=[PhraseStat("ab", 1, 3, 2.0, 1)])
    store = RunStore(tmp_path)
    assert store.load(store.save(r, T)).result == r


def test_alte_runde_ohne_neue_felder_laedt(tmp_path):
    import json
    store = RunStore(tmp_path)
    run_id = store.save(result(), T)
    path = tmp_path / f"{run_id}.json"
    d = json.loads(path.read_text("utf-8"))
    for k in ("phrases", "repetitions", "shuffle", "restart_phrase_on_error", "phrase_set_name"):
        del d["settings"][k]
    del d["phrase_stats"]
    path.write_text(json.dumps(d), encoding="utf-8")
    assert store.load(run_id).result == result()
