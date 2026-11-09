from __future__ import annotations

from functools import cache
from typing import Any

from PIL import Image
from pydantic import BaseModel, Field, ValidationError, create_model

from .config import EXTRACT_EFFORT as EFFORT
from .config import TEXT_MODEL, VISION_MODEL
from .llm import call_structured, image_blocks
from .schemas import SCHEMAS, DocType, PathOutput

RULES = (
    "Rules: copy values exactly as printed, do not translate names or descriptions. Dates as ISO 8601 "
    "YYYY-MM-DD. Money as plain numbers with a dot decimal separator and no thousands separators or "
    "currency symbols. Currency as an ISO 4217 code. Percentages as plain numbers. Use null for anything "
    "not present; never guess or compute a value that is not printed. For forms, list every labelled field "
    "with its filled value, keeping the label text in the original language. For each top-level field you "
    "fill, also give your own 0-1 confidence that the value is exactly correct under field_confidence; be "
    "honest, lower it when the print is unclear or ambiguous."
)

SYSTEM_VISION = (
    "You are a meticulous multilingual document data-entry specialist reading page images. " + RULES
)
SYSTEM_TEXT = (
    "You are a meticulous multilingual document data-entry specialist. You receive OCR text of a document, "
    "line by line in reading order; OCR may contain character errors, so prefer values consistent with the "
    "document's own arithmetic and formats. " + RULES
)


class FieldConfidence(BaseModel):
    field: str = Field(description="top-level field name that was filled")
    confidence: float = Field(ge=0, le=1, description="0-1 confidence the value is exactly correct")


@cache
def output_model(doc_type: DocType) -> type[BaseModel]:
    model = SCHEMAS[doc_type]
    return create_model(
        f"{model.__name__}Extraction",
        data=(model, ...),
        field_confidence=(list[FieldConfidence], Field(default_factory=list)),
    )


def _parse(out: dict[str, Any], doc_type: DocType) -> tuple[dict[str, Any], dict[str, float]]:
    model = SCHEMAS[doc_type]
    raw = out.get("data") or {}
    try:
        data = model.model_validate(raw).model_dump()
    except ValidationError:
        data = model.model_validate({k: v for k, v in raw.items() if k in model.model_fields}).model_dump()
    if doc_type == DocType.form:
        data = _clean_form(data)
    raw_conf = out.get("field_confidence") or []
    if isinstance(raw_conf, dict):
        raw_conf = [{"field": k, "confidence": v} for k, v in raw_conf.items()]
    conf = {
        str(c["field"]): float(c["confidence"])
        for c in raw_conf
        if isinstance(c, dict) and isinstance(c.get("confidence"), (int, float)) and c.get("field")
    }
    return data, conf


FORM_RULES = (
    " For this form: output one pair per printed label, in reading order, top to bottom and left to right. "
    "Keep the label exactly as printed, without a trailing colon; do not add qualifiers in brackets. The "
    "value is everything filled in next to or below that label, kept together as one value even when it "
    "spans a postal code and an address or several lines. For a group of checkboxes use the group label as "
    "the key and the text of the ticked option as the value; never output true or false. Skip labels with "
    "nothing filled in. Keep Japanese and Chinese text exactly as printed, with no spaces inserted."
)


def _task(doc_type: DocType, prefix: str) -> str:
    text = f"{prefix} the {doc_type.value} data."
    return text + FORM_RULES if doc_type == DocType.form else text


def _clean_form(data: dict[str, Any]) -> dict[str, Any]:
    fields = []
    for item in data.get("fields") or []:
        key = str(item.get("key") or "").strip().rstrip(":：").strip()
        value = item.get("value")
        value = "" if value is None else str(value).strip()
        if not key or value.lower() in ("", "true", "false", "null", "none"):
            continue
        fields.append({"key": key, "value": value})
    return {**data, "fields": fields}


def extract_vision(images: list[Image.Image], doc_type: DocType) -> PathOutput:
    content = image_blocks(images)
    content.append({"type": "text", "text": _task(doc_type, "Extract") + " Use these pages."})
    try:
        out, meta = call_structured(
            VISION_MODEL, SYSTEM_VISION, content, output_model(doc_type), effort=EFFORT
        )
        data, conf = _parse(out, doc_type)
        return PathOutput(
            path="vision",
            data=data,
            self_confidence=conf,
            latency_s=meta["latency_s"],
            input_tokens=meta["input_tokens"],
            output_tokens=meta["output_tokens"],
            model=meta.get("model"),
        )
    except Exception as e:  # noqa: BLE001
        return PathOutput(
            path="vision", data=SCHEMAS[doc_type]().model_dump(), error=f"{type(e).__name__}: {e}"
        )


def extract_text(ocr_text: str, doc_type: DocType) -> PathOutput:
    content = f"OCR text of the document:\n\n{ocr_text}\n\n{_task(doc_type, 'Extract')}"
    try:
        out, meta = call_structured(TEXT_MODEL, SYSTEM_TEXT, content, output_model(doc_type), effort=EFFORT)
        data, conf = _parse(out, doc_type)
        return PathOutput(
            path="ocr_text",
            data=data,
            self_confidence=conf,
            latency_s=meta["latency_s"],
            input_tokens=meta["input_tokens"],
            output_tokens=meta["output_tokens"],
            model=meta.get("model"),
        )
    except Exception as e:  # noqa: BLE001
        return PathOutput(
            path="ocr_text", data=SCHEMAS[doc_type]().model_dump(), error=f"{type(e).__name__}: {e}"
        )
