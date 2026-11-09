"""Focused second look at fields where the two readers disagree.

Each dispute is sent to a vision model as a tight crop of the page around both candidate values, so the
model judges one field at a time instead of re-reading the whole document. By default the verdict only
feeds the confidence score (LL_ARBITER_MODE=signal); with LL_ARBITER_MODE=override it also replaces the
merged value, which did not improve accuracy on the benchmark run.
"""

from __future__ import annotations

from typing import Any, Literal

from PIL import Image
from pydantic import BaseModel, Field

from .confidence import agreement, flatten, leaf_name, unflatten
from .config import ARBITER_MODE, ARBITER_MODEL, MAX_DISPUTES
from .llm import call_structured, image_blocks
from .normalize import parse_amount, parse_date
from .ocr import locate_value
from .schemas import SCHEMAS, ArbiterResult, ArbiterVerdict, DocType, OcrPage

SYSTEM = (
    "You settle disagreements between two automated readers of a business document. For every numbered "
    "dispute you get a crop of the page (sometimes the whole page) and two candidate values, a and b. Look "
    "only at what is printed. Answer a or b when that candidate matches the print exactly; answer other and "
    "give the printed value when neither does; answer unreadable when the crop does not show the field or "
    "the print cannot be made out. Dates as ISO 8601 YYYY-MM-DD, money as plain numbers with a dot decimal "
    "separator and no currency symbols, text copied exactly in the original language. Never guess."
)

SKIP_PREFIXES = ("fields[", "parties[")
NUMERIC_LEAVES = {
    "quantity",
    "unit_price",
    "total",
    "subtotal",
    "tax_rate",
    "tax_amount",
    "service_charge",
    "discount",
    "cash_paid",
    "change",
}


class _Verdict(BaseModel):
    dispute: int = Field(description="dispute number as given")
    choice: Literal["a", "b", "other", "unreadable"]
    value: str | None = Field(None, description="printed value, only when choice is other")
    confidence: float = Field(ge=0, le=1)


class _Output(BaseModel):
    verdicts: list[_Verdict]


def disputes(merged: dict[str, Any], vision: dict[str, Any], ocr: dict[str, Any]) -> list[str]:
    fv, fo = flatten(vision), flatten(ocr)
    out = []
    for path in flatten(merged):
        if path.startswith(SKIP_PREFIXES):
            continue
        a, b = fv.get(path), fo.get(path)
        if a in (None, "", []) or b in (None, "", []):
            continue
        if agreement(path, a, b) is False:
            out.append(path)
    scalars = [p for p in out if "[" not in p]
    items = [p for p in out if "[" in p]
    return (scalars + items)[:MAX_DISPUTES]


def _union(boxes: list[list[int]]) -> list[int]:
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def crop_for(values: list[Any], pages: list[Image.Image], ocr: list[OcrPage]) -> tuple[Image.Image, bool]:
    located = [loc for loc in (locate_value(v, ocr) for v in values) if loc]
    if not located:
        page = pages[0].copy()
        page.thumbnail((1200, 1200))
        return page, False
    page_no = located[0][2]
    box = _union([loc[1] for loc in located if loc[2] == page_no])
    img = pages[page_no]
    w, h = box[2] - box[0], box[3] - box[1]
    pad_x, pad_y = int(w * 0.6) + 60, int(h * 1.5) + 24
    region = (
        max(0, box[0] - pad_x),
        max(0, box[1] - pad_y),
        min(img.width, box[2] + pad_x),
        min(img.height, box[3] + pad_y),
    )
    crop = img.crop(region)
    if crop.width < 700:
        scale = 700 / crop.width
        crop = crop.resize((700, max(1, int(crop.height * scale))), Image.LANCZOS)
    return crop, True


def _coerce(path: str, text: str | None) -> Any:
    if text is None:
        return None
    leaf = leaf_name(path)
    if leaf in NUMERIC_LEAVES:
        return parse_amount(text)
    if leaf.endswith("date"):
        return parse_date(text) or text.strip()
    return text.strip() or None


def arbitrate(
    doc_type: DocType,
    merged: dict[str, Any],
    vision: dict[str, Any],
    ocr_data: dict[str, Any],
    pages: list[Image.Image],
    ocr: list[OcrPage],
) -> tuple[dict[str, Any], ArbiterResult]:
    paths = disputes(merged, vision, ocr_data)
    if not paths or not pages:
        return merged, ArbiterResult(model=ARBITER_MODEL, disputes=0)
    fv, fo = flatten(vision), flatten(ocr_data)
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"This is a {doc_type.value}. {len(paths)} disputes follow."}
    ]
    cropped: list[bool] = []
    for i, path in enumerate(paths, 1):
        a, b = fv[path], fo[path]
        crop, was_cropped = crop_for([a, b], pages, ocr)
        cropped.append(was_cropped)
        content.append(
            {"type": "text", "text": f"Dispute {i}: field {path}. Candidate a: {a!s}. Candidate b: {b!s}."}
        )
        content.extend(image_blocks([crop], max_side=1400)[1:])
    try:
        out, meta = call_structured(ARBITER_MODEL, SYSTEM, content, _Output, max_tokens=4096, effort="low")
    except Exception as e:  # noqa: BLE001
        return merged, ArbiterResult(
            model=ARBITER_MODEL, disputes=len(paths), error=f"{type(e).__name__}: {e}"
        )
    by_num = {v.get("dispute"): v for v in out.get("verdicts", []) if isinstance(v, dict)}
    flat = flatten(merged)
    verdicts: list[ArbiterVerdict] = []
    for i, path in enumerate(paths, 1):
        v = by_num.get(i)
        if not v or v.get("choice") not in ("a", "b", "other", "unreadable"):
            continue
        choice = {"a": "vision", "b": "ocr", "other": "other", "unreadable": "unreadable"}[v["choice"]]
        value = {
            "vision": fv[path],
            "ocr": fo[path],
            "other": _coerce(path, v.get("value")),
            "unreadable": None,
        }[choice]
        if choice == "other" and value in (None, ""):
            choice, value = "unreadable", None
        elif choice == "other" and agreement(path, value, fv[path]):
            choice, value = "vision", fv[path]
        elif choice == "other" and agreement(path, value, fo[path]):
            choice, value = "ocr", fo[path]
        if choice != "unreadable" and ARBITER_MODE == "override":
            flat[path] = value
        verdicts.append(
            ArbiterVerdict(
                field=path,
                vision_value=fv[path],
                ocr_value=fo[path],
                choice=choice,
                value=value,
                confidence=float(v.get("confidence") or 0.0),
                cropped=cropped[i - 1],
            )
        )
    template = SCHEMAS[doc_type]().model_dump()
    result = ArbiterResult(
        model=meta.get("model"),
        disputes=len(paths),
        verdicts=verdicts,
        latency_s=meta["latency_s"],
        input_tokens=meta["input_tokens"],
        output_tokens=meta["output_tokens"],
    )
    return unflatten(flat, template), result
