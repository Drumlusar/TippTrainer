# Architekturplan: Tipptrainer für das 10-Finger-System

**Sprache:** Python 3.11+  ·  **GUI:** PySide6 (Qt)  ·  **Graph:** matplotlib  ·  **Oberfläche:** Deutsch

---

## 1. Ziel und Umfang

Ein Desktop-Programm zum Üben des 10-Finger-Systems (Tipp10). Es misst:

- **Anschläge pro Minute (A/min)**: live während des Tippens und als Durchschnitt am Ende
- **Fehler**: jedes getippte Zeichen, das nicht mit dem Originalzeichen an dieser Position übereinstimmt

Am Ende jeder Runde gibt es eine Übersicht mit Einstellungen, Textname(n), Fehlern, Durchschnitts-A/min, dem Text mit rot markierten Fehlern und einem A/min-Verlaufsgraphen. Die wichtigsten Kennzahlen jeder Runde werden in einer CSV-Datei gespeichert.

---

## 2. Einstellungen (Hauptmenü)

| Einstellung | Optionen | Standard |
|---|---|---|
| **Zeitlimit** | Toggle an/aus; Presets 30 s / 60 s / 120 s / 300 s / 600 s + freie Eingabe in Sekunden | aus |
| **Textquelle** | *Zufällige Wörter* · *Zufälliger Text* (aus Textordner) · *Spezifischer Text* (Datei wählen) | Zufälliger Text |
| **Wortanzahl** (nur *Zufällige Wörter* ohne Zeitlimit) | Presets 25 / 50 / 100 + freie Eingabe | 50 |
| **Eingabemodus** | *Computer* (Backspace erlaubt) · *Schreibmaschine* (kein Backspace) | Computer |
| **Death by Mistake** | Toggle an/aus | aus |
| **AltGr-Zeichen zulassen** | Toggle an/aus (`@ € { } [ ] \ ~ \|`) | aus |

### Abhängigkeiten zwischen den Einstellungen

```
Zeitlimit AN  → Textquelle ∈ { Zufällige Wörter, Zufälliger Text }
                 "Spezifischer Text" ist ausgegraut
                 Wortanzahl ist ausgegraut (Wörter/Texte werden nachgeladen, bis die Zeit abläuft)

Zeitlimit AUS → Textquelle ∈ { Zufällige Wörter, Zufälliger Text, Spezifischer Text }
                 Runde endet, wenn der Text vollständig getippt ist
```

`Death by Mistake`, `Eingabemodus` und `AltGr` sind mit allen Kombinationen frei kombinierbar.

---

## 3. Bildschirme und Ablauf

```
            ┌──────────────┐
            │  Hauptmenü   │◄──────────────────────────────┐
            └──────┬───────┘                               │
                   │ Start                                 │ Esc / Button "Menü"
                   ▼                                       │
            ┌──────────────┐   Fehler + Death by Mistake  ┌┴─────────────┐
     ┌─────►│ Tippansicht  │─────────────────────────────►│ Deathscreen  │
     │      └──────┬───────┘                              └┬─────────────┘
     │             │ Text fertig / Zeit abgelaufen         │ Leertaste (nach 0,5 s Sperre)
     │             ▼                                       │ → gleicher Text neu
     │      ┌──────────────┐                               │
     │      │  Ergebnis    │───── "Menü" ──────────────────┼──► Hauptmenü
     │      └──────┬───────┘                               │
     │             │ "Nochmal" (gleicher Text)             │
     └─────────────┴───────────────────────────────────────┘
```

**Hauptmenü, rechte Spalte „Letzte Runden“:** scrollbare Liste der gespeicherten Runden (zwei Zeilen je Runde: Datum + Modus, A/min + Fehler + Ergebnis). Klick öffnet Ergebnisansicht bzw. Deathscreen der Runde; „Nochmal“ startet von dort denselben Text (gleicher Seed). Der Stern ☆/★ markiert eine Runde als dauerhaft gespeichert; sonst bleiben die letzten 20 Runden erhalten.

Alle Bildschirme liegen in einem `QStackedWidget`. Es gibt keinen Fensterwechsel und kein Neuladen. Ein Neustart setzt nur den Zustand zurück.

### 3.1 Tippansicht

```
┌──────────────────────────────────────────────────────────┐
│   247 A/min        Fehler: 3          Zeit: 0:42 / 1:00  │  ← Live-Leiste
│                                                          │
│   Der schnelle braune Fuchs springt über den faulen      │  ← bereits getippt (dunkel / rot)
│   Hund.↵ Zwölf Boxkämpfer jagen Viktor quer über│den    │  ← aktuelle Zeile, Balken-Cursor
│   großen Sylter Deich. Franz jagt im komplett            │  ← noch nicht getippt (grau)
│                                                          │
│   Esc = zurück zum Menü                                  │
└──────────────────────────────────────────────────────────┘
```

Die Darstellung orientiert sich an Monkeytype und ähnlichen Tipptests:

