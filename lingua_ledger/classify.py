from __future__ import annotations

import re
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from .config import CLASSIFY_MODEL
from .llm import call_structured, has_api_key, image_blocks
from .schemas import Classification, DocType

SYSTEM = (
    "You classify scanned business documents. Decide the document type and the dominant language of the "
    "printed text. Types: invoice (bill requesting payment, has invoice number and totals), receipt "
    "(point-of-sale proof of purchase), form (labelled fields with filled values, questionnaires, "
    "applications), contract (legal agreement between parties). Use ISO 639-1 language codes."
)


class ClassifyOut(BaseModel):
    doc_type: Literal["invoice", "receipt", "form", "contract"]
    language: str = Field(description="ISO 639-1 code such as en, de, ja, zh")
    confidence: float = Field(ge=0, le=1)


_KEYWORDS = {
    DocType.invoice: [
        "invoice",
        "rechnung",
        "facture",
        "factura",
        "fattura",
        "fatura",
        "請求書",
        "发票",
        "iban",
        "due date",
    ],
    DocType.receipt: ["receipt", "total", "cash", "change", "thank you", "kasir", "tunai", "kembali", "qty"],
    DocType.contract: [
        "agreement",
        "hereinafter",
        "party",
        "parties",
        "governing law",
        "whereas",
        "witnesseth",
    ],
}


def classify(images: list[Image.Image], ocr_text: str | None = None) -> Classification:
    if has_api_key():
        content = image_blocks(images[:1], max_side=1200)
        content.append({"type": "text", "text": "Classify this document."})
        out, _ = call_structured(CLASSIFY_MODEL, SYSTEM, content, ClassifyOut, max_tokens=2000, effort="low")
        try:
            return Classification(
                doc_type=DocType(out["doc_type"]),
                language=out.get("language", "en")[:2].lower(),
                confidence=float(out.get("confidence", 0.5)),
            )
        except (KeyError, ValueError):
            pass
    return heuristic(ocr_text or "")


def heuristic(text: str) -> Classification:
    low = text.lower()
    scores = {t: sum(low.count(k) for k in kws) for t, kws in _KEYWORDS.items()}
    best = max(scores, key=scores.get) if any(scores.values()) else DocType.form
    lang = "en"
    if re.search(r"[぀-ヿ]", text):
        lang = "ja"
    elif re.search(r"[一-鿿]", text):
        lang = "zh"
    elif re.search(r"\b(und|der|die|rechnung)\b", low):
        lang = "de"
    elif re.search(r"\b(et|le|la|facture)\b", low):
        lang = "fr"
    elif re.search(r"\b(y|el|factura)\b", low):
        lang = "es"
    return Classification(doc_type=best, language=lang, confidence=0.3)
