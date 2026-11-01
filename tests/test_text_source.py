import random
from dataclasses import replace

import pytest

import config
from core.models import InputMode, SessionSettings, SourceMode
from core.text_normalizer import normalize
from core.text_source import (FileSource, RandomFileSource, RawText, TextLibrary,
                              WordSource, build_source, parse_wordlist)

WORDS = ["Haus", "Baum", "Tür", "groß", "laufen"]
TEXTS = [RawText("a.txt", "Text A"), RawText("b.txt", "Text B"), RawText("c.txt", "Text C")]


def settings(mode, time_limit=None, words=10, seed=1, file=None, altgr=False):
    return SessionSettings(mode, time_limit, words, file, InputMode.COMPUTER, False, altgr, seed)


def lib():
    return TextLibrary(texts=list(TEXTS), words=list(WORDS), wordlist_name="test.txt")


# --- Wortliste --------------------------------------------------------------------

def test_wortliste_parsen():
    raw = "# Kommentar\nHaus\n\n  Baum  \nHaus\nzwei Wörter\n"
    assert parse_wordlist(raw) == ["Haus", "Baum"]


def test_mitgelieferte_wortliste_ist_tippbar():
    words = parse_wordlist((config.WORDLIST_DIR / "deutsch.txt").read_text("utf-8"))
    assert len(words) >= 1000
    untippbar = [w for w in words if normalize(w).text != w]
    assert untippbar == []


# --- Zufällige Wörter -------------------------------------------------------------

def test_wortanzahl():
    src = WordSource(WORDS, "t", random.Random(1), count=25, allow_altgr=False)
    assert len(src.next_chunk().text.split(" ")) == 25


def test_nie_zweimal_dasselbe_wort_hintereinander():
    src = WordSource(WORDS, "t", random.Random(1), count=500, allow_altgr=False)
    w = src.next_chunk().text.split(" ")
    assert all(a != b for a, b in zip(w, w[1:]))


def test_gleicher_seed_gleiche_woerter():
    a = build_source(settings(SourceMode.RANDOM_WORDS, seed=42), lib())
    b = build_source(settings(SourceMode.RANDOM_WORDS, seed=42), lib())
    assert [a.next_chunk() for _ in range(3)] == [b.next_chunk() for _ in range(3)]


def test_anderer_seed_andere_woerter():
    a = build_source(settings(SourceMode.RANDOM_WORDS, seed=1, words=50), lib())
    b = build_source(settings(SourceMode.RANDOM_WORDS, seed=2, words=50), lib())
    assert a.next_chunk() != b.next_chunk()


def test_zeitlimit_nutzt_nachladebloecke():
    src = build_source(settings(SourceMode.RANDOM_WORDS, time_limit=60, words=100), lib())
    assert len(src.next_chunk().text.split(" ")) == config.WORD_CHUNK


# --- Zufälliger Text ---------------------------------------------------------------

def test_nie_derselbe_text_hintereinander():
    src = RandomFileSource(TEXTS, random.Random(3), allow_altgr=False)
    names = [src.next_chunk().name for _ in range(200)]
    assert all(a != b for a, b in zip(names, names[1:]))
    assert set(names) == {"a.txt", "b.txt", "c.txt"}


def test_nur_ein_text_wiederholt_sich():
    src = RandomFileSource(TEXTS[:1], random.Random(3), allow_altgr=False)
    assert [src.next_chunk().name for _ in range(3)] == ["a.txt"] * 3


def test_text_wird_normalisiert_je_nach_altgr():
    raw = [RawText("x.txt", "„5 €“")]
    assert RandomFileSource(raw, random.Random(), False).next_chunk().text == '"5 EUR"'
    assert RandomFileSource(raw, random.Random(), True).next_chunk().text == '"5 €"'


# --- Spezifischer Text --------------------------------------------------------------

def test_spezifischer_text(tmp_path):
    p = tmp_path / "mein.txt"
    p.write_text("Hallo – Welt", encoding="utf-8")
    src = build_source(settings(SourceMode.SPECIFIC_TEXT, file=p), lib())
    assert src.next_chunk().text == "Hallo - Welt"
    assert src.next_chunk().name == "mein.txt"


# --- Bibliothek von der Platte -------------------------------------------------------

def test_bibliothek_laden(tmp_path):
    texte = tmp_path / "texte"
    texte.mkdir()
    (texte / "gut.txt").write_text("Ein Text", encoding="utf-8")
    (texte / "leer.txt").write_text("  😀 \n", encoding="utf-8")
    (texte / "kaputt.txt").write_bytes(b"\x81\x8d")
    wl = tmp_path / "w.txt"
    wl.write_text("Haus\nBaum\n", encoding="utf-8")

    library = TextLibrary.load(texte, wl)
    assert [t.name for t in library.texts] == ["gut.txt"]
    assert library.words == ["Haus", "Baum"]
    assert len(library.problems) == 2      # leer.txt und kaputt.txt


def test_bibliothek_ohne_ordner(tmp_path):
    library = TextLibrary.load(tmp_path / "fehlt", tmp_path / "fehlt.txt")
    assert library.texts == [] and library.words == []
    assert len(library.problems) == 2


# --- Mehrere Wortlisten ---------------------------------------------------------------

def test_alle_wortlisten_im_ordner(tmp_path):
    wl = tmp_path / "wortlisten"
    wl.mkdir()
    (wl / "deutsch.txt").write_text("Haus\nBaum\n", encoding="utf-8")
    (wl / "englisch.txt").write_text("house\ntree\n", encoding="utf-8")
    (wl / "leer.txt").write_text("# nur Kommentar\n", encoding="utf-8")
    lib = TextLibrary.load(tmp_path / "texte", wl)
    assert lib.wordlist_names == ["deutsch.txt", "englisch.txt"]
    assert lib.wordlist_name == "deutsch.txt"              # Standard
    assert lib.words_for("englisch.txt") == ["house", "tree"]
    assert any("leer.txt" in p for p in lib.problems)


def test_gewaehlte_wortliste_wird_verwendet():
    lib = TextLibrary(words=["Haus"], wordlist_name="deutsch.txt",
                      wordlists={"deutsch.txt": ["Haus"], "englisch.txt": ["house", "tree"]})
    s = settings(SourceMode.RANDOM_WORDS, words=20)
    src = build_source(replace(s, wordlist="englisch.txt"), lib)
    chunk = src.next_chunk()
    assert set(chunk.text.split()) <= {"house", "tree"}
    assert chunk.name == "englisch.txt"
    assert build_source(s, lib).next_chunk().name == "deutsch.txt"   # ohne Angabe: Standard


def test_fehlende_wortliste():
    lib = TextLibrary(words=["Haus"], wordlist_name="deutsch.txt")
    with pytest.raises(ValueError):
        build_source(replace(settings(SourceMode.RANDOM_WORDS), wordlist="gibtsnicht.txt"), lib)


def test_mitgelieferte_englische_liste_ist_tippbar():
    words = parse_wordlist((config.WORDLIST_DIR / "englisch.txt").read_text("utf-8"))
    assert len(words) >= 300
    assert [w for w in words if normalize(w).text != w] == []