- Monospace-Schrift in großer Schriftgröße, z. B. 26 pt. Gesucht wird in dieser Reihenfolge: JetBrains Mono → Consolas → DejaVu Sans Mono → Systemstandard.
- Zeichenfarben:
  - grau: noch nicht getippt
  - normale Textfarbe: korrekt
  - rot: falsch
  - Ist ein falsches Leerzeichen gefordert, erscheint ein roter Hintergrundblock, weil man rote Leerzeichen nicht sieht.
- Der Cursor ist ein Balken vor dem nächsten erwarteten Zeichen.
- Es sind genau 3 Zeilen sichtbar. Die aktuelle Zeile bleibt in der Mitte, der Text scrollt zeilenweise mit.
- Zeilenumbrüche werden als `↵` angezeigt und erzwingen danach einen echten Umbruch.
- Bei Zeitlimit mit mehreren Texten wird der nächste Text nahtlos angehängt, getrennt durch einen `↵`.
- Die Live-Leiste wird alle 200 ms aktualisiert. Vor dem ersten Anschlag steht dort: „Beginnen Sie zu tippen …“.

### 3.2 Deathscreen

Er erscheint sofort beim ersten Fehler, wenn Death by Mistake aktiv ist.

- Großer Hinweis „Fehler!“, darunter das erwartete Zeichen und das getippte Zeichen, z. B. `erwartet: „e“ – getippt: „r“`
- Statistik bis dahin: Dauer, Anschläge, A/min, Fortschritt in %
- **Leertaste:** derselbe Text startet neu. Alle Tasten (auch N und Esc) sind erst nach 0,5 s aktiv, damit ein im Tippfluss gedrücktes Leerzeichen nicht sofort einen Neustart auslöst. Ein dezenter Hinweis „Leertaste = Neustart“ blendet nach Ablauf der Sperre ein.
- **Esc oder Button:** zurück zum Hauptmenü
- Die abgebrochene Runde wird mit `abgebrochen = ja` gespeichert.

### 3.3 Ergebnisansicht

- **Kopfbereich:** Einstellungen der Runde, Textname(n), Dauer
- **Kennzahlen:** Anschläge gesamt, Fehler, Fehlerquote in %, Ø A/min, Spitzen-A/min
- **Textansicht:** der vollständige Text. Fehlerhafte Positionen sind rot markiert. Im Computer-Modus erscheinen korrigierte Fehler rot unterstrichen, nicht korrigierte rot hinterlegt.
- **Graph:**
  - A/min über die Zeit, in 1-Sekunden-Schritten, geglättet über ein gleitendes 5-Sekunden-Fenster
  - eine gestrichelte Linie für den Durchschnitt
  - rote Punkte auf der Zeitachse, wo Fehler passiert sind
- **Buttons:**
  - „Nochmal“: gleicher Text, Leertaste funktioniert hier ebenfalls
  - „Neuer Text“
  - „Menü“

---

## 4. Begriffe und Messregeln

Die Regeln gelten für alle Modi.

| Begriff | Definition |
|---|---|
| **Anschlag** | Jede Eingabe, die ein Zeichen erzeugt, einschließlich Leerzeichen und Enter. Backspace, Shift, Strg, Esc usw. zählen **nicht**. |
| **Fehler** | Ein Anschlag, dessen Zeichen nicht mit dem erwarteten Zeichen an der Cursorposition übereinstimmt. |
| **A/min** | `Anschläge / Minuten`. Gezählt wird brutto, also mit Fehlern, wie bei Tipp10. **Backspace ist kein Anschlag** und fließt nicht in die Geschwindigkeit ein. |
| **Fehler** (Anzeige) | Im Computer-Modus die aktuell *stehenden* Fehler – gelöschte Fehler werden abgezogen. Zusätzlich wird „korrigiert“ gezählt. |
| **Zeitstart** | Mit dem **ersten Anschlag**, nicht beim Öffnen der Ansicht. |
| **Zeitende** | Bei Zeitlimit, sobald die Zeit abgelaufen ist; alle bis dahin getippten Zeichen zählen. Ohne Zeitlimit beim korrekt oder falsch getippten letzten Zeichen. |

### Verhalten pro Eingabemodus

| Situation | Computer | Schreibmaschine |
|---|---|---|
| Falsches Zeichen | Fehler +1, Zeichen rot, Cursor rückt weiter | Fehler +1, Zeichen rot, Cursor rückt weiter |
| Backspace über falsches Zeichen | Cursor zurück, Position wieder grau, **Fehler −1**. Die Position bleibt intern als „korrigiert“ markiert (Ergebnis: rot unterstrichen, Zähler „korrigiert“). | wird ignoriert |
| Backspace über richtiges Zeichen | Cursor zurück, Fehlerzahl unverändert | wird ignoriert |
| Dieselbe Position erneut falsch | erneut Fehler +1 | – |

**Beispiel Computer-Modus**, erwarteter Text `Haus`:

```
Eingabe:  H  a  i  ⌫  u  s
Fehler:   0  0  1  0  0  0     → 0 Fehler, 1 korrigiert, Anschläge = 5 (Backspace zählt nicht)
Ergebnis: H a u s  – das „u“ ist rot unterstrichen (korrigierter Fehler)
```

**Beispiel Schreibmaschine**, gleicher Text:

```
Eingabe:  H  a  i  u  s
Ergebnis: H a i u  – Position 3 bleibt rot, „u“ landet auf Position 4 (erwartet „s“) → 2 Fehler
```

