"""Neue Funktionen für Wettbewerbe: Online-Stil, Textprüfungen, Konsistenz, Ausdauer."""
import random

import pytest

from core.models import (CharState, InputMode, KeyOutcome, SessionEnd, SessionSettings,
                         SourceMode, settings_from_dict, settings_to_dict)
from core.session import SessionController
from core.text_source import RawText, TextLibrary, WordSource, build_source, text_group

T0 = 50.0


def settings(**kw):
    base = dict(source_mode=SourceMode.RANDOM_TEXT, time_limit_s=None, word_count=10,
                specific_file=None, input_mode=InputMode.COMPUTER, death_by_mistake=False,
                allow_altgr=False, seed=1)
    base.update(kw)
    return SessionSettings(**base)


def controller(text="ab cd ef", **kw):
    c = SessionController(TextLibrary(texts=[RawText("t.txt", text)]),
                          clock=lambda: pytest.fail("now fehlt"))
    c.start(settings(**kw))
    return c


def tippe(c, text, t=T0, schritt=0.2):
    for ch in text:
        c.on_char(ch, now=t)
        t += schritt
    return t


# --- Wortfilter (Online-Stil) ---------------------------------------------------------------

def test_nur_kleinbuchstaben_ohne_satzzeichen():
    words = ["Haus", "haus", "Baum!", "z.B.", "E-Mail", "12", "über", "groß"]
    src = WordSource(words, "w", random.Random(1), 200, False, lowercase=True)
    assert sorted(src.words) == ["groß", "haus", "über"]   # Haus/haus nur einmal


def test_wortlaenge():
    words = ["a", "ab", "abc", "abcd", "abcde", "abcdef"]
    src = WordSource(words, "w", random.Random(1), 10, False, min_len=2, max_len=4)
    assert sorted(src.words) == ["ab", "abc", "abcd"]


def test_filter_ohne_treffer():
    with pytest.raises(ValueError):
        WordSource(["Haus"], "w", random.Random(1), 10, False, min_len=8)


# --- Textgruppen und Text mit Zeitlimit ------------------------------------------------------

def test_textgruppen():
    assert text_group("lang_de_gewohnheiten.txt") == "lang_de"
    assert text_group("leicht_honig.txt") == "leicht"
    assert text_group("beispiel.txt") == ""


def test_zufallstext_nur_aus_gruppe():
    lib = TextLibrary(texts=[RawText("lang_de_a.txt", "A"), RawText("lang_en_b.txt", "B"),
                             RawText("leicht_c.txt", "C")])
    src = build_source(settings(text_group="lang_de"), lib)
    assert {src.next_chunk().name for _ in range(20)} == {"lang_de_a.txt"}


def test_spezifischer_text_mit_zeitlimit_wiederholt_sich(tmp_path):
    p = tmp_path / "pruefung.txt"
    p.write_text("Kurzer Text.", encoding="utf-8")
    c = SessionController(TextLibrary())
    c.start(settings(source_mode=SourceMode.SPECIFIC_TEXT, specific_file=p, time_limit_s=60))
    assert c.engine.target.startswith("Kurzer Text.\nKurzer Text.\n")


# --- Leertaste springt zum nächsten Wort --------------------------------------------------

def test_leertaste_mitten_im_wort_springt():
    c = controller("haus baum", space_skips_word=True)
    tippe(c, "ha ")                       # „us“ ausgelassen
    e = c.engine
    assert e.pos == 5                      # hinter dem Leerzeichen, bei „baum“
    assert e.states[:5] == [CharState.CORRECT] * 2 + [CharState.WRONG] * 2 + [CharState.CORRECT]
    assert e.errors == 2 and e.mistakes == 2
    assert e.keystrokes == 3


def test_leertaste_am_wortanfang_wird_ignoriert():
    c = controller("haus baum", space_skips_word=True)
    assert c.on_char(" ", now=T0) is KeyOutcome.IGNORED
    assert c.engine.pos == 0 and c.engine.keystrokes == 0


def test_ohne_option_ist_leertaste_ein_normaler_fehler():
    c = controller("haus baum")
    tippe(c, "ha ")
    assert c.engine.pos == 3 and c.engine.errors == 1


def test_letztes_wort_ueberspringen_beendet_runde():
    c = controller("ab cd", space_skips_word=True)
    tippe(c, "ab c ")
    assert c.end_reason is SessionEnd.COMPLETED


def test_springen_mit_death_by_mistake():
    c = controller("haus baum", space_skips_word=True, death_by_mistake=True)
    tippe(c, "h ")
    assert c.end_reason is SessionEnd.DIED


# --- Konsistenz und Ausdauer ----------------------------------------------------------------

