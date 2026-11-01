from storage.presets import PresetStore


def test_presets_anlegen_ueberschreiben_loeschen(tmp_path):
    store = PresetStore(tmp_path / "p.json")
    assert store.names() == []
    store.save("Umlaute", "ä ö ü\nß")
    store.save("Zahlen", "1234")
    store.save("Umlaute", "Größe")                  # überschreiben, Reihenfolge bleibt
    assert store.names() == ["Umlaute", "Zahlen"]
    assert store.get("Umlaute") == "Größe"
    store.delete("Umlaute")
    assert store.names() == ["Zahlen"]
    assert store.get("Umlaute") is None


def test_zuletzt_verwendet(tmp_path):
    store = PresetStore(tmp_path / "p.json")
    assert store.last_text() == ""
    store.set_last_text("Haus\nBaum")
    store.save("x", "y")
    assert PresetStore(tmp_path / "p.json").last_text() == "Haus\nBaum"


def test_kaputte_datei(tmp_path):
    p = tmp_path / "p.json"
    p.write_text("{kaputt", encoding="utf-8")
    store = PresetStore(p)
    assert store.names() == []
    assert store.save("a", "b")
    assert store.names() == ["a"]


def test_vorlagen(tmp_path):
    vorlagen = tmp_path / "vorlagen"
    vorlagen.mkdir()
    (vorlagen / "Bigramme.txt").write_text("# Kommentar\nen en en\n\nch ch ch\n", encoding="utf-8")
    store = PresetStore(tmp_path / "p.json", vorlagen)
    store.save("Eigenes", "abc")
    assert store.names() == ["Eigenes", "Bigramme"]           # eigene zuerst
    assert store.get("Bigramme") == "en en en\n\nch ch ch"    # ohne Kommentarzeilen
    assert store.is_template("Bigramme") and not store.is_template("Eigenes")
    store.save("Bigramme", "eigene Fassung")                   # eigenes Preset verdeckt Vorlage
    assert store.get("Bigramme") == "eigene Fassung" and not store.is_template("Bigramme")
    assert store.names().count("Bigramme") == 1
    store.delete("Bigramme")                                   # Vorlage ist wieder da
    assert store.is_template("Bigramme") and store.get("Bigramme").startswith("en")


def test_mitgelieferte_vorlagen():
    import config
    store = PresetStore(tmp := config.PRESETS_FILE.with_name("gibt_es_nicht.json"),
                        config.PRESET_TEMPLATE_DIR)
    names = store.template_names()
    for n in ("Bigramme Deutsch", "Bigramme Englisch",
              "Schwierige Wörter Deutsch", "Schwierige Wörter Englisch"):
        assert n in names
        assert not any(l.startswith("#") for l in store.get(n).splitlines())
    assert not tmp.exists()