Das zweite Beispiel zeigt bewusst die Verschiebungsfalle. Im Schreibmaschinenmodus lohnt es sich nicht, ein vergessenes Zeichen „nachzuholen“. Man tippt einfach mit dem nächsten Zeichen weiter.

**Death by Mistake** löst in beiden Modi beim ersten Fehler sofort aus. Korrigieren ist dann nicht mehr möglich.

---

## 5. Texte, Normalisierung und Zeichensatz

### 5.1 Ordnerstruktur der Daten

```
daten/
├── texte/              ← beliebige .txt-Dateien, Dateiname = Textname
│   ├── fuchs.txt
│   └── zeitungsartikel_01.txt
├── wortlisten/
│   └── deutsch.txt     ← ein Wort pro Zeile
└── verlauf/
    └── sessions.csv    ← wird automatisch angelegt
```

### 5.2 Kodierung

1. Die Datei wird als **UTF-8** gelesen. Ein BOM wird dabei erkannt und entfernt.
2. Schlägt das fehl, wird sie als **Windows-1252** gelesen. Das ist der typische Fall bei Dateien aus älterem Windows-Editor.
3. Schlägt auch das fehl, erscheint eine Fehlermeldung im Menü und die Datei wird übersprungen.

Die CSV-Datei wird als **UTF-8 mit BOM** und mit **Semikolon** als Trennzeichen geschrieben. So öffnet das deutsche Excel sie per Doppelklick korrekt, inklusive Umlauten.

### 5.3 Erlaubte Zeichen

| Gruppe | Zeichen | Status |
|---|---|---|
| Grundtasten (± Shift) | `a–z A–Z ä ö ü Ä Ö Ü ß 0–9` `! " § $ % & / ( ) = ? ' * + # - _ . : , ; < >` Leerzeichen, Enter | immer erlaubt |
| AltGr | `@ € { } [ ] \ ~ \|` | nur mit Toggle „AltGr zulassen“ |
| Tottasten | `^ ´ \`` und damit gebildete Zeichen (â, é, è …) | nie, werden ersetzt |

### 5.4 Normalisierungstabelle

Die Normalisierung wird beim Laden angewendet, die Originaldatei bleibt unverändert.

| Original | wird zu | Hinweis |
|---|---|---|
| `„ “ ” « » ‹ ›` | `"` | |
| `‚ ‘ ’ ´ \`` | `'` | |
| `– — ‒ −` | `-` | Gedankenstrich, Minuszeichen |
| `…` | `...` | |
| `·` `•` | `-` | Aufzählungspunkte |
| geschütztes Leerzeichen, Tab | ` ` | |
| mehrfache Leerzeichen | ein Leerzeichen | |
| `\r\n`, `\r` | `\n` | Windows-Zeilenenden |
| Leerzeichen am Zeilenende | entfernt | sonst müsste man unsichtbare Zeichen tippen |
| mehrere Leerzeilen | ein `\n` | |
| `é è ê à â …` | `e e e a a …` | Akzent wird entfernt (Unicode-NFKD) |
| `€` (AltGr aus) | `EUR` | |
| `@` (AltGr aus) | `at` | |
| `[ ] { }` (AltGr aus) | `( )` | |
| `\ ~ \|` (AltGr aus) | `/ - /` | |
| `^` | entfernt | |
| sonstige unbekannte Zeichen | entfernt | werden pro Datei gezählt und im Log ausgegeben |

Leerzeichen und Zeilenumbrüche am Anfang und Ende des Textes werden entfernt.

**Beispiel:**

```
Original:    „Café-Preise steigen – um 5 € …“
Normalisiert: "Cafe-Preise steigen - um 5 EUR ..."
```

### 5.5 Textquellen

| Quelle | Verhalten ohne Zeitlimit | Verhalten mit Zeitlimit |
|---|---|---|
| Zufällige Wörter | N Wörter aus der Wortliste, durch Leerzeichen getrennt | Wörter werden blockweise nachgeladen (jeweils 30), solange die Zeit läuft |
| Zufälliger Text | eine zufällige Datei aus `texte/` | zufällige Dateien nacheinander, getrennt durch `↵`; direkt hintereinander nie dieselbe Datei |
| Spezifischer Text | die gewählte Datei | nicht verfügbar |

**Neustart mit identischem Text:** Jede Runde erhält einen **Zufalls-Seed**. Bei einem Neustart über Leertaste oder „Nochmal“ wird derselbe Seed verwendet. Dadurch entstehen dieselbe Wortfolge bzw. dieselbe Reihenfolge der Texte, auch im Zeitlimit-Modus, wo erst beim Tippen nachgeladen wird. „Neuer Text“ erzeugt einen neuen Seed.

---

## 6. Softwarearchitektur

### 6.1 Grundprinzip: Logik und Oberfläche trennen

