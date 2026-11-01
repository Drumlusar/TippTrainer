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
