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
        "vision": "gemini-3.5-flash-lite",
        "text": "gemini-3.5-flash-lite",
        "classify": "gemini-3.5-flash-lite",
        "price_in": 0.30,
        "price_out": 2.50,
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
ARBITER_MODEL = os.getenv("LL_ARBITER_MODEL", VISION_MODEL)
ARBITER_ENABLED = os.getenv("LL_ARBITER", "1") not in ("0", "false", "no")
ARBITER_MODE = os.getenv("LL_ARBITER_MODE", "signal")
MAX_DISPUTES = int(os.getenv("LL_MAX_DISPUTES", "12"))
FALLBACK_MODELS = [m for m in os.getenv("LL_FALLBACK_MODELS", "gemini-3.5-flash").split(",") if m.strip()]
GEMINI_RPM = int(os.getenv("LL_GEMINI_RPM", "15"))
PRICE_IN_PER_M = float(os.getenv("LL_PRICE_IN_PER_M", _DEFAULTS["price_in"]))
PRICE_OUT_PER_M = float(os.getenv("LL_PRICE_OUT_PER_M", _DEFAULTS["price_out"]))

EXTRACT_EFFORT = os.getenv("LL_EXTRACT_EFFORT", "medium")
RENDER_DPI = int(os.getenv("LL_RENDER_DPI", "150"))
MAX_PAGES = int(os.getenv("LL_MAX_PAGES", "4"))
DEFAULT_REVIEW_THRESHOLD = float(os.getenv("LL_REVIEW_THRESHOLD", "0.85"))
STATE_DIR = Path(os.getenv("LL_STATE_DIR", ROOT / "state"))
CORRECTION_WEIGHT = int(os.getenv("LL_CORRECTION_WEIGHT", "10"))

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
