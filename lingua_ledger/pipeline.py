from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from PIL import Image

from .classify import classify
from .confidence import Calibrator, agreement, flatten, raw_score, top_name, unflatten
from .config import DEFAULT_REVIEW_THRESHOLD
from .extract import extract_text, extract_vision
from .ingest import load_pages
from .ocr import locate_value, ocr_pages, pages_text
from .schemas import (
    SCHEMAS,
    Classification,
    DocType,
    ExtractionResult,
    FieldResult,
    OcrPage,
    PathOutput,
    RuleResult,
)
from .validate import rule_outcome_for_field, validate

_calibrator: Calibrator | None = None


def calibrator() -> Calibrator:
    global _calibrator
    if _calibrator is None:
        _calibrator = Calibrator.load()
    return _calibrator


def reconcile(doc_type: DocType, vision: dict[str, Any], ocr: dict[str, Any]) -> dict[str, Any]:
    """Start from the vision reading, fill gaps from OCR, then swap in OCR values where that fixes a failed rule."""
    fv, fo = flatten(vision), flatten(ocr)
    merged = dict(fv)
    for k, v in fo.items():
        if merged.get(k) is None and v is not None:
            merged[k] = v
    template = SCHEMAS[doc_type]().model_dump()
    rules = validate(doc_type.value, unflatten(merged, template))
    failed_fields = {f for r in rules if r.passed is False for f in r.fields}
    n_fail = sum(1 for r in rules if r.passed is False)
    for k in list(failed_fields):
        if k in fo and fo[k] is not None and not agreement(k, merged.get(k), fo[k]):
            trial = dict(merged)
            trial[k] = fo[k]
            trial_rules = validate(doc_type.value, unflatten(trial, template))
            trial_fail = sum(1 for r in trial_rules if r.passed is False)
            if trial_fail < n_fail:
                merged, n_fail = trial, trial_fail
    return unflatten(merged, template)


def score_fields(doc_type: DocType, merged: dict[str, Any], paths: list[PathOutput], rules: list[RuleResult],
                 ocr: list[OcrPage], threshold: float) -> list[FieldResult]:
    by_path = {p.path: p for p in paths}
    fv = flatten(by_path["vision"].data) if "vision" in by_path else {}
    fo = flatten(by_path["ocr_text"].data) if "ocr_text" in by_path else {}
    self_conf = by_path["vision"].self_confidence if "vision" in by_path else (
        by_path["ocr_text"].self_confidence if "ocr_text" in by_path else {})
    cal = calibrator()
    results: list[FieldResult] = []
    for path, value in flatten(merged).items():
        present = value is not None and value != "" and value != []
        agree = agreement(path, fv.get(path), fo.get(path)) if fv and fo else None
        loc = locate_value(value, ocr) if present and ocr else None
        ocr_conf = loc[0] if loc else None
        outcome = rule_outcome_for_field(rules, path)
        sc = self_conf.get(top_name(path))
        raw = raw_score(agree, ocr_conf, outcome, sc, present)
        conf = cal(raw, doc_type.value) if present else 1.0
        results.append(FieldResult(
            field=path, value=value, confidence=round(conf, 4), raw_score=round(raw, 4), agree=agree,
            ocr_conf=None if ocr_conf is None else round(ocr_conf, 3), validator=outcome, self_conf=sc,
            vision_value=fv.get(path), ocr_value=fo.get(path), bbox=loc[1] if loc else None, page=loc[2] if loc else None,
            needs_review=present and conf < threshold,
        ))
    return results


def run(source: str | Path | bytes, filename: str | None = None, doc_type: DocType | None = None,
        language: str | None = None, threshold: float = DEFAULT_REVIEW_THRESHOLD,
        paths: tuple[str, ...] = ("vision", "ocr_text"), images: list[Image.Image] | None = None,
        doc_id: str | None = None) -> ExtractionResult:
    t0 = time.perf_counter()
    pages = images or load_pages(source, filename)
    ocr: list[OcrPage] = []
    if doc_type is None or language is None:
        cls = classify(pages)
        doc_type = doc_type or cls.doc_type
        language = language or cls.language
    else:
        cls = Classification(doc_type=doc_type, language=language, confidence=1.0)
    ocr = ocr_pages(pages, language)
    text = pages_text(ocr)
    jobs = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        if "vision" in paths:
            jobs["vision"] = ex.submit(extract_vision, pages, doc_type)
        if "ocr_text" in paths:
            jobs["ocr_text"] = ex.submit(extract_text, text, doc_type)
    outputs = [jobs[k].result() for k in ("vision", "ocr_text") if k in jobs]
    by_path = {p.path: p.data for p in outputs}
    if "vision" in by_path and "ocr_text" in by_path:
        merged = reconcile(doc_type, by_path["vision"], by_path["ocr_text"])
    else:
        merged = next(iter(by_path.values()))
    rules = validate(doc_type.value, merged)
    fields = score_fields(doc_type, merged, outputs, rules, ocr, threshold)
    reviewable = [f for f in fields if f.value not in (None, "", [])]
    review_rate = (sum(f.needs_review for f in reviewable) / len(reviewable)) if reviewable else 0.0
    return ExtractionResult(
        doc_id=doc_id or uuid.uuid4().hex[:12], classification=cls, data=merged, fields=fields, rules=rules,
        paths=outputs, review_threshold=threshold, review_rate=round(review_rate, 4), pages=len(pages),
        latency_s=round(time.perf_counter() - t0, 3),
    )