```
┌───────────────────────── ui/ (PySide6) ──────────────────────────┐
│  MenuView   TypingView   DeathView   ResultView   CpmChart       │
│       │          │ Tasten-Events ▲ Zustand anzeigen              │
└───────┼──────────┼───────────────┼───────────────────────────────┘
        ▼          ▼               │
┌────────────────── core/ (reines Python, ohne Qt) ────────────────┐
│  SessionController ──► TypingEngine ──► Metrics                  │
│         │                                                        │
│         └──► TextSource (Wörter / Zufallstext / Datei)           │
│                    └──► TextNormalizer                           │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
                 storage/HistoryStore  ──► sessions.csv
```

Der Ordner `core/` importiert **kein** Qt. Dadurch lässt sich die gesamte Tipplogik mit `pytest` testen, ohne ein Fenster zu öffnen. Ein Test simuliert z. B. die Eingabe `"Hais"` auf den Text `"Haus"` und prüft, dass genau 1 Fehler gezählt wird.

### 6.2 Projektstruktur

```
tipptrainer/
├── main.py                     # Einstiegspunkt: QApplication starten, MainWindow öffnen
├── config.py                   # Pfade, Presets, Konstanten (Fenstergröße 5 s, Sperre 0,5 s …)
├── core/
│   ├── models.py               # Dataclasses und Enums
│   ├── text_normalizer.py      # Kodierung erkennen + Normalisierung (Abschnitt 5)
│   ├── text_source.py          # WordSource, RandomFileSource, FileSource
│   ├── typing_engine.py        # Tastenlogik, Cursor, Fehler, Zustand pro Zeichen
│   ├── metrics.py              # A/min live, gleitendes Fenster, Verlauf für den Graphen
│   └── session.py              # SessionController: steuert Ablauf, Zeitlimit, Ende, Tod
├── storage/
│   └── history.py              # CSV schreiben/lesen
├── ui/
│   ├── main_window.py          # QStackedWidget, wechselt zwischen den Ansichten
│   ├── menu_view.py
│   ├── typing_view.py          # Live-Leiste + TextDisplay, nimmt Tasten entgegen
│   ├── text_display.py         # eigenes Widget, zeichnet den Text per paintEvent
│   ├── death_view.py
│   ├── result_view.py
│   ├── cpm_chart.py            # matplotlib-Canvas (FigureCanvasQTAgg)
│   └── style.qss               # Farben, Schriften (dunkles Theme)
├── daten/                      # siehe 5.1
└── tests/
    ├── test_normalizer.py
    ├── test_typing_engine.py
    └── test_metrics.py
```

### 6.3 Datenmodelle (`core/models.py`)

```python
class SourceMode(Enum):      RANDOM_WORDS, RANDOM_TEXT, SPECIFIC_TEXT
class InputMode(Enum):       COMPUTER, TYPEWRITER
class CharState(Enum):       PENDING, CORRECT, WRONG, CORRECTED   # CORRECTED = war falsch, jetzt richtig
class SessionEnd(Enum):      COMPLETED, TIME_UP, DIED, ABORTED

@dataclass(frozen=True)
class SessionSettings:
    source_mode: SourceMode
    time_limit_s: int | None        # None = kein Zeitlimit
    word_count: int                 # nur RANDOM_WORDS ohne Zeitlimit
    specific_file: Path | None
    input_mode: InputMode
    death_by_mistake: bool
    allow_altgr: bool
    seed: int                       # für identischen Neustart

@dataclass
class SessionResult:
    settings: SessionSettings
    end_reason: SessionEnd
    text_names: list[str]
    target_text: str                # nur der Teil, der erreicht wurde (+ Rest bei Tod)
    char_states: list[CharState]    # für die rote Markierung
    duration_s: float
    keystrokes: int
    errors: int
    cpm_avg: float
    cpm_peak: float
    cpm_series: list[float]         # ein Wert pro Sekunde (nur im Speicher, für den Graphen)
    error_times_s: list[float]      # nur im Speicher, für die roten Punkte im Graphen
```

### 6.4 `TypingEngine`: Kern der Tipplogik

Zustand: `target: str`, `pos: int`, `states: list[CharState]`, `errors: int`, `keystrokes: int`, `ever_wrong: set[int]`

```python
def type_char(self, ch: str, t: float) -> KeyOutcome:
    expected = self.target[self.pos]
    self.keystrokes += 1
    if ch == expected:
        self.states[self.pos] = CharState.CORRECTED if self.pos in self.ever_wrong else CharState.CORRECT
        outcome = KeyOutcome.CORRECT
    else:
        self.states[self.pos] = CharState.WRONG
        self.ever_wrong.add(self.pos)
        self.errors += 1
        outcome = KeyOutcome.WRONG
    self.pos += 1
    return outcome                       # SessionController entscheidet über Tod/Ende

def backspace(self) -> None:             # wird nur im COMPUTER-Modus aufgerufen
    if self.pos > 0:
        self.pos -= 1
        self.states[self.pos] = CharState.PENDING    # ever_wrong bleibt erhalten!

def append_text(self, more: str) -> None:  # Nachladen bei Zeitlimit
```

**Wichtiges Detail:** Damit `CORRECTED` funktioniert, merkt sich `ever_wrong`, welche Positionen jemals falsch waren. Sonst würde ein korrigierter Fehler in der Ergebnisansicht nicht mehr erscheinen.

### 6.5 `Metrics`: Live- und Verlaufswerte

