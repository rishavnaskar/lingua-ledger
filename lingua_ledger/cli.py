from __future__ import annotations

import json
from pathlib import Path

import typer

from .config import DEFAULT_REVIEW_THRESHOLD
from .schemas import DocType

app = typer.Typer(no_args_is_help=True, add_completion=False)
eval_app = typer.Typer(no_args_is_help=True)
app.add_typer(eval_app, name="eval")


@app.command()
def extract(path: Path, doc_type: DocType | None = None, language: str | None = None,
            threshold: float = DEFAULT_REVIEW_THRESHOLD, paths: str = "vision,ocr_text", out: Path | None = None):
    from .pipeline import run

    result = run(path, doc_type=doc_type, language=language, threshold=threshold,
                 paths=tuple(p.strip() for p in paths.split(",")))
    payload = result.model_dump_json(indent=2)
    if out:
        out.write_text(payload)
        typer.echo(f"wrote {out}")
    else:
        typer.echo(payload)


@app.command()
def data(name: str = "all", limit: int | None = None):
    from .eval.datasets import DATASETS, build

    names = DATASETS if name == "all" else [name]
    for n in names:
        samples = build(n, limit=limit)
        typer.echo(f"{n}: {len(samples)} samples")


@app.command()
def synth(n_per_lang: int = 8):
    from .synth import generate

    records = generate(n_per_lang=n_per_lang)
    typer.echo(f"synth_invoices: {len(records)} samples")


@eval_app.command("run")
def eval_run(datasets: str = "all", limit: int | None = None, paths: str = "vision,ocr_text", workers: int = 4,
             resume: bool = True):
    from .eval.run import run_eval

    run_eval(datasets=datasets, limit=limit, paths=tuple(p.strip() for p in paths.split(",")), workers=workers,
             resume=resume)


@eval_app.command("report")
def eval_report(threshold: float = DEFAULT_REVIEW_THRESHOLD):
    from .eval.report import build_report

    summary = build_report(threshold=threshold)
    typer.echo(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
