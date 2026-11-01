from core.models import CharState
from ui.result_html import marked_html, snippet_around

C, W, K, P = CharState.CORRECT, CharState.WRONG, CharState.CORRECTED, CharState.PENDING


def test_gleiche_zustaende_ein_span():
    html = marked_html("Haus", [C, C, C, C])
    assert html.count("<span") == 1 and "Haus" in html


def test_fehler_und_korrektur_markiert():
    html = marked_html("Haus", [C, W, K, C])
    assert html.count("<span") == 4
    assert "background-color" in html          # stehender Fehler: roter Block
    assert "underline" in html                 # korrigierter Fehler


def test_falsches_leerzeichen_sichtbar_und_enter():
    html = marked_html("a b\nc", [C, W, C, C, C])
    assert "&nbsp;" in html
    assert "↵<br>" in html


def test_html_wird_escaped():
    assert "&lt;b&gt;" in marked_html("<b>", [C, C, C])


def test_ausschnitt():
    text = "x" * 50 + "F" + "y" * 50
    states = [C] * 50 + [W] + [P] * 50
    part, st = snippet_around(text, states, 50, radius=5)
    assert part == "…xxxxxFyyyyy…"
    assert len(st) == len(part)
    assert st[6] is W
