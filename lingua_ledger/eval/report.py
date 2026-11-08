from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import itertools

import matplotlib.pyplot as plt
import numpy as np

from ..confidence import Calibrator
from ..config import ARTIFACTS
from .metrics import Counts, label_fields

RESULTS_DIR = ARTIFACTS / "eval"
INK, MUTED, GRID = "#121A2B", "#4A5568", "#D5DCE4"
TEAL, NAVY, AMBER = "#0F8B8D", "#1F3A5F", "#E8A33D"
PRICE_IN = float(os.getenv("LL_PRICE_IN_PER_M", "2.0"))
PRICE_OUT = float(os.getenv("LL_PRICE_OUT_PER_M", "10.0"))


def _records() -> list[dict]:
    rows = []
    for path in sorted(RESULTS_DIR.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                r["_file"] = path.name
                rows.append(r)
    return rows


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def _ece(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in itertools.pairwise(edges):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(ece)


def build_report(threshold: float = 0.85, targets: tuple[float, ...] = (0.95, 0.98)) -> dict:
    rows = [r for r in _records() if "error" not in r]
    errors = [r for r in _records() if "error" in r]
    ARTIFACTS.mkdir(exist_ok=True)
    summary: dict = {"documents": len(rows), "failed_documents": len(errors)}

    # Field-level F1 per dataset/language and per path.
    agg: dict[tuple[str, str, str], Counts] = defaultdict(Counts)
    for r in rows:
        for path, sc in r["scores"].items():
            c = Counts(tp=sc["tp"], fp=sc["fp"], fn=sc["fn"])
            agg[(r["dataset"], r["language"], path)].add(c)
            agg[(r["dataset"], "all", path)].add(c)
            agg[("all", "all", path)].add(c)
    table = [{"dataset": d, "language": lang, "path": p, **c.as_dict()} for (d, lang, p), c in sorted(agg.items())]
    with (ARTIFACTS / "f1_table.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0].keys()) if table else ["dataset"])
        w.writeheader()
        w.writerows(table)
    summary["f1"] = {f"{d}/{lang}/{p}": c.as_dict()["f1"] for (d, lang, p), c in sorted(agg.items())}

    # Classification accuracy.
    cls = [r for r in rows if r.get("classification")]
    if cls:
        summary["classification"] = {
            "n": len(cls),
            "doc_type_acc": round(np.mean([r["classification"]["doc_type"] == r["doc_type"] for r in cls]), 4),
            "language_acc": round(np.mean([r["classification"]["language"] == r["language"] for r in cls]), 4),
        }

    # Calibration on field-level correctness, fit on even-hash docs, evaluate on odd-hash docs.
    fit_rows, test_rows = [], []
    for r in rows:
        if not r.get("fields"):
            continue
        labels = label_fields(r["pred"], r["gold"])
        bucket = fit_rows if (hash(r["doc_id"]) % 2 == 0) else test_rows
        for f in r["fields"]:
            if f["value"] in (None, "", []) or f["field"] not in labels:
                continue
            bucket.append((r["doc_type"], float(f["raw_score"]), bool(labels[f["field"]]), r["dataset"]))
    cal = Calibrator.fit([(d, s, c) for d, s, c, _ in fit_rows]) if len(fit_rows) >= 50 else Calibrator()
    cal.save()
    if test_rows:
        raw = np.array([s for _, s, _, _ in test_rows])
        correct = np.array([c for _, _, c, _ in test_rows], dtype=float)
        calibrated = np.array([cal(s, d) for d, s, _, _ in test_rows])
        summary["calibration"] = {
            "fit_fields": len(fit_rows), "test_fields": len(test_rows),
            "field_accuracy": round(float(correct.mean()), 4),
            "ece_raw": round(_ece(raw, correct), 4), "ece_calibrated": round(_ece(calibrated, correct), 4),
            "brier_raw": round(float(np.mean((raw - correct) ** 2)), 4),
            "brier_calibrated": round(float(np.mean((calibrated - correct) ** 2)), 4),
        }
        _reliability_chart(raw, calibrated, correct)
        summary["review"] = _review_curve(calibrated, correct, threshold, targets)
        summary["signals"] = _signal_breakdown(rows)

    # Latency and tokens.
    lat = [r["latency_s"] for r in rows if "latency_s" in r]
    toks_in = sum(p.get("input_tokens", 0) for r in rows for p in r.get("paths", []))
    toks_out = sum(p.get("output_tokens", 0) for r in rows for p in r.get("paths", []))
    summary["latency_s"] = {"p50": round(float(np.percentile(lat, 50)), 2), "p95": round(float(np.percentile(lat, 95)), 2)} if lat else {}
    summary["tokens"] = {"input": toks_in, "output": toks_out, "per_doc_input": round(toks_in / max(1, len(rows))),
                         "per_doc_output": round(toks_out / max(1, len(rows)))}
    if PRICE_IN and PRICE_OUT:
        cost = (toks_in * PRICE_IN + toks_out * PRICE_OUT) / 1e6
        summary["cost_usd"] = {"total": round(cost, 2), "per_1000_docs": round(cost / max(1, len(rows)) * 1000, 2)}

    _f1_charts(agg)
    (ARTIFACTS / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def _signal_breakdown(rows: list[dict]) -> dict:
    out: dict[str, dict] = {}
    groups: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        labels = label_fields(r["pred"], r["gold"])
        for f in r["fields"]:
            if f["field"] not in labels or f["value"] in (None, "", []):
                continue
            ok = labels[f["field"]]
            groups[f"agree={f['agree']}"].append(ok)
            groups[f"validator={f['validator']}"].append(ok)
    for k, v in sorted(groups.items()):
        out[k] = {"n": len(v), "accuracy": round(float(np.mean(v)), 4)}
    return out


def _review_curve(conf: np.ndarray, correct: np.ndarray, threshold: float, targets: tuple[float, ...]) -> dict:
    grid = np.linspace(0, 1, 101)
    review, acc = [], []
    for t in grid:
        auto = conf >= t
        review.append(1 - auto.mean())
        acc.append(correct[auto].mean() if auto.any() else 1.0)
    review, acc = np.array(review), np.array(acc)
    res = {"baseline_accuracy_no_review": round(float(correct.mean()), 4)}
    for target in targets:
        ok = np.where(acc >= target)[0]
        if ok.size:
            i = ok[np.argmin(review[ok])]
            res[f"review_rate_at_{int(target * 100)}pct_accuracy"] = round(float(review[i]), 4)
            res[f"threshold_at_{int(target * 100)}pct_accuracy"] = round(float(grid[i]), 2)
    auto = conf >= threshold
    res[f"at_threshold_{threshold}"] = {"review_rate": round(float(1 - auto.mean()), 4),
                                        "auto_accuracy": round(float(correct[auto].mean()) if auto.any() else 1.0, 4)}
    fig, ax = plt.subplots(figsize=(6, 3.6), dpi=160)
    ax.plot(review * 100, acc * 100, color=TEAL, linewidth=2)
    ax.axhline(correct.mean() * 100, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(1, correct.mean() * 100 + 0.4, "no review", color=MUTED, fontsize=8)
    for target in targets:
        key = f"review_rate_at_{int(target * 100)}pct_accuracy"
        if key in res:
            x = res[key] * 100
            ax.plot([x], [target * 100], marker="o", color=AMBER, markersize=7)
            ax.annotate(f"{target:.0%} accuracy at {x:.0f}% reviewed", (x, target * 100), xytext=(8, -12),
                        textcoords="offset points", fontsize=8, color=INK)
    ax.set_xlabel("Fields sent to human review (%)")
    ax.set_ylabel("Accuracy of auto-accepted fields (%)")
    ax.set_title("Review load versus accuracy of what posts automatically", fontsize=10, loc="left")
    ax.set_xlim(0, 100)
    _style(ax)
    fig.tight_layout()
    fig.savefig(ARTIFACTS / "review_curve.png")
    plt.close(fig)
    return res


def _reliability_chart(raw: np.ndarray, calibrated: np.ndarray, correct: np.ndarray) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), dpi=160, sharey=True)
    for ax, conf, name in ((axes[0], raw, "Raw score"), (axes[1], calibrated, "Calibrated confidence")):
        edges = np.linspace(0, 1, 11)
        xs, ys, ns = [], [], []
        for lo, hi in itertools.pairwise(edges):
            m = (conf >= lo) & (conf < hi) if hi < 1 else (conf >= lo) & (conf <= hi)
            if m.sum() >= 5:
                xs.append(conf[m].mean())
                ys.append(correct[m].mean())
                ns.append(int(m.sum()))
        ax.plot([0, 1], [0, 1], color=GRID, linewidth=1)
        ax.plot(xs, ys, color=TEAL, linewidth=2, marker="o", markersize=5)
        ax.set_title(f"{name}  (ECE {_ece(conf, correct):.3f})", fontsize=10, loc="left")
        ax.set_xlabel("Predicted confidence")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        _style(ax)
    axes[0].set_ylabel("Observed share correct")
    fig.tight_layout()
    fig.savefig(ARTIFACTS / "reliability.png")
    plt.close(fig)


def _f1_charts(agg: dict[tuple[str, str, str], Counts]) -> None:
    langs = [(lang, c.f1) for (d, lang, p), c in agg.items() if d == "xfund" and lang != "all" and p == "merged"]
    funsd = [c.f1 for (d, lang, p), c in agg.items() if d == "funsd" and lang == "all" and p == "merged"]
    if funsd:
        langs.append(("en", funsd[0]))
    if langs:
        langs.sort(key=lambda x: -x[1])
        fig, ax = plt.subplots(figsize=(6, 3.2), dpi=160)
        names = [x[0].upper() for x in langs]
        vals = [x[1] * 100 for x in langs]
        bars = ax.bar(names, vals, color=TEAL, width=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}", ha="center", fontsize=8, color=INK)
        ax.set_ylim(0, 105)
        ax.set_ylabel("Key-value F1 (%)")
        ax.set_title("Form extraction F1 by language (XFUND, FUNSD)", fontsize=10, loc="left")
        _style(ax)
        fig.tight_layout()
        fig.savefig(ARTIFACTS / "f1_by_language.png")
        plt.close(fig)

    datasets = sorted({d for (d, lang, p) in agg if d != "all"})
    paths = [p for p in ("vision", "ocr_text", "merged") if any((d, "all", p) in agg for d in datasets)]
    if datasets and len(paths) > 1:
        fig, ax = plt.subplots(figsize=(7, 3.4), dpi=160)
        width = 0.8 / len(paths)
        colors = {"vision": NAVY, "ocr_text": AMBER, "merged": TEAL}
        labels = {"vision": "Vision reader", "ocr_text": "OCR + text reader", "merged": "Both + validators"}
        x = np.arange(len(datasets))
        for i, p in enumerate(paths):
            vals = [agg[(d, "all", p)].f1 * 100 if (d, "all", p) in agg else 0 for d in datasets]
            ax.bar(x + (i - (len(paths) - 1) / 2) * width, vals, width=width * 0.92, color=colors[p], label=labels[p])
        ax.set_xticks(x)
        ax.set_xticklabels([d.replace("_", " ") for d in datasets])
        ax.set_ylim(0, 105)
        ax.set_ylabel("Field F1 (%)")
        ax.set_title("Ablation: each reader alone versus the full pipeline", fontsize=10, loc="left")
        ax.legend(frameon=False, fontsize=8, loc="lower right")
        _style(ax)
        fig.tight_layout()
        fig.savefig(ARTIFACTS / "ablation.png")
        plt.close(fig)
