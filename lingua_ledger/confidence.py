from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import ARTIFACTS
from .normalize import values_match

LIST_FIELDS = {"line_items", "fields", "parties"}


def flatten(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    for sk, sv in item.items():
                        out[f"{k}[{i}].{sk}"] = sv
                else:
                    out[f"{k}[{i}]"] = item
        else:
            out[k] = v
    return out


def unflatten(flat: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {k: ([] if isinstance(v, list) else None) for k, v in template.items()}
    for path, value in flat.items():
        if "[" not in path:
            out[path] = value
            continue
        name, rest = path.split("[", 1)
        idx, _, sub = rest.partition("]")
        idx = int(idx)
        lst = out.setdefault(name, [])
        while len(lst) <= idx:
            lst.append({} if sub else None)
        if sub:
            lst[idx][sub.lstrip(".")] = value
        else:
            lst[idx] = value
    return out


def leaf_name(path: str) -> str:
    return path.rsplit(".", 1)[-1] if "." in path else path.split("[")[0]


def top_name(path: str) -> str:
    return path.split("[")[0].split(".")[0]


def agreement(path: str, a: Any, b: Any) -> bool | None:
    if a is None and b is None:
        return None
    if a is None or b is None:
        return False
    return values_match(leaf_name(path), a, b)


def raw_score(agree: bool | None, ocr_conf: float | None, validator: str, self_conf: float | None,
              present: bool) -> float:
    if not present:
        return 0.5
    s = 0.55
    if agree is True:
        s += 0.28
    elif agree is False:
        s -= 0.30
    if validator == "pass":
        s += 0.12
    elif validator == "fail":
        s -= 0.35
    if ocr_conf is not None:
        s += (ocr_conf - 0.6) * 0.25
    if self_conf is not None:
        s += (self_conf - 0.7) * 0.25
    return float(min(0.99, max(0.02, s)))


class Calibrator:
    """Isotonic map from raw score to empirical precision, fitted per document type with a global fallback."""

    def __init__(self, curves: dict[str, tuple[list[float], list[float]]] | None = None):
        self.curves = curves or {}

    def __call__(self, raw: float, doc_type: str | None = None) -> float:
        curve = self.curves.get(doc_type or "", None) or self.curves.get("global")
        if not curve:
            return raw
        xs, ys = curve
        return float(np.interp(raw, xs, ys))

    @classmethod
    def fit(cls, rows: list[tuple[str, float, bool]], min_rows: int = 150) -> Calibrator:
        from sklearn.isotonic import IsotonicRegression

        curves: dict[str, tuple[list[float], list[float]]] = {}
        groups: dict[str, list[tuple[float, bool]]] = {"global": []}
        for doc_type, raw, correct in rows:
            groups.setdefault(doc_type, []).append((raw, correct))
            groups["global"].append((raw, correct))
        for name, pairs in groups.items():
            if len(pairs) < min_rows and name != "global":
                continue
            x = np.array([p[0] for p in pairs])
            y = np.array([1.0 if p[1] else 0.0 for p in pairs])
            iso = IsotonicRegression(y_min=0.01, y_max=0.995, out_of_bounds="clip").fit(x, y)
            grid = np.linspace(0.0, 1.0, 41)
            curves[name] = (grid.tolist(), iso.predict(grid).tolist())
        return cls(curves)

    def save(self, path: Path | None = None) -> Path:
        path = path or ARTIFACTS / "calibrator.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.curves))
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> Calibrator:
        path = path or ARTIFACTS / "calibrator.json"
        if path.exists():
            data = json.loads(path.read_text())
            return cls({k: (v[0], v[1]) for k, v in data.items()})
        return cls()
