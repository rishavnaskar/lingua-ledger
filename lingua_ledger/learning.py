"""Refit the confidence calibrator from reviewer decisions.

Base rows come from the benchmark run shipped in artifacts/eval; every reviewer decision adds labelled rows
with a higher weight so a handful of corrections visibly moves the curve. Numbers reported back are on the
benchmark fields plus the corrections, scored by the refit calibrator.
"""

from __future__ import annotations

import itertools
from functools import lru_cache
from typing import Any

import numpy as np

from .confidence import Calibrator
from .config import ARTIFACTS, CORRECTION_WEIGHT
from .memory import Correction, load_json

Row = tuple[str, float, bool]


@lru_cache(maxsize=1)
def base_rows() -> tuple[Row, ...]:
    from .eval.metrics import label_fields

    rows: list[Row] = []
    for path in sorted((ARTIFACTS / "eval").glob("*.jsonl")):
        for r in load_json(path):
            if "error" in r or not r.get("fields"):
                continue
            fields = r.get("fields_arbiter") or r["fields"]
            labels = label_fields(r.get("pred_arbiter") or r["pred"], r["gold"])
            for f in fields:
                if f["value"] in (None, "", []) or f["field"] not in labels:
                    continue
                rows.append((r["doc_type"], float(f["raw_score"]), bool(labels[f["field"]])))
    return tuple(rows)


def correction_rows(items: list[Correction]) -> list[Row]:
    return [
        (c.doc_type, float(c.raw_score), bool(c.accepted)) for c in items for _ in range(CORRECTION_WEIGHT)
    ]


def refit(items: list[Correction]) -> Calibrator:
    rows = list(base_rows()) + correction_rows(items)
    return Calibrator.fit(rows) if len(rows) >= 50 else Calibrator.load()


def operating_points(
    cal: Calibrator, rows: list[Row], targets: tuple[float, ...] = (0.95, 0.98)
) -> dict[str, Any]:
    if not rows:
        return {}
    conf = np.array([cal(s, d) for d, s, _ in rows])
    correct = np.array([1.0 if c else 0.0 for _, _, c in rows])
    grid = np.linspace(0, 1, 101)
    review = np.array([1 - (conf >= t).mean() for t in grid])
    acc = np.array([correct[conf >= t].mean() if (conf >= t).any() else 1.0 for t in grid])
    out: dict[str, Any] = {"fields": len(rows)}
    for target in targets:
        ok = np.where(acc >= target)[0]
        out[f"review_rate_at_{int(target * 100)}"] = round(float(review[ok].min()), 4) if ok.size else None
    out["ece"] = round(_ece(conf, correct), 4)
    return out


def _ece(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in itertools.pairwise(edges):
        m = (conf >= lo) & (conf <= hi) if lo == 0 else (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(total)


def curve(cal: Calibrator, doc_type: str, points: int = 21) -> list[list[float]]:
    xs = np.linspace(0, 1, points)
    return [[round(float(x), 3), round(cal(float(x), doc_type), 4)] for x in xs]


def learning_state(items: list[Correction], doc_type: str | None = None) -> dict[str, Any]:
    before = Calibrator.load()
    after = refit(items) if items else before
    rows = list(base_rows()) + [(c.doc_type, float(c.raw_score), bool(c.accepted)) for c in items]
    kind = doc_type or (items[-1].doc_type if items else "invoice")
    return {
        "corrections": len(items),
        "fields_fixed": sum(1 for c in items if not c.accepted),
        "weight": CORRECTION_WEIGHT,
        "doc_type": kind,
        "before": operating_points(before, rows),
        "after": operating_points(after, rows),
        "curve_before": curve(before, kind),
        "curve_after": curve(after, kind),
    }