- Die Zeitstempel aller Anschläge liegen in einer `collections.deque`. Sie werden nur im Speicher gehalten und nicht gespeichert.
- **Live-A/min:** Anschläge der letzten 5 s × 12. In den ersten 5 s wird stattdessen durch die bisher vergangene Zeit geteilt, damit nicht zu niedrige Werte entstehen.
- **Verlauf:** Jede volle Sekunde wird ein Live-Wert in `cpm_series` geschrieben. Das ergibt den geglätteten Graphen.
- **Durchschnitt:** `keystrokes / duration_s × 60`

**Beispiel:** Bei t = 12 s liegen 19 Anschläge im Fenster 7–12 s. Live-A/min = 19 × 12 = 228.

### 6.6 `SessionController`: Ablaufsteuerung

Diese Klasse ist ebenfalls Qt-frei. Die UI ruft `tick()` regelmäßig auf.

```python
start(settings)        # Text holen, Engine aufbauen, Zustand WAITING_FOR_FIRST_KEY
on_char(ch)            # erster Anschlag → Zeit starten
                       # Fehler + death_by_mistake → end(DIED)
                       # pos == len(target) und kein Zeitlimit → end(COMPLETED)
                       # Zeitlimit und Restpuffer < 50 Zeichen → Text nachladen
on_backspace()         # nur COMPUTER-Modus
tick(now)              # Zeit abgelaufen → end(TIME_UP); Verlaufswert pro Sekunde
restart()              # gleicher Seed → gleicher Text
abort()                # Esc → end(ABORTED), wird NICHT gespeichert
result() -> SessionResult
```

Die Zeit wird mit `time.perf_counter()` gemessen, nicht mit dem Qt-Timer, weil `QTimer` ungenau sein kann. Ein `QTimer` mit 100 ms in der UI dient nur als „Wecker“ für `tick()` und das Neuzeichnen.

### 6.7 Tasteneingabe in Qt (`TypingView.keyPressEvent`)

| Taste | Behandlung |
|---|---|
| `event.text()` ist ein druckbares Zeichen | `controller.on_char(text)` |
| Enter / Return | `controller.on_char("\n")` |
| Backspace | `controller.on_backspace()`, nur im Computer-Modus |
| Esc | Abbruch → Menü |
| Shift, Strg, Alt, Tab, Pfeile, F-Tasten | ignoriert |
| Strg+Backspace (Wort löschen) | ignoriert, sonst ließe sich das Fehlersystem umgehen |

AltGr-Zeichen kommen über `event.text()` bereits als fertiges Zeichen an, z. B. `@`. Ist AltGr deaktiviert, kommen sie im Text nicht vor. Wer sie trotzdem tippt, macht einfach einen Fehler, es ist keine Sonderbehandlung nötig.

### 6.8 `TextDisplay`: eigenes Zeichen-Widget

Ein `QTextEdit` wäre bei jedem Anschlag zu langsam und schwer kontrollierbar. Deshalb gibt es ein eigenes Widget:

1. **Layout berechnen**, nur bei Textänderung oder Fenstergröße: Der Text wird an Wortgrenzen in Zeilen umgebrochen, die ins Widget passen. Ein `\n` erzwingt einen Umbruch. Ergebnis ist eine Liste `lines: list[tuple[start_idx, end_idx]]`.
2. **Zeichnen** in `paintEvent`: Die Zeile mit dem Cursor wird bestimmt, die Zeile davor, die aktuelle und die danach werden gezeichnet. Die Farbe jedes Zeichens ergibt sich aus `states[i]`.
3. Da die Schrift Monospace ist, liegt jedes Zeichen bei `x = spalte × zeichenbreite`. Das macht das Zeichnen trivial und schnell.

In der Ergebnisansicht wird der komplette Text dagegen als scrollbares `QTextBrowser` mit HTML-Spans dargestellt, weil er dort nur einmal gerendert wird.

---

## 7. Speicherung (`storage/history.py`)

**Datei:** `daten/verlauf/sessions.csv`. Pro Runde wird eine Zeile angehängt. Gespeichert werden nur Kennzahlen, kein Tastenprotokoll, keine einzelnen Fehler und kein Text.

| Spalte | Beispiel |
|---|---|
| datum_zeit | 2026-10-31 22:41:05 |
| textquelle | Zufälliger Text |
| textnamen | fuchs.txt, artikel_01.txt |
| zeitlimit_s | 60 (leer = kein Zeitlimit) |
| eingabemodus | Computer |
| death_by_mistake | ja |
| altgr | nein |
| ergebnis | abgeschlossen / zeit_abgelaufen / gestorben |
| dauer_s | 60.0 |
| anschlaege | 248 |
| fehler | 4 (stehende Fehler) |
| fehler_korrigiert | 2 |
| fehlerquote_prozent | 1,6 (stehende Fehler / getippte Zeichen) |
| apm_durchschnitt | 248.0 |
| apm_spitze | 291.0 |

**Gespeichert werden:** abgeschlossene Runden, Runden mit abgelaufener Zeit und gestorbene Runden. **Nicht gespeichert werden:** per Esc abgebrochene Runden und Runden mit null Anschlägen.

