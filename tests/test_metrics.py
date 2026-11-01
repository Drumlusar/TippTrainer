import pytest

from core.metrics import Metrics

START = 1000.0   # beliebiger Startwert, wie bei time.perf_counter()


def mit_anschlaegen(zeiten, fehler_bei=()):
    """Metrics mit Anschlägen zu den gegebenen Zeiten (relativ zu START)."""
    m = Metrics(window_s=5.0, min_divisor_s=1.0)
    for t in zeiten:
        m.record_keystroke(START + t, is_error=t in fehler_bei)
    return m


def gleichmaessig(pro_sekunde, dauer_s):
    """Anschläge im festen Takt: 0, 1/n, 2/n, ... bis dauer_s."""
    schritt = 1 / pro_sekunde
    return [i * schritt for i in range(int(dauer_s * pro_sekunde) + 1)]


# --- Beispiel aus dem Architekturplan (Abschnitt 6.5) ------------------------

def test_plan_beispiel_228():
    # 7 Anschläge in den ersten Sekunden, dann 19 Anschläge im Fenster (7, 12]
    zeiten = [0, 1, 2, 3, 4, 5, 6] + [7.25 + i * 0.25 for i in range(19)]
    m = mit_anschlaegen(zeiten)
    assert m.live_cpm(START + 12) == pytest.approx(228)   # 19 × 12


# --- Live-Wert ------------------------------------------------------------------

def test_vor_dem_start_null():
    m = Metrics()
    assert m.live_cpm(START) == 0.0
    assert m.average_cpm(START) == 0.0
    assert not m.started


def test_erste_sekunden_durch_vergangene_zeit():
    m = mit_anschlaegen([0, 0.5, 1.0])
    assert m.live_cpm(START + 1.0) == pytest.approx(180)   # 3 Anschläge / 1 s
    assert m.live_cpm(START + 2.0) == pytest.approx(90)    # 3 Anschläge / 2 s


def test_mindestdivisor_verhindert_fantasiewerte():
    m = mit_anschlaegen([0, 0.2])
    # ohne Untergrenze wären das 2 / 0.2 s = 600 A/min
    assert m.live_cpm(START + 0.2) == pytest.approx(120)


def test_fenster_vergisst_alte_anschlaege():
    m = mit_anschlaegen(gleichmaessig(4, 10))           # 4 Anschläge/s, 10 s lang
    assert m.live_cpm(START + 10) == pytest.approx(240)  # 20 im Fenster × 12
    assert m.live_cpm(START + 20) == 0.0                 # Pause: Fenster leer


# --- Verlauf (Graph) ------------------------------------------------------------

def test_verlauf_wird_nachgeholt():
    m = mit_anschlaegen(gleichmaessig(4, 10))
    m.sample(START + 10.08)          # ein einziger, verspäteter UI-Tick
    assert len(m.series) == 10
    assert m.series[4] == pytest.approx(21 / 5 * 60)       # Sekunde 5: alle 21 / 5 s = 252
    assert m.series[5:] == pytest.approx([240] * 5)        # danach konstant 240


def test_verlauf_nicht_doppelt():
    m = mit_anschlaegen(gleichmaessig(4, 3))
    m.sample(START + 3)
    m.sample(START + 3.5)
    m.sample(START + 3.9)
    assert len(m.series) == 3


def test_kein_verlauf_nach_ende():
    m = mit_anschlaegen(gleichmaessig(4, 3))
    m.finish(START + 3.5)
    m.sample(START + 60)
    assert len(m.series) == 3


# --- Ende, Durchschnitt, Spitze -------------------------------------------------

def test_durchschnitt():
    m = mit_anschlaegen([i * 0.3 for i in range(100)])   # 100 Anschläge
    m.finish(START + 30)
    assert m.average_cpm() == pytest.approx(200)          # 100 / 30 s × 60
    assert m.duration() == pytest.approx(30)


def test_durchschnitt_laufend():
    m = mit_anschlaegen(gleichmaessig(2, 9))              # 19 Anschläge
    assert m.average_cpm(START + 10) == pytest.approx(19 / 10 * 60)


def test_spitze():
    # 2 s schnell (8/s), dann 8 s langsam (2/s)
    zeiten = gleichmaessig(8, 2) + [2 + 0.5 * i for i in range(1, 17)]
    m = mit_anschlaegen(zeiten)
    m.finish(START + 10)
    assert m.peak_cpm() == max(m.series)
    assert m.peak_cpm() > m.series[-1]


def test_anschlaege_nach_ende_ignoriert():
    m = mit_anschlaegen([0, 1, 2])
    m.finish(START + 3)
    m.record_keystroke(START + 4)
    assert m.keystrokes == 3


def test_fehlerzeiten_relativ_zum_start():
    m = mit_anschlaegen([0, 1.5, 3], fehler_bei=(1.5,))
    assert m.error_times == [1.5]


def test_zeit_muss_aufsteigen():
    m = mit_anschlaegen([0, 2])
    with pytest.raises(ValueError):
        m.record_keystroke(START + 1)
