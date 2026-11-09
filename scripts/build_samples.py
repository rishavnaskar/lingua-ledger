"""Copy a small, varied set of benchmark documents into samples/ for the hosted demo."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "samples"

PICKS = {
    "synth_invoices": {"per_language": 1, "languages": ["de", "fr", "ja", "es", "en"], "title": "Invoice"},
    "cord": {"per_language": 2, "languages": ["id"], "title": "Receipt"},
    "sroie": {"per_language": 1, "languages": ["en"], "title": "Receipt"},
    "xfund": {"per_language": 1, "languages": ["zh", "ja", "de", "es", "pt"], "title": "Form"},
    "funsd": {"per_language": 1, "languages": ["en"], "title": "Form"},
}

LANG_NAMES = {
    "de": "German",
    "fr": "French",
    "ja": "Japanese",
    "es": "Spanish",
    "en": "English",
    "id": "Indonesian",
    "zh": "Chinese",
    "pt": "Portuguese",
    "it": "Italian",
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    index = []
    for dataset, spec in PICKS.items():
        path = PROCESSED / dataset / "samples.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        for lang in spec["languages"]:
            picked = [r for r in rows if r["language"] == lang and r["image_paths"]][: spec["per_language"]]
            for i, r in enumerate(picked):
                src = Path(r["image_paths"][0])
                sample_id = f"{dataset}-{lang}-{i + 1}"
                dst = OUT / f"{sample_id}{src.suffix.lower()}"
                shutil.copyfile(src, dst)
                index.append(
                    {
                        "id": sample_id,
                        "title": f"{spec['title']} · {LANG_NAMES.get(lang, lang)}",
                        "doc_type": r["doc_type"],
                        "language": lang,
                        "dataset": dataset,
                        "file": dst.name,
                        "doc_id": r["doc_id"],
                    }
                )
    (OUT / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"{len(index)} samples -> {OUT}")


if __name__ == "__main__":
    main()