**Zusätzlich (ab Phase 10):** `daten/verlauf/runs/<id>.json` je Runde mit Einstellungen inkl. Seed, Text, Zustand je Zeichen (ein Buchstabe pro Zeichen), A/min-Verlauf und Fehlerzeitpunkten – damit lässt sich der Endbildschirm jeder Runde wieder anzeigen. Aufbewahrung: letzte 20 Runden + alle mit ★ markierten; ältere werden beim Speichern einer neuen Runde gelöscht. Für eine spätere Verlaufsstatistik, z. B. „A/min der letzten 30 Tage“, reicht die CSV aber vollständig aus.

---

## 8. Fehlerfälle und Randbedingungen

| Fall | Verhalten |
|---|---|
| Textordner leer | „Zufälliger Text“ und „Spezifischer Text“ sind ausgegraut, mit Hinweis |
| Wortliste fehlt | „Zufällige Wörter“ ausgegraut |
| Datei nach Normalisierung leer | Datei wird übersprungen, Hinweis im Menü |
| Nur 1 Datei bei Zufallstext mit Zeitlimit | dieselbe Datei wiederholt sich (Ausnahme von der Nicht-Wiederholungs-Regel) |
| Fenster verliert Fokus während des Tippens | die Zeit läuft weiter (wie bei echten Tests); kein Pausieren |
| `sessions.csv` in Excel geöffnet (gesperrt) | Hinweis „Ergebnis konnte nicht gespeichert werden“, das Programm läuft weiter |
| Sehr schnelles Tippen | kein Problem: Jede Taste ist ein eigenes Event, die Verarbeitung dauert < 1 ms |

---

## 9. Abhängigkeiten

```
PySide6       # GUI
matplotlib    # Graph in der Ergebnisansicht
pytest        # nur für Tests
```

Alles andere stammt aus der Standardbibliothek: `csv`, `unicodedata`, `random`, `time`, `pathlib`, `dataclasses`, `collections`.

---

## 10. Umsetzungsreihenfolge

Jede Phase ist für sich testbar und in kleinen Schritten machbar.

1. **`text_normalizer.py` + Tests**: Kodierung und Normalisierungstabelle. Beispiel-Test: `„Café – 5 €“` → `"Cafe - 5 EUR"`
2. **`typing_engine.py` + Tests**: beide Eingabemodi und die Beispiele aus Abschnitt 4 als Testfälle
3. **`metrics.py` + Tests**: gleitendes Fenster mit künstlichen Zeitstempeln
4. **`text_source.py`**: alle drei Quellen, Seed-Reproduzierbarkeit testen (gleicher Seed → gleicher Text)
5. **`session.py`**: Ablauf, Zeitlimit, Nachladen, Tod, Neustart
6. **Minimale UI**: Hauptmenü + Tippansicht mit einfachem Text, erster echter Durchlauf
7. **`text_display.py`**: schöne Darstellung mit 3 Zeilen, Scrollen und Cursor
8. **Deathscreen + Ergebnisansicht + Graph**
9. **`history.py`**: CSV-Speicherung
10. **Feinschliff**: Stylesheet, Tastaturkürzel, Hinweistexte

---

## 11. Erweiterung: Reiter und Phrasen-Modus

**Hauptmenü in drei Reitern:** *Training* (Abschnitt 2), *Phrasen* (unten), *Verlauf* (Liste „Letzte Runden“). Enter startet den aktiven Reiter; im Phrasen-Textfeld fügt Enter eine Zeile ein, dort startet ⌘/Strg + Enter. Der Textordner wird bei jeder Rückkehr ins Menü neu eingelesen.

**Phrasen-Modus** (eigene Einstellungen, unabhängig vom Reiter Training):

| Einstellung | Optionen |
|---|---|
| Phrasen | Textfeld, eine Phrase pro Zeile (normalisiert wie Texte) |
| Presets | Auswahl lädt ins Textfeld; „Speichern unter …“, „Überschreiben“, „Löschen“ → `daten/phrasen_presets.json`; der letzte Feldinhalt wird gemerkt |
| Durchgänge | 3× / 5× / 10× / 20× / Eigene … / Unendlich |
| Reihenfolge | der Reihe nach · zufällig gemischt (je Durchgang neu, keine Doppelung an der Grenze) |
| Bei Fehler | weitertippen · Phrase neu beginnen · Death by Mistake |
| Eingabe | Computer / Schreibmaschine, AltGr |

- Ein Durchgang = alle Phrasen einmal, getrennt durch ein Leerzeichen (eine Leertaste). Das Leerzeichen nach einer Phrase gehört zu ihr. In der Tippansicht beginnt trotzdem jede Phrase in einer neuen Zeile, es sind also höchstens 3 Phrasen gleichzeitig zu sehen (lange Phrasen können zwei Zeilen belegen).
- **Unendlich:** Text wird nachgeladen; **Esc beendet mit Auswertung** (Ergebnis „beendet“). Bei fester Anzahl ist Esc wie überall ein Abbruch.
- **Phrase neu beginnen:** Nach einem Fehler springt der Cursor an den Anfang der aktuellen Phrase; der Fehler zählt als gemacht (Live-Anzeige zeigt hier alle Fehler).
- **Auswertung je Phrase:** Tabelle mit Durchgängen, Ø A/min (nur vollständige Durchgänge; Zeit vom Enter davor bis zum eigenen Enter) und Fehler gesamt (inkl. korrigierter).

