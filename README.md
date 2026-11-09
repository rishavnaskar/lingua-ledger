# Lingua Ledger

Lingua Ledger extracts structured, validated data from documents in multiple languages, giving you a calibrated confidence score for every field.

Entry for the DataNova 2026 Global Data-thon, track DN-AI-01 (Multilingual Intelligent Document Understanding).

Live demo: https://lingua-ledger-three.vercel.app
Source: https://github.com/rishavnaskar/lingua-ledger

## The problem

Businesses receive invoices, receipts, forms, and contracts in many languages. Pulling out fields by hand is slow. Using an LLM is fast, but you cannot tell which values to trust, so someone still has to check every single field. Lingua Ledger answers one question: which fields can you auto-accept, and which ones need a human check? It gives each field a calibrated confidence score, meaning a score of 0.9 actually means the value is correct about 90 percent of the time.

## How it works

1. Ingest. We render PDF pages and images using pypdfium2 at 150 dpi, up to 4 pages per document.
2. Classify. A small model (gemini-3.5-flash-lite) detects the document type (invoice, receipt, form, contract) and its language.
3. Two independent readers. Reader A (vision) sends page images to gemini-3.6-flash. Reader B (OCR text) runs Tesseract with the detected language pack and sends the OCR text to the same model. Both readers populate the same pydantic schema using structured JSON, and each gives its own 0-1 confidence score for every field.
4. Reconcile. We use the vision output as our base and fill in missing fields from the OCR reader. If a validation rule fails on the vision value but passes with the OCR value, we use the OCR value instead.
5. Validate. We check deterministic rules without calling any models: line items sum to the subtotal, subtotal plus tax equals total, dates parse, due date comes after the invoice date, currency is a valid ISO 4217 code, IBAN checksum passes, VAT id format is valid, receipt change arithmetic matches, contract dates follow proper order, and form fields are non-empty.
6. Score. Each field receives a raw score from four signals: agreement between both readers, Tesseract word confidence under the located value, validator pass or fail, and the model's self-reported confidence.
7. Calibrate. An isotonic regression (scikit-learn) turns raw scores into calibrated probabilities. We fit this per document type with a global fallback, training on half of the evaluation documents and testing on the other half.
8. Route. Any field below a threshold (default 0.85) is flagged for review. The output is a single JSON object with the data, per-field confidence, evidence box and page for each value, validator results, and raw outputs from both readers.

Provider: Gemini by default (GEMINI_API_KEY). Set ANTHROPIC_API_KEY instead to run on Claude models. If a Gemini model returns a server error, the call automatically falls back to gemini-3.5-flash.

Document types: invoice, receipt, form, contract. Languages tested in the evaluation: English, German, French, Spanish, Italian, Portuguese, Japanese, Chinese, Indonesian. The Docker image also includes OCR packs for Hindi.

## Quickstart

Requirements: Python 3.13, uv, Tesseract with language packs (macOS: brew install tesseract tesseract-lang), Node 20+ for the web app.

```bash
uv sync
cp .env.example .env   # add GEMINI_API_KEY
uv run ll extract samples/synth_invoices-de-1.jpg
```

Run the API and the web app locally:

```bash
uv run uvicorn api.main:app --port 8000
cd web && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Docker (API only, includes Tesseract):

```bash
docker build -t lingua-ledger .
docker run -p 8000:8000 -e GEMINI_API_KEY=... lingua-ledger
```

Deployment: vercel.json defines two Vercel services: the Next.js app in web/ and the API container built from the Dockerfile, served under /api on the same domain.

## Reproduce the evaluation

Every number in the deck comes from these commands.

```bash
uv run ll data all        # downloads and normalizes XFUND, FUNSD, CORD, SROIE, CUAD into data/processed/
uv run ll synth           # generates 56 synthetic invoices in 7 languages, clean and noisy renders
uv run ll eval run --datasets synth_invoices,cord,funsd,cuad,xfund --workers 6
uv run ll eval run --datasets sroie --limit 150 --workers 6
uv run ll eval report --threshold 0.85
```

The report writes artifacts/summary.json, artifacts/f1_table.csv, and four charts: review_curve.png (review rate needed to reach 95 and 98 percent accuracy on auto-accepted fields), reliability.png (calibration before and after isotonic fitting, with ECE and Brier score), f1_by_language.png, and ablation.png (vision only vs OCR-text only vs merged). Latency p50 and p95 and cost per 1,000 documents are saved in summary.json. Costs use list prices: gemini-3.6-flash at 0.75 USD per million input tokens and 3.75 USD per million output tokens including thinking tokens; override these with LL_PRICE_IN_PER_M and LL_PRICE_OUT_PER_M.

Each dataset is scored only on the fields it labels: SROIE on merchant name, address, date and total; CORD on line items, subtotal, tax, service charge, discount, total, cash paid and change; CUAD on document name, parties, agreement date, effective date and governing law; XFUND and FUNSD on the title and the key-value fields. Matching is exact after normalization (amounts as numbers, dates in ISO format, text case and whitespace folded); list fields are matched pairwise.

## Results

Numbers, charts and the cost table are added here once the full evaluation run finishes. Until then, the Evidence page of the live demo shows the metrics the backend has.

## Tests

```bash
uv run pytest -q
uv run ruff check .
```

225 tests cover the validators, normalization, confidence scoring, calibration, OCR value location, dataset loaders, and the synthetic generator.

## Project layout

- lingua_ledger/ pipeline: ingest.py, ocr.py, classify.py, extract.py, pipeline.py, validate.py, normalize.py, confidence.py, schemas.py, config.py, llm.py, synth.py
- lingua_ledger/eval/ datasets.py (loaders), metrics.py, run.py, report.py
- api/main.py FastAPI service: POST /extract, GET /samples, POST /samples/{id}/extract, GET /metrics
- web/ Next.js review workbench, evidence page, about page
- deck/ pptxgenjs generator for the Round 1 deck
- tests/

## Datasets and third-party components

Evaluation data is downloaded by the user at run time and is not redistributed in this repository. Datasets: XFUND (Microsoft), FUNSD (Guillaume Jaume et al.), CORD (Clova AI), SROIE (ICDAR 2019), and CUAD (The Atticus Project). Each is used under its own license strictly for evaluation. The 56 synthetic invoices were generated by this project using reportlab and are free to use.

Components: Tesseract OCR (Apache 2.0), pypdfium2, pydantic, FastAPI, scikit-learn, rapidfuzz, matplotlib, reportlab, Next.js, Tailwind CSS, lucide-react, pptxgenjs. Models: Google Gemini API (gemini-3.6-flash, gemini-3.5-flash-lite); optional Anthropic Claude.

## Limitations

- Reads up to 4 pages per document.
- OCR quality depends on installed Tesseract language packs; CJK word confidences are noisier than Latin scripts.
- Calibration is fit on the evaluation datasets; for a new document domain, label a sample and refit it with ll eval report.
- Model API rate limits constrain throughput; the evaluation runs with 6 parallel workers.

## Author

Rishav Naskar, rishavnaskar.r@gmail.com