def test_konsistenz_gleichmaessig_vs_ungleichmaessig():
    text = "a" * 200
    gleich = controller(text)
    tippe(gleich, "a" * 100, schritt=0.2)          # 20 s, perfekt gleichmäßig
    gleich.abort(now=T0 + 20)
    ungleich = controller(text)
    t = T0
    for i in range(100):                            # abwechselnd schnell und langsam
        ungleich.on_char("a", now=t)
        t += 0.05 if (i // 10) % 2 == 0 else 0.35
    ungleich.abort(now=t)
    k1, k2 = gleich.result().consistency, ungleich.result().consistency
    assert k1 == pytest.approx(100, abs=1)
    assert k2 < 70


def test_drittel_zeigen_ermuedung():
    c = controller("a" * 300)
    t = T0
    for i in range(150):
        # erstes Drittel schnell, letztes langsam und mit Fehlern
        c.on_char("x" if i > 120 and i % 5 == 0 else "a", now=t)
        t += 0.2 if i < 60 else 0.35
    c.abort(now=t)
    thirds = c.result().thirds
    assert len(thirds) == 3
    assert thirds[0][0] > thirds[2][0]               # Tempo fällt ab
    assert thirds[2][1] > thirds[0][1] == 0          # Fehler nur am Ende


def test_kurze_runde_ohne_drittel_und_konsistenz():
    c = controller("abc")
    tippe(c, "abc")
    r = c.result()
    assert r.thirds == [] and r.consistency is None


# --- Einstellungen speichern/laden -----------------------------------------------------------

def test_einstellungen_hin_und_zurueck(tmp_path):
    s = settings(source_mode=SourceMode.RANDOM_WORDS, time_limit_s=30, words_lowercase=True,
                 word_min_len=2, word_max_len=6, space_skips_word=True, exam_mode=True,
                 profile="Online", wordlist="englisch_200.txt", specific_file=tmp_path / "x.txt")
    assert settings_from_dict(settings_to_dict(s)) == s


def test_alte_einstellungen_ohne_neue_felder():
    d = settings_to_dict(settings())
    for k in ("words_lowercase", "exam_mode", "profile", "text_group"):
        del d[k]
    assert settings_from_dict(d) == settings()


# --- Profile, Profil-Highscores, Speicherung ------------------------------------------------

def test_standardprofile_beim_ersten_start(tmp_path):
    from storage.profiles import ProfileStore
    store = ProfileStore(tmp_path / "profile.json")
    names = store.names()
    assert "Online: Englisch 30 s" in names and "Text: Deutsch 10 min (Prüfung)" in names
    online = store.get("Online: Englisch 30 s")
    assert online.time_limit_s == 30 and online.words_lowercase and online.space_skips_word
    assert (tmp_path / "profile.json").exists()


def test_profil_speichern_erkennen_loeschen(tmp_path):
    from dataclasses import replace
    from storage.profiles import ProfileStore
    store = ProfileStore(tmp_path / "p.json")
    s = settings(time_limit_s=120, exam_mode=True)
    store.save("Mein Test", s)
    assert store.matching(replace(s, seed=999)) == "Mein Test"      # Seed egal
    assert store.matching(replace(s, time_limit_s=60)) == ""
    store.delete("Mein Test")
    assert "Mein Test" not in store.names()


def test_profil_highscores_aus_csv(tmp_path):
    from datetime import datetime, timedelta
    from core.models import SessionResult
    from storage import highscores as hs, history
    p = tmp_path / "s.csv"

    def res(end, ks, profile):
        s = settings(source_mode=SourceMode.RANDOM_WORDS, time_limit_s=30, profile=profile)
        return SessionResult(s, end, ["englisch_200.txt"], "x", [CharState.CORRECT], 30.0,
                             ks, 0, 0, ks * 2, 0.0, typed_chars=ks)
    t = datetime(2026, 11, 1, 16, 0)
    history.append(res(SessionEnd.TIME_UP, 150, "Online 30"), p, t)
    history.append(res(SessionEnd.TIME_UP, 180, "Online 30"), p, t + timedelta(minutes=1))
    history.append(res(SessionEnd.DIED, 300, "Online 30"), p, t + timedelta(minutes=2))
    history.append(res(SessionEnd.TIME_UP, 200, ""), p, t + timedelta(minutes=3))
    att = hs.load_profile_attempts(p)
    assert len(att) == 2
    assert hs.top(att, "Online 30", penalty=10)[0].keystrokes == 180
    assert hs.load_attempts(p) == []          # Wortläufe zählen nicht in der Text-Bestenliste


def test_neue_ergebnisfelder_im_verlauf(tmp_path):
    from datetime import datetime
    from core.models import SessionResult
    from storage.run_store import RunStore
    r = SessionResult(settings(profile="X", exam_mode=True), SessionEnd.COMPLETED, ["t.txt"], "ab",
                      [CharState.CORRECT] * 2, 40.0, 2, 0, 0, 3.0, 3.0, typed_chars=2,
                      consistency=81.5, thirds=[(300.0, 1.0), (280.0, 2.0), (250.0, 4.5)])
    store = RunStore(tmp_path)
    assert store.load(store.save(r, datetime(2026, 11, 1, 16, 0))).result == r


def test_neue_standardprofile_in_alte_datei(tmp_path):
    """Datei der ersten Version: neue Standardprofile kommen einmalig hinzu,
    eigene Profile bleiben, gelöschte Standardprofile kommen nicht zurück."""
    import json
    from storage.profiles import DEFAULT_PROFILES, ProfileStore, profile_dict
    path = tmp_path / "profile.json"
    old = dict(DEFAULT_PROFILES)
    path.write_text(json.dumps({"profile": [
        {"name": "Online: Englisch 30 s", "einstellungen": profile_dict(old["Online: Englisch 30 s"])},
        {"name": "Mein Test", "einstellungen": profile_dict(old["Online: Englisch 15 s"])},
    ]}), encoding="utf-8")
    store = ProfileStore(path)
    names = store.names()
    assert "Mein Test" in names and "Online: Englisch 30 s" in names
    assert "Online: Deutsch 30 s" in names and "Text: Englisch 10 min (Prüfung)" in names
    assert "Online: Englisch 15 s" not in names            # war gelöscht -> bleibt weg
    assert store.get("Online: Deutsch 30 s").wordlist == "deutsch_200.txt"
    store.delete("Online: Deutsch 30 s")
    assert "Online: Deutsch 30 s" not in ProfileStore(path).names()
