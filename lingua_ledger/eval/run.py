from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image
from tqdm import tqdm

from ..classify import classify
from ..config import ARTIFACTS, DATA_PROCESSED
from ..ingest import load_pages
from ..pipeline import run
from ..schemas import DocType
from .datasets import DATASETS, load
from .metrics import score_document

RESULTS_DIR = ARTIFACTS / "eval"
ALL_DATASETS = [*DATASETS, "synth_invoices"]


def _load_samples(name: str):
    if name == "synth_invoices":
        path = DATA_PROCESSED / "synth_invoices" / "samples.jsonl"
        from .datasets import Sample

        return [Sample.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]
    return load(name)


def _images(sample) -> list[Image.Image]:
    if sample.image_paths:
        return [Image.open(p).convert("RGB") for p in sample.image_paths[:4]]
    if sample.pdf_path:
        return load_pages(sample.pdf_path)
    return []


def _process(sample, paths: tuple[str, ...], classify_too: bool) -> dict:
    t0 = time.perf_counter()
    images = _images(sample)
    doc_type = DocType(sample.doc_type)
    record: dict = {"doc_id": sample.doc_id, "dataset": sample.dataset, "language": sample.language,
                    "doc_type": sample.doc_type, "gold": sample.gold}
    try:
        if images:
            result = run(b"", filename=None, doc_type=doc_type, language=sample.language, paths=paths,
                         images=images, doc_id=sample.doc_id)
        else:
            from ..extract import extract_text
            from ..validate import validate

            out = extract_text(sample.text or "", doc_type)
            record.update({"text_only": True, "pred": out.data, "paths": [out.model_dump()],
                           "rules": [r.model_dump() for r in validate(doc_type.value, out.data)], "fields": []})
            record["scores"] = {"merged": score_document(out.data, sample.gold).counts.as_dict()}
            record["latency_s"] = round(time.perf_counter() - t0, 3)
            return record
        record.update({
            "pred": result.data,
            "fields": [f.model_dump() for f in result.fields],
            "rules": [r.model_dump() for r in result.rules],
            "paths": [p.model_dump() for p in result.paths],
            "review_rate": result.review_rate,
            "pages": result.pages,
        })
        scores = {"merged": score_document(result.data, sample.gold).counts.as_dict()}
        for p in result.paths:
            scores[p.path] = score_document(p.data, sample.gold).counts.as_dict()
        record["scores"] = scores
        if classify_too:
            cls = classify(images[:1])
            record["classification"] = cls.model_dump()
    except Exception as e:  # noqa: BLE001
        record["error"] = f"{type(e).__name__}: {e}"
    record["latency_s"] = round(time.perf_counter() - t0, 3)
    return record


def run_eval(datasets: str = "all", limit: int | None = None, paths: tuple[str, ...] = ("vision", "ocr_text"),
             workers: int = 4, resume: bool = True, classify_too: bool = True) -> Path:
    names = ALL_DATASETS if datasets == "all" else [d.strip() for d in datasets.split(",")]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tag = "+".join(paths)
    for name in names:
        samples = _load_samples(name)
        if limit:
            samples = _spread(samples, limit)
        out_path = RESULTS_DIR / f"{name}.{tag}.jsonl"
        done: set[str] = set()
        if resume and out_path.exists():
            for line in out_path.read_text().splitlines():
                if line.strip():
                    done.add(json.loads(line)["doc_id"])
        todo = [s for s in samples if s.doc_id not in done]
        with out_path.open("a") as fh, ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_process, s, paths, classify_too) for s in todo]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"{name} [{tag}]"):
                fh.write(json.dumps(fut.result(), default=str) + "\n")
                fh.flush()
    return RESULTS_DIR


def _spread(samples, limit: int):
    by_lang: dict[str, list] = {}
    for s in samples:
        by_lang.setdefault(s.language, []).append(s)
    per = max(1, limit // max(1, len(by_lang)))
    out = []
    for lang in sorted(by_lang):
        out.extend(by_lang[lang][:per])
    return out[:limit] if len(by_lang) == 1 else out