**Netto-A/min** (alle Modi): richtig stehende Zeichen pro Minute, als zusätzliche Kachel und CSV-Spalte `apm_netto`. Ältere CSV-Dateien werden beim nächsten Speichern automatisch auf die neuen Spalten umgestellt.

---

## 12. Erweiterung: Punkte und Highscores

**Punkte** = (Anschläge − Strafe × Fehler) / Minuten, nie unter 0. Fehler = alle gemachten Fehler inkl. korrigierter. Strafe Standard 10 Anschläge, einstellbar im Reiter Highscores (`daten/einstellungen.json`). Beispiel: 300 Anschläge, 10 Fehler, 1 min → 200 Punkte. Die Punkte werden immer aus Anschlägen/Fehlern/Dauer der CSV neu berechnet, eine geänderte Strafe gilt rückwirkend.

**Reiter Highscores:** oben alle Textdateien (auch ungeübte) mit Bestwert, A/min, Fehler, Versuche, zuletzt geübt; unten Top 10 des gewählten Texts (Punkte, A/min, Netto, Fehler, Zeit, Eingabe, Death by Mistake, Datum). Beide Tabellen sortierbar; Filter Eingabe (alle/Computer/Schreibmaschine) und Death by Mistake (egal/nur mit/nur ohne). Klick auf einen Eintrag öffnet seine Auswertung.

**Es zählen** nur Runden ohne Zeitlimit mit genau einem vollständig getippten Text (Zufälliger oder Spezifischer Text); Death by Mistake nur überlebt. Quelle: `sessions.csv` – auch ältere Runden zählen.

**Rekorde:** Banner „Neuer Rekord!“ in der Ergebnisansicht (bzw. „Erster Eintrag“), Platz 1 golden, frischer Rekord in der Top-10 hinterlegt und mit „NEU“; Etikett „REKORD“ in der Verlaufsliste. Die Auswertungen der Top 10 je Text sind vor dem Aufräumen geschützt – unabhängig von ★. Verlaufsfilter „★ Gespeicherte“ zeigt alle dauerhaft gespeicherten Runden.

---

## 13. Erweiterung: Statistik und W/min

**Reiter Statistik** (Zeitraum 7 Tage / 30 Tage / gesamt):
- Tastaturansicht (QWERTZ), eingefärbt nach Fehlerquote oder Tempo (Groß/Klein und Shift-Zeichen je Taste zusammengefasst, Tooltip mit Zahlen).
- Zusammenfassung inkl. Großbuchstaben vs. Kleinbuchstaben (Shift-Problem).
- Tabellen: Problemzeichen (Groß/Klein getrennt, ab 20 Anschlägen), Verwechslungen (Soll → Ist), Problemwörter (Wort mit mind. einem Fehler, auch korrigiert). Alle sortierbar.
- Häkchen + „Auswahl als Phrasen-Preset …“ legt ein Preset für den Reiter Phrasen an.

**Erfassung:** pro Runde ein Anschlagsprotokoll (erwartet, getippt, Abstand zum vorigen Anschlag/Backspace) → Tagessummen in `daten/verlauf/statistik.json`. Tempo nur für richtige Anschläge, Pausen > 2 s ausgenommen. Es zählen Texte und Zufällige Wörter (keine Phrasen, keine per Esc abgebrochenen Runden).

**W/min** = A/min / 5, klein unter Ø A/min und Netto A/min in der Ergebnisansicht.

---

## 14. Erweiterung: Wettbewerbs- und Prüfungsformate

**Test-Profile** (`storage/profiles.py`, `daten/profile.json`): ein Profil speichert alle Einstellungen des Reiters Training unter einem Namen. Wird mit genau diesen Einstellungen gestartet (Seed egal), trägt die Runde den Profilnamen (CSV-Spalte `profil`). Standardprofile, je Deutsch und Englisch: „Online: Englisch/Deutsch 15/30/60 s“ (Wortliste `englisch_200.txt` bzw. `deutsch_200.txt`, nur Kleinbuchstaben ohne Satzzeichen, 2–6 Buchstaben, Leertaste springt) und „Text: Deutsch/Englisch 5/10 min (Prüfung)“ (Zufälliger Text aus Gruppe `lang_de`/`lang_en`, Prüfungsmodus). Neue Standardprofile späterer Versionen werden einmalig in eine bestehende `profile.json` übernommen (Liste „standard_angeboten“); gelöschte kommen nicht zurück. Speichern unter eigenem Namen, Überschreiben, Löschen im Reiter Training.

**Bestenliste je Profil:** Reiter Highscores, Umschalter „Texte / Test-Profile“. Es zählen Profilrunden mit Ergebnis „abgeschlossen“ oder „Zeit abgelaufen“. Rekord-Banner auch für Profile; Top 10 je Profil vor dem Aufräumen geschützt.

**Reiter Fortschritt** (`storage/progress.py`): je Profil Netto-Tempo pro Tag (Punkte) und gleitender 7-Tage-Schnitt (Mittel aller Runden der letzten 7 Kalendertage), darunter getrennt die Fehlerquote. Kopfzeile: Runden, Tage, aktueller 7-Tage-Schnitt, Konsistenz.

