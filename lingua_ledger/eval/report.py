from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import itertools

import matplotlib.pyplot as plt
import numpy as np

from ..confidence import Calibrator
from ..config import ARTIFACTS
from .metrics import Counts, label_fields, label_for_calibration, score_form_lenient

RESULTS_DIR = ARTIFACTS / "eval"
INK, MUTED, GRID = "#121A2B", "#4A5568", "#D5DCE4"
TEAL, NAVY, AMBER = "#0F8B8D", "#1F3A5F", "#E8A33D"
from ..config import PRICE_IN_PER_M as PRICE_IN
from ..config import PRICE_OUT_PER_M as PRICE_OUT


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


def _stable_hash(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest(), 16)


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
        scores = dict(r["scores"])
        if isinstance(r["gold"].get("fields"), list):
            scores["lenient"] = score_form_lenient(r["pred"], r["gold"]).as_dict()
        for path, sc in scores.items():
            c = Counts(tp=sc["tp"], fp=sc["fp"], fn=sc["fn"])
            agg[(r["dataset"], r["language"], path)].add(c)
            agg[(r["dataset"], "all", path)].add(c)
            if path != "lenient":
                agg[("all", "all", path)].add(c)
    table = [
        {"dataset": d, "language": lang, "path": p, **c.as_dict()} for (d, lang, p), c in sorted(agg.items())
    ]
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
            "doc_type_acc": round(
                np.mean([r["classification"]["doc_type"] == r["doc_type"] for r in cls]), 4
            ),
            "language_acc": round(
                np.mean([r["classification"]["language"] == r["language"] for r in cls]), 4
            ),
        }

    # Calibration on field-level correctness: two folds by document hash, each half scored by a
    # calibrator fit on the other half; the saved calibrator is fit on everything.
    cal_summary, cal, raw, calibrated, correct = _calibration(rows, use_arbiter=True)
    if cal is not None:
        cal.save()
        (ARTIFACTS / "calibration_rows.json").write_text(json.dumps(_calibration_rows(rows)))
        summary["calibration"] = cal_summary
        _reliability_chart(raw, calibrated, correct)
        summary["review"] = _review_curve(calibrated, correct, threshold, targets)
        summary["signals"] = _signal_breakdown(rows)

    arb = [r for r in rows if r.get("arbiter")]
    if arb:
        summary["arbiter"] = _arbiter_summary(arb)
        without, _, _, cal_wo, cor_wo = _calibration(rows, use_arbiter=False)
        if without:
            curve_wo = _review_curve(cal_wo, cor_wo, threshold, targets, chart=False)
            summary["arbiter"]["without_signal"] = {
                "ece_calibrated": without["ece_calibrated"],
                "brier_calibrated": without["brier_calibrated"],
                "review_rate_at_95pct_accuracy": curve_wo.get("review_rate_at_95pct_accuracy"),
                "review_rate_at_98pct_accuracy": curve_wo.get("review_rate_at_98pct_accuracy"),
            }
            summary["arbiter"]["with_signal"] = {
                "ece_calibrated": summary["calibration"]["ece_calibrated"],
                "brier_calibrated": summary["calibration"]["brier_calibrated"],
                "review_rate_at_95pct_accuracy": summary["review"].get("review_rate_at_95pct_accuracy"),
                "review_rate_at_98pct_accuracy": summary["review"].get("review_rate_at_98pct_accuracy"),
            }

    # Latency and tokens.
    lat = [r["latency_s"] for r in rows if "latency_s" in r]
    toks_in = sum(p.get("input_tokens", 0) for r in rows for p in r.get("paths", []))
    toks_out = sum(p.get("output_tokens", 0) for r in rows for p in r.get("paths", []))
    toks_in += sum(r["arbiter"].get("input_tokens", 0) for r in arb)
    toks_out += sum(r["arbiter"].get("output_tokens", 0) for r in arb)
    reader = [
        max(p.get("latency_s", 0.0) for p in r["paths"])
        for r in rows
        if r.get("paths") and not r.get("text_only")
    ]
    summary["latency_s"] = (
        {
            "p50": round(float(np.percentile(lat, 50)), 2),
            "p95": round(float(np.percentile(lat, 95)), 2),
            "reader_p50": round(float(np.percentile(reader, 50)), 2) if reader else None,
            "reader_p95": round(float(np.percentile(reader, 95)), 2) if reader else None,
        }
        if lat
        else {}
    )
    summary["tokens"] = {
        "input": toks_in,
        "output": toks_out,
        "per_doc_input": round(toks_in / max(1, len(rows))),
        "per_doc_output": round(toks_out / max(1, len(rows))),
    }
    if PRICE_IN and PRICE_OUT:
        cost = (toks_in * PRICE_IN + toks_out * PRICE_OUT) / 1e6
        summary["cost_usd"] = {
            "total": round(cost, 2),
            "per_1000_docs": round(cost / max(1, len(rows)) * 1000, 2),
        }

    _f1_charts(agg)
    (ARTIFACTS / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def _calibration_rows(rows: list[dict]) -> list[list]:
    out = []
    for r in rows:
        if not r.get("fields"):
            continue
        fields = r.get("fields_arbiter") or r["fields"]
        labels = label_for_calibration(r.get("pred_arbiter") or r["pred"], r["gold"])
        for f in fields:
            if f["value"] in (None, "", []) or f["field"] not in labels:
                continue
            out.append([r["doc_type"], round(float(f["raw_score"]), 4), bool(labels[f["field"]])])
    return out


def _calibration(rows: list[dict], use_arbiter: bool):
    folds: list[list[tuple[str, float, bool]]] = [[], []]
    fold_ds: list[list[str]] = [[], []]
    for r in rows:
        if not r.get("fields"):
            continue
        fields = (r.get("fields_arbiter") if use_arbiter else None) or r["fields"]
        pred = (r.get("pred_arbiter") if use_arbiter else None) or r["pred"]
        labels = label_for_calibration(pred, r["gold"])
        k = _stable_hash(r["doc_id"]) % 2
        for f in fields:
            if f["value"] in (None, "", []) or f["field"] not in labels:
                continue
            folds[k].append((r["doc_type"], float(f["raw_score"]), bool(labels[f["field"]])))
            fold_ds[k].append(r["dataset"])
    all_rows = folds[0] + folds[1]
    if len(all_rows) < 50:
        return {}, None, None, None, None
    cal = Calibrator.fit(all_rows)
    test: list[tuple[str, float, bool]] = []
    calibrated_list: list[float] = []
    datasets: list[str] = []
    for k in (0, 1):
        cal_k = Calibrator.fit(folds[1 - k]) if len(folds[1 - k]) >= 50 else Calibrator()
        for (d, s, c), ds in zip(folds[k], fold_ds[k], strict=True):
            test.append((d, s, c))
            datasets.append(ds)
            calibrated_list.append(cal_k(s, d))
    raw = np.array([s for _, s, _ in test])
    correct = np.array([c for _, _, c in test], dtype=float)
    calibrated = np.array(calibrated_list)
    by_dataset = {}
    for name in sorted(set(datasets)):
        m = np.array([d == name for d in datasets])
        by_dataset[name] = {
            "fields": int(m.sum()),
            "ece": round(_ece(calibrated[m], correct[m]), 4),
            "accuracy": round(float(correct[m].mean()), 4),
        }
    summary = {
        "by_dataset": by_dataset,
        "folds": 2,
        "fold_fields": [len(folds[0]), len(folds[1])],
        "test_fields": len(test),
        "field_accuracy": round(float(correct.mean()), 4),
        "ece_raw": round(_ece(raw, correct), 4),
        "ece_calibrated": round(_ece(calibrated, correct), 4),
        "brier_raw": round(float(np.mean((raw - correct) ** 2)), 4),
        "brier_calibrated": round(float(np.mean((calibrated - correct) ** 2)), 4),
    }
    return summary, cal, raw, calibrated, correct


def _arbiter_summary(rows: list[dict]) -> dict:
    disputes = sum(r["arbiter"]["disputes"] for r in rows)
    choices: dict[str, int] = defaultdict(int)
    base, override = [], []
    by_choice: dict[str, list[bool]] = defaultdict(list)
    changed = 0
    for r in rows:
        old = label_fields(r["pred"], r["gold"])
        new = label_fields(r.get("pred_override") or r["pred_arbiter"], r["gold"])
        for v in r["arbiter"]["verdicts"]:
            choices[v["choice"]] += 1
            f = v["field"]
            if f in old and f in new:
                base.append(old[f])
                override.append(new[f])
                by_choice[v["choice"]].append(new[f])
                changed += old[f] != new[f]
    lat = [r["arbiter"]["latency_s"] for r in rows if r["arbiter"].get("latency_s")]
    with_disputes = [r for r in rows if r["arbiter"]["disputes"]]
    return {
        "documents": len(rows),
        "documents_with_disputes": len(with_disputes),
        "disputes": disputes,
        "verdicts": dict(choices),
        "disputed_fields_scored": len(base),
        "disputed_accuracy_base": round(float(np.mean(base)), 4) if base else None,
        "disputed_accuracy_override": round(float(np.mean(override)), 4) if override else None,
        "override_accuracy_by_choice": {
            k: {"n": len(v), "accuracy": round(float(np.mean(v)), 4)} for k, v in sorted(by_choice.items())
        },
        "fields_flipped_by_override": changed,
        "latency_p50": round(float(np.percentile(lat, 50)), 2) if lat else None,
        "tokens_in": sum(r["arbiter"].get("input_tokens", 0) for r in rows),
        "tokens_out": sum(r["arbiter"].get("output_tokens", 0) for r in rows),
        "tokens_in_per_document_with_disputes": round(
            sum(r["arbiter"].get("input_tokens", 0) for r in with_disputes) / max(1, len(with_disputes))
        ),
    }


def _signal_breakdown(rows: list[dict]) -> dict:
    out: dict[str, dict] = {}
    groups: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        labels = label_for_calibration(r.get("pred_arbiter") or r["pred"], r["gold"])
        for f in r.get("fields_arbiter") or r["fields"]:
            if f["field"] not in labels or f["value"] in (None, "", []):
                continue
            ok = labels[f["field"]]
            groups[f"agree={f['agree']}"].append(ok)
            groups[f"validator={f['validator']}"].append(ok)
            if f.get("arbiter"):
                groups[f"arbiter={f['arbiter']}"].append(ok)
    for k, v in sorted(groups.items()):
        out[k] = {"n": len(v), "accuracy": round(float(np.mean(v)), 4)}
    return out


def _review_curve(
    conf: np.ndarray, correct: np.ndarray, threshold: float, targets: tuple[float, ...], chart: bool = True
) -> dict:
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
    res[f"at_threshold_{threshold}"] = {
        "review_rate": round(float(1 - auto.mean()), 4),
        "auto_accuracy": round(float(correct[auto].mean()) if auto.any() else 1.0, 4),
    }
    if not chart:
        return res
    fig, ax = plt.subplots(figsize=(6, 3.6), dpi=160)
    ax.plot(review * 100, acc * 100, color=TEAL, linewidth=2)
    ax.axhline(correct.mean() * 100, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(1, correct.mean() * 100 + 0.4, "no review", color=MUTED, fontsize=8)
    for target in targets:
        key = f"review_rate_at_{int(target * 100)}pct_accuracy"
        if key in res:
            x = res[key] * 100
            ax.plot([x], [target * 100], marker="o", color=AMBER, markersize=7)
            ax.annotate(
                f"{target:.0%} accuracy at {x:.0f}% reviewed",
                (x, target * 100),
                xytext=(8, -12),
                textcoords="offset points",
                fontsize=8,
                color=INK,
            )
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
    strict = {
        lang: c.f1 for (d, lang, p), c in agg.items() if d == "xfund" and lang != "all" and p == "merged"
    }
    lenient = {
        lang: c.f1 for (d, lang, p), c in agg.items() if d == "xfund" and lang != "all" and p == "lenient"
    }
    for p, target in (("merged", strict), ("lenient", lenient)):
        for (d, lang, pp), c in agg.items():
            if d == "funsd" and lang == "all" and pp == p:
                target["en"] = c.f1
    if strict:
        langs = sorted(strict, key=lambda k: -strict[k])
        fig, ax = plt.subplots(figsize=(6, 3.2), dpi=160)
        x = np.arange(len(langs))
        width = 0.38 if lenient else 0.6
        ax.bar(
            x - (width / 2 if lenient else 0),
            [strict[k] * 100 for k in langs],
            width,
            color=TEAL,
            label="Strict pairs",
        )
        if lenient:
            ax.bar(
                x + width / 2,
                [lenient.get(k, 0) * 100 for k in langs],
                width,
                color="#9FD3C7",
                label="Lenient, fragment-aware",
            )
        for i, k in enumerate(langs):
            ax.text(
                i - (width / 2 if lenient else 0),
                strict[k] * 100 + 1,
                f"{strict[k] * 100:.0f}",
                ha="center",
                fontsize=7,
                color=INK,
            )
            if lenient and k in lenient:
                ax.text(
                    i + width / 2,
                    lenient[k] * 100 + 1,
                    f"{lenient[k] * 100:.0f}",
                    ha="center",
                    fontsize=7,
                    color=INK,
                )
        ax.set_xticks(x)
        ax.set_xticklabels([k.upper() for k in langs])
        ax.set_ylim(0, 105)
        ax.set_ylabel("Key-value F1 (%)")
        ax.set_title("Form extraction F1 by language (XFUND, FUNSD)", fontsize=10, loc="left", pad=18)
        if lenient:
            ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
        _style(ax)
        fig.tight_layout()
        fig.savefig(ARTIFACTS / "f1_by_language.png")
        plt.close(fig)

    datasets = sorted({d for (d, lang, p) in agg if d != "all"})
    paths = [
        p for p in ("vision", "ocr_text", "merged", "arbiter") if any((d, "all", p) in agg for d in datasets)
    ]
    if datasets and len(paths) > 1:
        fig, ax = plt.subplots(figsize=(7, 3.4), dpi=160)
        width = 0.8 / len(paths)
        colors = {
            "vision": NAVY,
            "ocr_text": AMBER,
            "merged": "#9FD3C7" if "arbiter" in paths else TEAL,
            "arbiter": TEAL,
        }
        labels = {
            "vision": "Vision reader",
            "ocr_text": "OCR + text reader",
            "merged": "Both + validators",
            "arbiter": "Both + validators + arbiter",
        }
        x = np.arange(len(datasets))
        for i, p in enumerate(paths):
            vals = [agg[(d, "all", p)].f1 * 100 if (d, "all", p) in agg else 0 for d in datasets]
            ax.bar(
                x + (i - (len(paths) - 1) / 2) * width,
                vals,
                width=width * 0.92,
                color=colors[p],
                label=labels[p],
            )
        ax.set_xticks(x)
        ax.set_xticklabels([d.replace("_", " ") for d in datasets])
        ax.set_ylim(0, 105)
        ax.set_ylabel("Field F1 (%)")
        ax.set_title("Ablation: each reader alone versus the full pipeline", fontsize=10, loc="left", pad=22)
        ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(paths))
        _style(ax)
        fig.tight_layout()
        fig.savefig(ARTIFACTS / "ablation.png")
        plt.close(fig)
