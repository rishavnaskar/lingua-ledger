from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"

VISION_MODEL = os.getenv("LL_VISION_MODEL", "claude-sonnet-5-5")
TEXT_MODEL = os.getenv("LL_TEXT_MODEL", "claude-sonnet-5-5")
CLASSIFY_MODEL = os.getenv("LL_CLASSIFY_MODEL", "claude-haiku-5-5")

EXTRACT_EFFORT = os.getenv("LL_EXTRACT_EFFORT", "medium")
RENDER_DPI = int(os.getenv("LL_RENDER_DPI", "150"))
MAX_PAGES = int(os.getenv("LL_MAX_PAGES", "4"))
DEFAULT_REVIEW_THRESHOLD = float(os.getenv("LL_REVIEW_THRESHOLD", "0.85"))

TESSERACT_LANGS = {
    "en": "eng", "de": "deu", "fr": "fra", "es": "spa", "it": "ita", "pt": "por",
    "ja": "jpn", "zh": "chi_sim", "id": "ind", "hi": "hin", "nl": "nld", "pl": "pol",
}


def tesseract_lang(code: str | None) -> str:
    base = TESSERACT_LANGS.get((code or "en").lower(), "eng")
    return base if base == "eng" else f"{base}+eng"
