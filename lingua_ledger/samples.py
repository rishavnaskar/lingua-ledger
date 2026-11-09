"""Bundled sample documents and their precomputed extraction results."""

from __future__ import annotations

import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from .config import ROOT
from .schemas import DocType, ExtractionResult

SAMPLES_DIR = ROOT / "samples"
CACHE_DIR = SAMPLES_DIR / "cache"


def index() -> list[dict]:
    path = SAMPLES_DIR / "index.json"
    return json.loads(path.read_text()) if path.exists() else []


def load_cached(sample_id: str) -> ExtractionResult | None:
    path = CACHE_DIR / f"{sample_id}.json"
    if not path.exists():
        return None
    try:
        return ExtractionResult.model_validate_json(path.read_text())
    except ValueError:
        return None


def cached_at(sample_id: str) -> str | None:
    path = CACHE_DIR / f"{sample_id}.json"
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).strftime("%Y-%m-%d")


def _build_one(meta: dict) -> str:
    from .pipeline import run

    path = SAMPLES_DIR / meta["file"]
    doc_type = DocType(meta["doc_type"]) if meta.get("doc_type") else None
    result = run(path, doc_type=doc_type, language=meta.get("language"), doc_id=meta["id"])
    if any(p.error for p in result.paths):
        raise RuntimeError("; ".join(p.error for p in result.paths if p.error))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{meta['id']}.json").write_text(result.model_dump_json(indent=1))
    return f"{len(result.fields)} fields, {result.latency_s:.1f} s"


def build_cache(ids: list[str] | None = None, workers: int = 2) -> Iterator[tuple[str, str]]:
    metas = [m for m in index() if ids is None or m["id"] in ids]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_build_one, m): m["id"] for m in metas}
        for fut in as_completed(futures):
            try:
                yield futures[fut], fut.result()
            except Exception as e:  # noqa: BLE001
                yield futures[fut], f"failed: {type(e).__name__}: {e}"
