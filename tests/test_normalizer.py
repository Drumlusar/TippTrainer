import pytest

from core.text_normalizer import TextLoadError, load_text, normalize, read_text_file


def n(text, altgr=False):
    return normalize(text, allow_altgr=altgr).text


# --- Beispiele aus dem Architekturplan ---------------------------------------

def test_plan_beispiel():
    assert n("„Café-Preise steigen – um 5 € …“") == '"Cafe-Preise steigen - um 5 EUR ..."'


def test_plan_beispiel_kurz():
    assert n("„Café – 5 €“") == '"Cafe - 5 EUR"'


# --- Erlaubte Zeichen bleiben unverändert ----------------------------------

def test_umlaute_und_eszett_bleiben():
    text = "Größe Übermaß ärgerlich ÄÖÜ äöü ß"
    assert n(text) == text


def test_shift_zeichen_bleiben():
    text = "!\"§$%&/()=?'*+#-_.:,;<>° 0123456789"
    assert n(text) == text


# --- Typografie und Akzente --------------------------------------------------

@pytest.mark.parametrize("original, erwartet", [
    ("„Hallo“", '"Hallo"'),
    ("»Hallo«", '"Hallo"'),
    ("‚Hallo‘", "'Hallo'"),
    ("geht’s", "geht's"),
    ("A–B—C−D", "A-B-C-D"),
    ("Na…", "Na..."),
    ("• Punkt", "- Punkt"),
    ("Café crème à la Noël", "Cafe creme a la Noel"),
    ("ﬁnden", "finden"),          # Ligatur
    ("STRAẞE", "STRAßE"),
    ("3 × 4", "3 x 4"),
])
def test_typografie(original, erwartet):
    assert n(original) == erwartet


def test_tottasten():
    assert n("2^3") == "23"
    assert n("Akut´ Gravis`") == "Akut' Gravis'"


# --- AltGr ------------------------------------------------------------------

def test_altgr_aus_wird_ersetzt():
    assert n("max@web.de") == "maxatweb.de"
    assert n("5€ [a] {b} c\\d ~e |f m² µg") == "5EUR (a) (b) c/d -e /f m2 ug"


def test_altgr_an_bleibt():
    text = "max@web.de 5€ [a] {b} c\\d ~e |f m² µg"
    assert n(text, altgr=True) == text


# --- Leerraum und Zeilenumbrüche -------------------------------------------

def test_windows_zeilenenden_und_leerzeilen():
    assert n("Zeile 1\r\n\r\n\r\nZeile 2\rZeile 3") == "Zeile 1\nZeile 2\nZeile 3"


def test_leerzeichen_am_zeilenrand_und_mehrfach():
    assert n("  Hallo   Welt  \n\t Zweite\tZeile ") == "Hallo Welt\nZweite Zeile"


def test_geschuetzte_leerzeichen():
    assert n("5 km und 3 m") == "5 km und 3 m"


def test_anfang_und_ende_gesaeubert():
    assert n("\n\n  Text  \n\n") == "Text"


# --- Unbekannte Zeichen -------------------------------------------------------

def test_unbekannte_zeichen_entfernt_und_gezaehlt():
    result = normalize("Hallo 😀 Welt 😀 ✓")
    assert result.text == "Hallo Welt"
    assert result.removed == {"😀": 2, "✓": 1}


# --- Kodierung ----------------------------------------------------------------

def test_utf8(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes("Größe".encode("utf-8"))
    assert read_text_file(p) == "Größe"


def test_utf8_mit_bom(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"\xef\xbb\xbf" + "Größe".encode("utf-8"))
    assert read_text_file(p) == "Größe"


def test_windows_1252_fallback(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes("Größe – „ja“".encode("cp1252"))
    assert read_text_file(p) == "Größe – „ja“"
    assert load_text(p).text == 'Größe - "ja"'


def test_unlesbare_kodierung(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"\x81\x8d\x8f\x90\x9d")   # in UTF-8 und cp1252 ungültig
    with pytest.raises(TextLoadError):
        read_text_file(p)


def test_fehlende_datei(tmp_path):
    with pytest.raises(TextLoadError):
        read_text_file(tmp_path / "gibtsnicht.txt")
