from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..confidence import flatten
from ..normalize import normalize_text, text_match, values_match

PAIR_FIELDS = {
    "fields": ("key", "value"),
    "line_items": ("description", "total"),
}


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: Counts) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class DocScore:
    counts: Counts
    per_field: dict[str, Counts]
    correct_paths: dict[str, bool] = field(default_factory=dict)


def _present(v: Any) -> bool:
    return v is not None and v != "" and v != []


def _match_pairs(name: str, pred: list[dict], gold: list[dict]) -> tuple[Counts, dict[int, int]]:
    a, b = PAIR_FIELDS[name]
    used: set[int] = set()
    mapping: dict[int, int] = {}
    for i, p in enumerate(pred):
        best, best_j = 0.0, None
        for j, g in enumerate(gold):
            if j in used:
                continue
            ka = text_match(str(p.get(a) or ""), str(g.get(a) or ""))
            if ka < 0.75:
                continue
            vb = (
                1.0
                if values_match(b, p.get(b), g.get(b))
                else text_match(str(p.get(b) or ""), str(g.get(b) or ""))
            )
            score = ka * 0.5 + vb * 0.5
            if score > best:
                best, best_j = score, j
        if best_j is not None and best >= 0.85:
            used.add(best_j)
            mapping[i] = best_j
    tp = len(mapping)
    return Counts(tp=tp, fp=len(pred) - tp, fn=len(gold) - tp), mapping


def _match_strings(pred: list[str], gold: list[str]) -> tuple[Counts, dict[int, int]]:
    used: set[int] = set()
    mapping: dict[int, int] = {}
    for i, p in enumerate(pred):
        for j, g in enumerate(gold):
            if j not in used and (normalize_text(p) == normalize_text(g) or text_match(p, g) >= 0.85):
                used.add(j)
                mapping[i] = j
                break
    tp = len(mapping)
    return Counts(tp=tp, fp=len(pred) - tp, fn=len(gold) - tp), mapping


def score_document(pred: dict[str, Any], gold: dict[str, Any]) -> DocScore:
    total = Counts()
    per_field: dict[str, Counts] = {}
    correct: dict[str, bool] = {}
    for key, gv in gold.items():
        pv = pred.get(key)
        if isinstance(gv, list) or isinstance(pv, list):
            gv, pv = gv or [], pv or []
            if key in PAIR_FIELDS:
                c, mapping = _match_pairs(key, pv, gv)
                a, _b = PAIR_FIELDS[key]
                for i, item in enumerate(pv):
                    j = mapping.get(i)
                    for sub, sv in item.items():
                        if not _present(sv):
                            continue
                        if j is not None and sub != a and not _present(gv[j].get(sub)):
                            continue
                        ok = j is not None and (
                            sub in (a,)
                            or values_match(sub, sv, gv[j].get(sub))
                            or text_match(str(sv), str(gv[j].get(sub) or "")) >= 0.85
                        )
                        correct[f"{key}[{i}].{sub}"] = bool(ok)
            else:
                c, mapping = _match_strings([str(x) for x in pv], [str(x) for x in gv])
                for i in range(len(pv)):
                    correct[f"{key}[{i}]"] = i in mapping
            per_field[key] = c
            total.add(c)
            continue
        c = Counts()
        if _present(pv) and _present(gv):
            if values_match(key, pv, gv):
                c.tp += 1
                correct[key] = True
            else:
                c.fp += 1
                c.fn += 1
                correct[key] = False
        elif _present(pv):
            c.fp += 1
            correct[key] = False
        elif _present(gv):
            c.fn += 1
        per_field[key] = c
        total.add(c)
    for key, pv in pred.items():
        if key not in gold and _present(pv) and not isinstance(pv, list):
            total.fp += 1
            correct[key] = False
    return DocScore(counts=total, per_field=per_field, correct_paths=correct)


def label_fields(pred: dict[str, Any], gold: dict[str, Any]) -> dict[str, bool]:
    return score_document(pred, gold).correct_paths


def flatten_present(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in flatten(data).items() if _present(v)}
