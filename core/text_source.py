"""Textquellen: zufällige Wörter, zufälliger Text, spezifischer Text.

Jede Quelle liefert über `next_chunk()` beliebig oft neuen Text. Ohne
Zeitlimit wird nur der erste Chunk verwendet; mit Zeitlimit holt der
SessionController weitere Chunks, solange die Zeit läuft.

Reproduzierbarkeit: Alle Zufallsentscheidungen laufen über ein eigenes
`random.Random(seed)`. Gleicher Seed -> gleiche Wortfolge bzw. gleiche
Reihenfolge der Texte (Voraussetzung für den Neustart mit gleichem Text).
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import config
from core.models import SessionSettings, SourceMode
from core.text_normalizer import TextLoadError, normalize, read_text_file


@dataclass(frozen=True)
class TextChunk:
    text: str
    name: str            # Dateiname des Textes bzw. der Wortliste
    parts: tuple[int, ...] = ()   # nur Phrasen: Index jeder Phrase im Chunk, in Reihenfolge


@dataclass(frozen=True)
class RawText:
    """Eine Textdatei, dekodiert, aber noch nicht normalisiert
    (die Normalisierung hängt von der AltGr-Einstellung ab)."""
    name: str
    raw: str


# --- Bibliothek: alle Texte und Wörter einmal von der Platte laden -----------

@dataclass
class TextLibrary:
    texts: list[RawText] = field(default_factory=list)
    words: list[str] = field(default_factory=list)          # Standardliste
    wordlist_name: str = ""
    wordlists: dict[str, list[str]] = field(default_factory=dict)   # alle Listen: Dateiname -> Wörter
    problems: list[str] = field(default_factory=list)   # Hinweise fürs Menü

    @classmethod
    def load(cls, text_dir: Path = config.TEXT_DIR,
             wordlist: Path = config.WORDLIST_DIR) -> "TextLibrary":
        """`wordlist` darf ein Ordner (alle *.txt darin) oder eine einzelne Datei sein."""
        lib = cls()
        if text_dir.is_dir():
            for path in sorted(text_dir.glob("*.txt")):   # sortiert -> reproduzierbar
                try:
                    raw = read_text_file(path)
                except TextLoadError as exc:
                    lib.problems.append(str(exc))
                    continue
                if not normalize(raw).text:
                    lib.problems.append(f"Datei ist nach der Normalisierung leer: {path.name}")
                    continue
                lib.texts.append(RawText(path.name, raw))
        else:
            lib.problems.append(f"Textordner fehlt: {text_dir}")

        if wordlist.is_dir():
            paths = sorted(wordlist.glob("*.txt"))
        elif wordlist.is_file():
            paths = [wordlist]
        else:
            paths = []
            lib.problems.append(f"Wortliste fehlt: {wordlist}")
        for path in paths:
            try:
                words = parse_wordlist(read_text_file(path))
            except TextLoadError as exc:
                lib.problems.append(str(exc))
                continue
            if words:
                lib.wordlists[path.name] = words
            else:
                lib.problems.append(f"Wortliste ist leer: {path.name}")
        if lib.wordlists:
            # Standard: deutsch.txt, sonst die erste Liste
            lib.wordlist_name = (config.DEFAULT_WORDLIST if config.DEFAULT_WORDLIST in lib.wordlists
                                 else next(iter(lib.wordlists)))
            lib.words = lib.wordlists[lib.wordlist_name]
        return lib

    def words_for(self, name: str) -> list[str]:
        """Wörter einer Liste; leerer Name = Standardliste."""
        name = name or self.wordlist_name
        if name in self.wordlists:
            return self.wordlists[name]
        if name == self.wordlist_name:
            return self.words
        return []

    @property
    def wordlist_names(self) -> list[str]:
        return list(self.wordlists) or ([self.wordlist_name] if self.words else [])


def text_group(filename: str) -> str:
    """Gruppe = Dateiname bis zum letzten „_“: „lang_de_gewohnheiten.txt“ -> „lang_de“,
    „leicht_honig.txt“ -> „leicht“, „beispiel.txt“ -> "" (keine Gruppe)."""
    stem = filename.removesuffix(".txt")
    return stem.rsplit("_", 1)[0] if "_" in stem else ""


def parse_wordlist(raw: str) -> list[str]:
    """Ein Wort pro Zeile; leere Zeilen und Zeilen mit # werden ignoriert,
    doppelte Wörter nur einmal übernommen."""
    words: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        word = line.strip()
        if not word or word.startswith("#") or " " in word:
            continue
        if word not in seen:
            seen.add(word)
            words.append(word)
    return words


# --- Quellen -------------------------------------------------------------------

class TextSource(ABC):
    separator: str = " "     # womit nachgeladener Text angehängt wird

    @abstractmethod
    def next_chunk(self) -> TextChunk: ...


class WordSource(TextSource):
    """Zufällige Wörter; dasselbe Wort kommt nie zweimal direkt hintereinander."""
    separator = " "

    def __init__(self, words: list[str], name: str, rng: random.Random,
                 count: int, allow_altgr: bool, lowercase: bool = False,
                 min_len: int = 0, max_len: int = 0) -> None:
        cleaned = [w for w in (normalize(w, allow_altgr).text for w in words) if w]
        if lowercase:
            # Online-Stil: nur Kleinbuchstaben, keine Satzzeichen oder Ziffern
            cleaned = [w.lower() for w in cleaned if w.isalpha()]
        if min_len:
            cleaned = [w for w in cleaned if len(w) >= min_len]
        if max_len:
            cleaned = [w for w in cleaned if len(w) <= max_len]
        cleaned = list(dict.fromkeys(cleaned))          # „Haus“/„haus“ nur einmal
        if not cleaned:
            raise ValueError("Keine Wörter der Liste passen zu den gewählten Filtern.")
        self.words = cleaned
        self.name = name
        self.rng = rng
        self.count = count
        self._last: str | None = None

    def _pick(self) -> str:
        while True:
            word = self.rng.choice(self.words)
            if word != self._last or len(self.words) == 1:
                self._last = word
                return word

    def next_chunk(self) -> TextChunk:
        return TextChunk(" ".join(self._pick() for _ in range(self.count)), self.name)


class RandomFileSource(TextSource):
    """Zufällige Texte; derselbe Text kommt nie zweimal direkt hintereinander
    (außer es gibt nur einen)."""
    separator = "\n"

    def __init__(self, texts: list[RawText], rng: random.Random, allow_altgr: bool) -> None:
        if not texts:
            raise ValueError("Keine Texte vorhanden.")
        self.texts = [TextChunk(normalize(t.raw, allow_altgr).text, t.name) for t in texts]
        self.rng = rng
        self._last: int | None = None

    def next_chunk(self) -> TextChunk:
        choices = [i for i in range(len(self.texts)) if i != self._last] or [0]
        idx = self.rng.choice(choices)
        self._last = idx
        return self.texts[idx]


class FileSource(TextSource):
    """Ein fest gewählter Text."""
    separator = "\n"

    def __init__(self, path: Path, allow_altgr: bool) -> None:
        text = normalize(read_text_file(path), allow_altgr).text
        if not text:
            raise ValueError(f"Datei ist nach der Normalisierung leer: {path.name}")
        self.chunk = TextChunk(text, path.name)

    def next_chunk(self) -> TextChunk:
        return self.chunk


def parse_phrases(raw: str, allow_altgr: bool) -> list[str]:
    """Eine Phrase pro Zeile; normalisiert, leere Zeilen entfallen."""
    phrases = []
    for line in raw.splitlines():
        p = normalize(line, allow_altgr).text.replace("\n", " ")
        if p:
            phrases.append(p)
    return phrases


class PhraseSource(TextSource):
    """Phrasen aus dem Textfeld; ein Chunk = ein Durchgang (alle Phrasen einmal),
    getrennt durch Enter. Bei „gemischt“ wird jeder Durchgang neu gemischt, ohne
    dass dieselbe Phrase direkt an der Durchgangsgrenze doppelt kommt."""
    separator = "\n"

    def __init__(self, phrases: list[str], name: str, rng: random.Random, shuffle: bool) -> None:
        if not phrases:
            raise ValueError("Keine Phrasen eingegeben.")
        self.phrases = phrases
        self.name = name
        self.rng = rng
        self.shuffle = shuffle
        self._last: int | None = None

    def next_chunk(self) -> TextChunk:
        order = list(range(len(self.phrases)))
        if self.shuffle:
            self.rng.shuffle(order)
            if len(order) > 1 and order[0] == self._last:
                order[0], order[1] = order[1], order[0]
        self._last = order[-1]
        return TextChunk("\n".join(self.phrases[i] for i in order), self.name, tuple(order))


# --- Fabrik --------------------------------------------------------------------

def build_source(settings: SessionSettings, library: TextLibrary) -> TextSource:
    """Passende Quelle zu den Einstellungen bauen. Seed -> eigener Zufallsgenerator."""
    rng = random.Random(settings.seed)
    mode = settings.source_mode

    if mode is SourceMode.PHRASES:
        phrases = [normalize(p, settings.allow_altgr).text for p in settings.phrases]
        return PhraseSource([p for p in phrases if p],
                            settings.phrase_set_name or "Eigene Phrasen", rng, settings.shuffle)

    if mode is SourceMode.SPECIFIC_TEXT:
        # mit Zeitlimit wird der Text bei Bedarf wiederholt (Prüfungs-Abschrift)
        if settings.specific_file is None:
            raise ValueError("Keine Datei gewählt.")
        return FileSource(settings.specific_file, settings.allow_altgr)

    if mode is SourceMode.RANDOM_TEXT:
        texts = library.texts
        if settings.text_group:
            texts = [t for t in texts if text_group(t.name) == settings.text_group]
            if not texts:
                raise ValueError(f"Keine Texte in der Gruppe „{settings.text_group}“.")
        return RandomFileSource(texts, rng, settings.allow_altgr)

    # RANDOM_WORDS: ohne Zeitlimit die gewählte Wortanzahl, mit Zeitlimit Nachladeblöcke
    count = settings.word_count if settings.time_limit_s is None else config.WORD_CHUNK
    name = settings.wordlist or library.wordlist_name
    words = library.words_for(name)
    if not words:
        raise ValueError(f"Wortliste nicht gefunden oder leer: {name}")
    return WordSource(words, name, rng, count, settings.allow_altgr,
                      settings.words_lowercase, settings.word_min_len, settings.word_max_len)
