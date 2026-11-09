"""Run the arbiter over an existing evaluation run without repeating the two reader calls.

Each record keeps its original reader outputs; this adds pred_arbiter, fields_arbiter, scores["arbiter"] and
the arbiter metadata, so the report can show the pipeline with and without the focused second look.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

from ..arbiter import arbitrate
from ..confidence import flatten, unflatten
from ..config import ARBITER_MODE
from ..ocr import ocr_pages
from ..pipeline import reconcile, score_fields
from ..schemas import SCHEMAS, ArbiterResult, DocType, PathOutput
from ..validate import validate
from .metrics import score_document
from .run import ALL_DATASETS, RESULTS_DIR, _images, _load_samples, restrict


def _arbitrate_record(record: dict, sample, rescore: bool = False) -> dict:
    images = _images(sample)
    doc_type = DocType(record["doc_type"])
    paths = [PathOutput.model_validate(p) for p in record["paths"]]
    by_path = {p.path: p.data for p in paths}
    if "vision" not in by_path or "ocr_text" not in by_path or not images:
        return record
    ocr = ocr_pages(images, record["language"])
    threshold = record.get("review_threshold", 0.85)
    base = reconcile(doc_type, by_path["vision"], by_path["ocr_text"])
    if rescore and record.get("arbiter"):
        result = ArbiterResult.model_validate(record["arbiter"])
    else:
        _, result = arbitrate(doc_type, base, by_path["vision"], by_path["ocr_text"], images, ocr)
    if result.error:
        raise RuntimeError(result.error)
    flat = flatten(base)
    for v in result.verdicts:
        if v.choice != "unreadable":
            flat[v.field] = v.value
    override = unflatten(flat, SCHEMAS[doc_type]().model_dump())
    merged = override if ARBITER_MODE == "override" else base
    rules = validate(doc_type.value, merged)
    base_rules = validate(doc_type.value, base)
    # Base pipeline, rescored with the current code so both columns come from the same revision.
    record["pred"] = restrict(base, record["dataset"])
    record["pred_full"] = base
    record["rules"] = [r.model_dump() for r in base_rules]
    record["fields"] = [
        f.model_dump() for f in score_fields(doc_type, base, paths, base_rules, ocr, threshold)
    ]
    record["scores"]["merged"] = score_document(record["pred"], record["gold"]).counts.as_dict()
    # With the arbiter: verdicts as a signal (default) or also as values (override mode).
    record["arbiter"] = result.model_dump()
    record["pred_arbiter"] = restrict(merged, record["dataset"])
    record["pred_override"] = restrict(override, record["dataset"])
    record["fields_arbiter"] = [
        f.model_dump() for f in score_fields(doc_type, merged, paths, rules, ocr, threshold, result)
    ]
    record["rules_arbiter"] = [r.model_dump() for r in rules]
    record["scores"].pop("arbiter", None)
    if ARBITER_MODE == "override":
        record["scores"]["arbiter"] = score_document(record["pred_arbiter"], record["gold"]).counts.as_dict()
    return record


def run_arbiter(
    datasets: str = "all", workers: int = 2, limit: int | None = None, rescore: bool = False
) -> Path:
    names = ALL_DATASETS if datasets == "all" else [d.strip() for d in datasets.split(",")]
    for name in names:
        path = RESULTS_DIR / f"{name}.vision+ocr_text.jsonl"
        if not path.exists():
            continue
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        samples = {s.doc_id: s for s in _load_samples(name)}
        todo = [
            i
            for i, r in enumerate(records)
            if "error" not in r
            and (rescore or "arbiter" not in r)
            and r.get("fields")
            and r["doc_id"] in samples
        ]
        if limit:
            todo = todo[:limit]
        failures = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {
                ex.submit(_arbitrate_record, records[i], samples[records[i]["doc_id"]], rescore): i
                for i in todo
            }
            for fut in tqdm(as_completed(futures), total=len(futures), desc=f"{name} [arbiter]"):
                i = futures[fut]
                try:
                    records[i] = fut.result()
                except Exception as e:  # noqa: BLE001
                    failures += 1
                    tqdm.write(f"{records[i]['doc_id']}: {type(e).__name__}: {e}")
                path.write_text("".join(json.dumps(r, default=str) + "\n" for r in records))
        if failures:
            tqdm.write(f"{name}: {failures} documents left without an arbiter pass; rerun to resume")
    return RESULTS_DIR