**Konsistenz:** Anschläge je 2-s-Abschnitt; 100 × (1 − Standardabweichung / Mittelwert), begrenzt auf 0–100 %. Erst ab 4 Abschnitten (8 s). Eigene Kachel in der Auswertung, CSV-Spalte `konsistenz_prozent`.

**Ausdauer:** ab 30 s Dauer Tempo und Fehlerquote (alle Fehler je Anschlag) im 1. gegen 3. Drittel der Runde; Zeile unter den Kacheln mit Veränderung in % (unter 5 % = „gleichmäßig“).

**Wortfilter:** „nur Kleinbuchstaben, ohne Satzzeichen“ (Wörter mit Ziffern/Satzzeichen entfallen, Rest klein), min./max. Wortlänge. Bleibt kein Wort übrig, startet die Runde nicht (Meldung).

**Leertaste springt (Online-Verhalten):** Leertaste mitten im Wort → Rest des Wortes zählt als Fehler (verpasst), weiter beim nächsten Wort. Leertaste am Wortanfang wird ignoriert.

**Prüfungsmodus:** während der Runde keine roten Zeichen, kein Live-Tempo, keine Fehlerzahl – nur die Zeit. Auswertung wie gewohnt.

**Textgruppen:** Dateiname bis zum letzten „_“ (z. B. `lang_de_stadtpark.txt` → `lang_de`). Bei Zufälliger Text wählbar. Sechs lange Texte (2.400–2.900 Zeichen) liegen bei, je drei Themen in beiden Sprachen (Gewohnheiten/Practice, Stadtpark/City Park, Bibliothek/Library). **Spezifischer Text** jetzt auch mit Zeitlimit (der Text wiederholt sich bei Bedarf).

**Einheit:** Menü oben rechts A/min oder W/min (= A/min / 5); gilt für Live-Leiste, Auswertung, Graph, Listen und Bestenlisten. Die andere Einheit steht klein darunter. Zeitlimit-Preset 15 s ergänzt.

---

## 15. Erweiterung: Einstellungen und Tempo-Cursor

**Fenster „Einstellungen …“** (Menü oben rechts, `ui/settings_dialog.py`), gespeichert in `daten/einstellungen.json`:
- Design „Dunkel“ oder „Hell“. Alle Farben stehen benannt in `ui/theme.py` (zwei Paletten); `style.qss` enthält Platzhalter (@bg, @accent …), Diagramme, Tabellen und Tastaturansicht fragen die Farben erst beim Zeichnen ab. Der Wechsel wirkt sofort, ohne Neustart. Die Pfeile der Auswahllisten werden je Design als SVG in `ui/pfeile/` erzeugt.
- Schriftgröße des Tipptexts (12–60 pt, Standard 26) und der Oberfläche (80–160 %; skaliert alle Schriftgrößen im Stylesheet und den Ergebnistext).
- Tempo-Cursor an/aus und Zieltempo (Eingabe in der aktuellen Einheit, gespeichert in A/min).

**Tempo-Cursor:** Position = verstrichene Zeit × Zieltempo / 60 Zeichen, ab dem ersten Anschlag; mit Nachkommastellen, daher gleitend (Neuzeichnen alle 30 ms). Schmal und grau, unter dem eigenen Cursor gezeichnet; nur sichtbar, wenn er in den drei angezeigten Zeilen liegt. Im Prüfungsmodus ausgeblendet, weil er das Tempo verraten würde.

---

## 16. Erweiterung: Phrasen-Vorlagen und Feststelltasten-Hinweis

**Phrasen-Vorlagen:** Jede `.txt`-Datei in `daten/phrasen_vorlagen/` ist ein mitgeliefertes Preset (Name = Dateiname, `#`-Zeilen = Kommentare). Mitgeliefert: „Bigramme Deutsch/Englisch“ (je 32 häufige Buchstabenpaare; Zeile = Paar dreimal + drei Beispielwörter) und „Schwierige Wörter Deutsch/Englisch“. Vorlagen stehen in der Auswahl unter den eigenen Presets (durch eine Linie getrennt) und sind schreibgeschützt; ein eigenes Preset gleichen Namens verdeckt die Vorlage, nach dessen Löschen ist sie wieder da. Sie liegen im Repository, die eigenen Presets (`phrasen_presets.json`) nicht.

**Feststelltasten-Hinweis:** Qt kann den Zustand der Feststelltaste nicht abfragen. Er wird aus jedem getippten Buchstaben erschlossen: Großbuchstabe ohne Shift oder Kleinbuchstabe mit Shift = an, sonst aus; Ziffern, Satzzeichen und ß ändern nichts. Ein Druck auf die Feststelltaste schaltet den erschlossenen Zustand um. Ist sie an, erscheint über dem Text „FESTSTELLTASTE AKTIV“ (der Platz ist reserviert, der Text springt nicht).

---

## 17. Mögliche spätere Erweiterungen

Diese Punkte gehören nicht zur ersten Version.

- Lektionen nach Tipp10-Logik (Grundreihe → obere Reihe → …)
