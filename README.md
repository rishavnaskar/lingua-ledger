# Lingua Ledger

Self-verifying extraction for multilingual business documents. Two independent readers (a vision model and OCR plus a text model), deterministic validators, and per-field confidence calibrated against held-out ground truth so that a reported 0.9 means roughly 90 percent correct.

Built for DataNova 2026 Global Data-thon, problem statement DN-AI-01 (Multilingual Intelligent Document Understanding).

## Quick start

```bash
uv sync --all-extras
cp .env.example .env   # add ANTHROPIC_API_KEY
uv run ll extract path/to/invoice.pdf
```

## Reproducing the evaluation

```bash
uv run ll data all          # download and normalize public benchmarks
uv run ll eval run          # run both extraction paths on the eval sets
uv run ll eval report       # metrics, calibration and review-rate charts in artifacts/
```

See PLAN.md for the design, datasets and judging mapping.
