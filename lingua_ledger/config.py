from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"

PROVIDER = os.getenv("LL_PROVIDER") or (
    "gemini" if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) else "anthropic"
)

_DEFAULTS = {
    "gemini": {
        "vision": "gemini-3-flash-preview",
        "text": "gemini-3-flash-preview",
        "classify": "gemini-3.1-flash-lite-preview",
        "price_in": 0.5,
        "price_out": 3.0,
    },
    "anthropic": {
        "vision": "claude-sonnet-5-5",
        "text": "claude-sonnet-5-5",
        "classify": "claude-haiku-5-5",
        "price_in": 2.0,
        "price_out": 10.0,
    },
}[PROVIDER]

VISION_MODEL = os.getenv("LL_VISION_MODEL", _DEFAULTS["vision"])
TEXT_MODEL = os.getenv("LL_TEXT_MODEL", _DEFAULTS["text"])
CLASSIFY_MODEL = os.getenv("LL_CLASSIFY_MODEL", _DEFAULTS["classify"])
PRICE_IN_PER_M = float(os.getenv("LL_PRICE_IN_PER_M", _DEFAULTS["price_in"]))
PRICE_OUT_PER_M = float(os.getenv("LL_PRICE_OUT_PER_M", _DEFAULTS["price_out"]))

EXTRACT_EFFORT = os.getenv("LL_EXTRACT_EFFORT", "medium")
RENDER_DPI = int(os.getenv("LL_RENDER_DPI", "150"))
MAX_PAGES = int(os.getenv("LL_MAX_PAGES", "4"))
DEFAULT_REVIEW_THRESHOLD = float(os.getenv("LL_REVIEW_THRESHOLD", "0.85"))

TESSERACT_LANGS = {
    "en": "eng",
    "de": "deu",
    "fr": "fra",
    "es": "spa",
    "it": "ita",
    "pt": "por",
    "ja": "jpn",
    "zh": "chi_sim",
    "id": "ind",
    "hi": "hin",
    "nl": "nld",
    "pl": "pol",
}


def tesseract_lang(code: str | None) -> str:
    base = TESSERACT_LANGS.get((code or "en").lower(), "eng")
    return base if base == "eng" else f"{base}+eng"
