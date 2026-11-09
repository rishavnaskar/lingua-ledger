from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from lingua_ledger.config import (
    ARBITER_ENABLED,
    ARBITER_MODEL,
    ARTIFACTS,
    CLASSIFY_MODEL,
    DEFAULT_REVIEW_THRESHOLD,
    PROVIDER,
    ROOT,
    TEXT_MODEL,
    VISION_MODEL,
)
from lingua_ledger.ingest import load_pages, to_png_bytes
from lingua_ledger.learning import learning_state, refit
from lingua_ledger.llm import has_api_key
from lingua_ledger.memory import Correction, store
from lingua_ledger.pipeline import run, set_calibrator
from lingua_ledger.schemas import DocType

SAMPLES_DIR = ROOT / "samples"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

app = FastAPI(title="Lingua Ledger API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _page_payload(images) -> list[dict]:
    return [
        {
            "index": i,
            "width": im.width,
            "height": im.height,
            "data_url": "data:image/png;base64," + base64.b64encode(to_png_bytes(im)).decode(),
        }
        for i, im in enumerate(images)
    ]


def _extract(
    data: bytes,
    filename: str,
    doc_type: str | None,
    language: str | None,
    threshold: float,
    paths: str,
    arbiter: bool | None = None,
) -> dict:
    images = load_pages(data, filename)
    result = run(
        data,
        filename=filename,
        doc_type=DocType(doc_type) if doc_type else None,
        language=language,
        threshold=threshold,
        paths=tuple(p for p in paths.split(",") if p),
        images=images,
        arbiter=arbiter,
        vendor=None,
    )
    vendor = store().vendor_for(result.data)
    if vendor is not None or result.classification.doc_type in (DocType.invoice, DocType.receipt):
        from lingua_ledger.anomaly import detect

        result.anomalies = detect(
            result.classification.doc_type, result.data, result.classification.language, vendor
        )
        result.memory = {"vendor_seen": bool(vendor), "vendor_documents": (vendor or {}).get("documents", 0)}
    payload = result.model_dump()
    payload["pages_preview"] = _page_payload(images)
    payload["filename"] = filename
    return payload


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "provider": PROVIDER,
        "vision_model": VISION_MODEL,
        "text_model": TEXT_MODEL,
        "classify_model": CLASSIFY_MODEL,
        "arbiter_model": ARBITER_MODEL if ARBITER_ENABLED else None,
        "has_key": has_api_key(),
        "memory": store().summary(),
    }


@app.post("/extract")
async def extract(
    file: UploadFile = File(...),  # noqa: B008
    doc_type: str | None = Form(None),
    language: str | None = Form(None),
    threshold: float = Form(DEFAULT_REVIEW_THRESHOLD),
    paths: str = Form("vision,ocr_text"),
    arbiter: bool | None = Form(None),
) -> JSONResponse:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large")
    try:
        return JSONResponse(
            _extract(data, file.filename or "upload", doc_type, language, threshold, paths, arbiter)
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/samples")
def samples() -> list[dict]:
    index = SAMPLES_DIR / "index.json"
    if not index.exists():
        return []
    return json.loads(index.read_text())


@app.get("/samples/{sample_id}/file")
def sample_file(sample_id: str) -> FileResponse:
    path = _sample_path(sample_id)
    return FileResponse(path)


@app.post("/samples/{sample_id}/extract")
def extract_sample(
    sample_id: str,
    threshold: float = DEFAULT_REVIEW_THRESHOLD,
    paths: str = "vision,ocr_text",
    arbiter: bool | None = None,
) -> dict:
    path = _sample_path(sample_id)
    meta = next(s for s in samples() if s["id"] == sample_id)
    return _extract(
        path.read_bytes(), path.name, meta.get("doc_type"), meta.get("language"), threshold, paths, arbiter
    )


class Decision(BaseModel):
    field: str
    raw_score: float
    accepted: bool
    value: Any = None
    corrected_value: Any = None


class ReviewRequest(BaseModel):
    doc_id: str
    doc_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    decisions: list[Decision] = Field(default_factory=list)
    post: bool = True


@app.post("/review")
def review(req: ReviewRequest) -> dict:
    st = store()
    items = [
        Correction(
            doc_id=req.doc_id,
            doc_type=req.doc_type,
            field=d.field,
            raw_score=d.raw_score,
            accepted=d.accepted,
            value=d.value,
            corrected_value=d.corrected_value,
        )
        for d in req.decisions
    ]
    if items:
        st.add_corrections(items)
    if req.post:
        st.remember(req.doc_id, req.doc_type, req.data)
    state = learning_state(st.state.corrections, req.doc_type)
    set_calibrator(refit(st.state.corrections) if st.state.corrections else None)
    return {**state, "memory": st.summary()}


@app.get("/learning")
def learning(doc_type: str | None = None) -> dict:
    st = store()
    return {**learning_state(st.state.corrections, doc_type), "memory": st.summary()}


@app.post("/learning/reset")
def learning_reset() -> dict:
    st = store()
    st.reset()
    set_calibrator(None)
    return {**learning_state([], None), "memory": st.summary()}


@app.get("/metrics")
def metrics() -> dict:
    summary = ARTIFACTS / "summary.json"
    if not summary.exists():
        return {}
    return json.loads(summary.read_text())


@app.get("/metrics/charts/{name}")
def chart(name: str) -> FileResponse:
    if name not in {"review_curve", "reliability", "f1_by_language", "ablation"}:
        raise HTTPException(404)
    path = ARTIFACTS / f"{name}.png"
    if not path.exists():
        raise HTTPException(404)
    return FileResponse(path)


def _sample_path(sample_id: str) -> Path:
    meta = next((s for s in samples() if s["id"] == sample_id), None)
    if not meta:
        raise HTTPException(404, "unknown sample")
    path = (SAMPLES_DIR / meta["file"]).resolve()
    if SAMPLES_DIR.resolve() not in path.parents or not path.exists():
        raise HTTPException(404, "unknown sample")
    return path
