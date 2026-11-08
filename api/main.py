from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from lingua_ledger.config import ARTIFACTS, DEFAULT_REVIEW_THRESHOLD, ROOT
from lingua_ledger.ingest import load_pages, to_png_bytes
from lingua_ledger.pipeline import run
from lingua_ledger.schemas import DocType

SAMPLES_DIR = ROOT / "samples"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

app = FastAPI(title="Lingua Ledger API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _page_payload(images) -> list[dict]:
    return [{"index": i, "width": im.width, "height": im.height,
             "data_url": "data:image/png;base64," + base64.b64encode(to_png_bytes(im)).decode()}
            for i, im in enumerate(images)]


def _extract(data: bytes, filename: str, doc_type: str | None, language: str | None, threshold: float,
             paths: str) -> dict:
    images = load_pages(data, filename)
    result = run(data, filename=filename, doc_type=DocType(doc_type) if doc_type else None, language=language,
                 threshold=threshold, paths=tuple(p for p in paths.split(",") if p), images=images)
    payload = result.model_dump()
    payload["pages_preview"] = _page_payload(images)
    payload["filename"] = filename
    return payload


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/extract")
async def extract(file: UploadFile = File(...),  # noqa: B008
                  doc_type: str | None = Form(None), language: str | None = Form(None),
                  threshold: float = Form(DEFAULT_REVIEW_THRESHOLD), paths: str = Form("vision,ocr_text")) -> JSONResponse:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large")
    try:
        return JSONResponse(_extract(data, file.filename or "upload", doc_type, language, threshold, paths))
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
def extract_sample(sample_id: str, threshold: float = DEFAULT_REVIEW_THRESHOLD, paths: str = "vision,ocr_text") -> dict:
    path = _sample_path(sample_id)
    meta = next(s for s in samples() if s["id"] == sample_id)
    return _extract(path.read_bytes(), path.name, meta.get("doc_type"), meta.get("language"), threshold, paths)


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
