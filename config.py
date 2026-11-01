"""Zentrale Konstanten und Pfade des Tipptrainers."""
from __future__ import annotations

from pathlib import Path

# --- Pfade -----------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "daten"
TEXT_DIR = DATA_DIR / "texte"
DEFAULT_WORDLIST = "deutsch.txt"
WORDLIST_DIR = DATA_DIR / "wortlisten"
HISTORY_DIR = DATA_DIR / "verlauf"
HISTORY_FILE = HISTORY_DIR / "sessions.csv"
RUNS_DIR = HISTORY_DIR / "runs"          # eine JSON-Datei pro Runde (für die Endbildschirme)
KEEP_RECENT_RUNS = 20                    # so viele nicht markierte Runden bleiben erhalten
PRESETS_FILE = DATA_DIR / "phrasen_presets.json"
PRESET_TEMPLATE_DIR = DATA_DIR / "phrasen_vorlagen"   # mitgelieferte Vorlagen, je Datei ein Preset
SETTINGS_FILE = DATA_DIR / "einstellungen.json"
STATS_FILE = HISTORY_DIR / "statistik.json"
PROFILES_FILE = DATA_DIR / "profile.json"

# --- Messung ---------------------------------------------------------------
CPM_WINDOW_S = 5.0        # gleitendes Fenster für Live-A/min und Graph
SCORE_PENALTY = 10        # Punkte: so viele Anschläge kostet ein Fehler
HIGHSCORE_TOP_N = 10      # Länge der Bestenliste je Text (deren Auswertungen bleiben erhalten)
STATS_PAUSE_S = 2.0       # Statistik: längere Pausen zählen nicht zum Tempo eines Zeichens
STATS_MIN_KEYS = 20       # Statistik: Zeichen erst ab so vielen Anschlägen anzeigen
CONSISTENCY_BUCKET_S = 2.0   # Konsistenz: Anschläge je 2-Sekunden-Abschnitt
THIRDS_MIN_S = 30.0          # Ausdauer-Analyse (Drittel) erst ab dieser Rundendauer
MIN_DIVISOR_S = 1.0       # Untergrenze für die Zeit im Nenner (verhindert Fantasiewerte in den ersten ms)

# --- Ablauf ----------------------------------------------------------------
RESTART_LOCK_S = 0.5      # Sperrzeit der Leertaste auf dem Deathscreen
TIME_LIMIT_PRESETS_S = (15, 30, 60, 120, 300, 600)
WORD_COUNT_PRESETS = (25, 50, 100)
DEFAULT_WORD_COUNT = 50
REPETITION_PRESETS = (3, 5, 10, 20)       # Durchgänge im Phrasen-Modus
WORD_CHUNK = 30           # Wörter pro Nachladeblock im Zeitlimit-Modus
REFILL_THRESHOLD_CHARS = 50

# --- Oberfläche ------------------------------------------------------------
UI_TICK_MS = 100
LIVE_BAR_REFRESH_MS = 200
