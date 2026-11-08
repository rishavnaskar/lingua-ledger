from __future__ import annotations

from typing import Any

from PIL import Image
from pydantic import ValidationError

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

SYSTEM_VISION = "You are a meticulous multilingual document data-entry specialist reading page images. " + RULES
SYSTEM_TEXT = (
    "You are a meticulous multilingual document data-entry specialist. You receive OCR text of a document, "
    "line by line in reading order; OCR may contain character errors, so prefer values consistent with the "
    "document's own arithmetic and formats. " + RULES
)


def tool_schema(doc_type: DocType) -> dict[str, Any]:
    model = SCHEMAS[doc_type]
    data_schema = model.model_json_schema()
    defs = data_schema.pop("$defs", None)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "data": data_schema,
            "field_confidence": {
                "type": "object",
                "description": "0-1 confidence per top-level field name that was filled",
                "additionalProperties": {"type": "number"},
            },
        },
        "required": ["data", "field_confidence"],
    }
    if defs:
        schema["$defs"] = defs
    return schema


def _parse(out: dict[str, Any], doc_type: DocType) -> tuple[dict[str, Any], dict[str, float]]:
    model = SCHEMAS[doc_type]
    raw = out.get("data") or {}
    try:
        data = model.model_validate(raw).model_dump()
    except ValidationError:
        data = model.model_validate({k: v for k, v in raw.items() if k in model.model_fields}).model_dump()
    conf = {k: float(v) for k, v in (out.get("field_confidence") or {}).items() if isinstance(v, (int, float))}
    return data, conf


def extract_vision(images: list[Image.Image], doc_type: DocType) -> PathOutput:
    content = image_blocks(images)
    content.append({"type": "text", "text": f"Extract the {doc_type.value} data from these pages."})
    try:
        out, meta = call_structured(VISION_MODEL, SYSTEM_VISION, content, tool_schema(doc_type), effort=EFFORT)
        data, conf = _parse(out, doc_type)
        return PathOutput(path="vision", data=data, self_confidence=conf, latency_s=meta["latency_s"],
                          input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"])
    except Exception as e:  # noqa: BLE001
        return PathOutput(path="vision", data=SCHEMAS[doc_type]().model_dump(), error=f"{type(e).__name__}: {e}")


def extract_text(ocr_text: str, doc_type: DocType) -> PathOutput:
    content = f"OCR text of the document:\n\n{ocr_text}\n\nExtract the {doc_type.value} data."
    try:
        out, meta = call_structured(TEXT_MODEL, SYSTEM_TEXT, content, tool_schema(doc_type), effort=EFFORT)
        data, conf = _parse(out, doc_type)
        return PathOutput(path="ocr_text", data=data, self_confidence=conf, latency_s=meta["latency_s"],
                          input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"])
    except Exception as e:  # noqa: BLE001
        return PathOutput(path="ocr_text", data=SCHEMAS[doc_type]().model_dump(), error=f"{type(e).__name__}: {e}")
