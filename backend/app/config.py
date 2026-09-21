"""Central path configuration for WriteUP.

All persistent data lives under <project>/data so the app is fully
self-contained and portable: the SQLite database, paper photos, handwriting
samples, fonts and rendered outputs.
"""
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "writeup.db"
PAPERS_DIR = DATA_DIR / "papers"
SAMPLES_DIR = DATA_DIR / "samples"
FONTS_DIR = DATA_DIR / "fonts"
OUTPUTS_DIR = DATA_DIR / "outputs"
THUMBS_DIR = DATA_DIR / "thumbs"

for _d in (DATA_DIR, PAPERS_DIR, SAMPLES_DIR, FONTS_DIR, OUTPUTS_DIR, THUMBS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Canonical rectified-page height in pixels. Width follows the detected
# page aspect ratio. High enough for crisp ink, small enough for speed.
CANONICAL_PAGE_HEIGHT = 1600
