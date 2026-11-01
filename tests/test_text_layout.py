from ui.text_layout import line_of, wrap_lines


def zeilen(text, cols):
    return [text[s:e] for s, e in wrap_lines(text, cols)]


def test_umbruch_an_wortgrenze():
    assert zeilen("eins zwei drei vier", 10) == ["eins zwei ", "drei vier"]


def test_enter_erzwingt_umbruch_und_bleibt_in_zeile():
    assert zeilen("ab\ncd", 10) == ["ab\n", "cd"]


def test_zu_langes_wort_wird_hart_getrennt():
    assert zeilen("Donaudampfschifffahrt", 8) == ["Donaudam", "pfschiff", "fahrt"]


def test_jede_position_genau_einmal():
    text = "Der schnelle braune Fuchs\nspringt über den faulen Hund."
    lines = wrap_lines(text, 12)
    assert "".join(text[s:e] for s, e in lines) == text
    assert all(e - s <= 12 for s, e in lines)


def test_cursorzeile():
    lines = wrap_lines("eins zwei drei vier", 10)   # [0,10) [10,19)
    assert line_of(lines, 0) == 0
    assert line_of(lines, 9) == 0
    assert line_of(lines, 10) == 1
    assert line_of(lines, 19) == 1                    # Textende -> letzte Zeile
