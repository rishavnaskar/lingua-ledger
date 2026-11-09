# Lingua Ledger

Lingua Ledger extracts structured, validated data from documents in multiple languages, giving you a calibrated confidence score for every field.

Entry for the DataNova 2026 Global Data-thon, track DN-AI-01 (Multilingual Intelligent Document Understanding).

Live demo: https://lingua-ledger-three.vercel.app
Source: https://github.com/rishavnaskar/lingua-ledger

## The problem

Businesses receive invoices, receipts, forms, and contracts in many languages. Pulling out fields by hand is slow. Using an LLM is fast, but you cannot tell which values to trust, so someone still has to check every single field. Lingua Ledger answers one question: which fields can you auto-accept, and which ones need a human check? It gives each field a calibrated confidence score, meaning a score of 0.9 actually means the value is correct about 90 percent of the time.

## How it works

1. Ingest. We render PDF pages and images using pypdfium2 at 150 dpi, up to 4 pages per document.
2. Classify. A fast, small model (gemini-3.5-flash-lite by default) detects the document type (invoice, receipt, form, contract) and its language.
3. Two independent readers. Reader A (vision) sends page images directly to the vision model. Reader B (OCR text) runs Tesseract with the detected language pack and sends the extracted text to the text model. Both default to gemini-3.5-flash-lite; set LL_VISION_MODEL and LL_TEXT_MODEL to switch to a larger model like gemini-3.6-flash. Both readers fill out the same pydantic schema using structured JSON, and each scores its confidence from 0-1 for every field.
4. Reconcile. We use the vision output as our base and fill in missing fields from the OCR reader. If a validation rule fails on the vision value but passes with the OCR value, we use the OCR value instead.
5. Validate. We check deterministic rules without calling any models: line items sum to the subtotal, subtotal plus tax equals total, dates parse, due date comes after the invoice date, currency is a valid ISO 4217 code, IBAN checksum passes, VAT id format is valid, receipt change arithmetic matches, contract dates follow proper order, and form fields are non-empty.
6. Score. Each field receives a raw score from four signals: agreement between both readers, Tesseract word confidence under the located value, validator pass or fail, and the model's self-reported confidence.
7. Calibrate. An isotonic regression (scikit-learn) turns raw scores into calibrated probabilities. We fit this per document type with a global fallback, training on half of the evaluation documents and testing on the other half.
8. Route. Any field below a threshold (default 0.85) is flagged for review. The output is a single JSON object with the data, per-field confidence, evidence box and page for each value, validator results, and raw outputs from both readers.

Provider: Gemini by default (GEMINI_API_KEY). Set ANTHROPIC_API_KEY instead to use Claude models. Optional: LL_FALLBACK_MODELS lists backup models to try if the main one hits a server error, and LL_GEMINI_RPM (default 15) caps requests per minute so a Free Tier key avoids 429 errors.

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
uv run ll eval run --datasets synth_invoices --limit 28 --workers 2
uv run ll eval run --datasets cord --limit 30 --workers 2
uv run ll eval run --datasets funsd,cuad --limit 20 --workers 2
uv run ll eval run --datasets xfund --limit 70 --workers 2
uv run ll eval run --datasets sroie --limit 30 --workers 2
uv run ll eval report --threshold 0.85
```

The report outputs artifacts/summary.json, artifacts/f1_table.csv, and four charts: review_curve.png (review rate needed for 95 and 98 percent accuracy on auto-accepted fields), reliability.png (calibration before and after isotonic fitting, with ECE and Brier score), f1_by_language.png, and ablation.png (vision only vs OCR-text only vs merged). summary.json records p50 and p95 latency plus cost per 1,000 documents. Costs follow config list prices: gemini-3.5-flash-lite at 0.30 USD per million input tokens and 2.50 USD per million output tokens (including thinking tokens); override these with LL_PRICE_IN_PER_M and LL_PRICE_OUT_PER_M. The --limit flag distributes documents evenly across languages, so the run above tests the exact same 198-document set every time. Runs are resumable: re-running the same command finishes any documents that failed.

Each dataset is scored only on the fields it labels: SROIE on merchant name, address, date and total; CORD on line items, subtotal, tax, service charge, discount, total, cash paid and change; CUAD on document name, parties, agreement date, effective date and governing law; XFUND and FUNSD on the title and the key-value fields. Matching is exact after normalization (amounts as numbers, dates in ISO format, text case and whitespace folded); list fields are matched pairwise.

## Results

We tested this setup on 198 public benchmark documents: 28 synthetic invoices, 30 CORD receipts, 30 SROIE receipts, 20 CUAD contracts, 20 FUNSD forms, and 70 XFUND forms. We ran the vision reader, the OCR-text reader, and the classifier on gemini-3.5-flash-lite within the Gemini API Free Tier (no paid usage), using 2 parallel workers at 15 requests per minute. All scores reflect field-level F1 against the published ground truth, counting only the fields labeled by each dataset.

### Field extraction F1

| Benchmark | Documents | Vision only | OCR + text only | Both + validators |
|---|---|---|---|---|
| synthetic invoices (DE, EN, ES, FR, IT, JA, PT) | 28 | 98.6% | 95.9% | **98.6%** |
| CORD receipts (ID) | 30 | 94.9% | 52.4% | **94.7%** |
| SROIE receipts (EN) | 30 | 95.0% | 88.6% | **95.0%** |
| CUAD contracts (EN) | 20 | 60.9% | 60.1% | **60.2%** |
| FUNSD forms (EN) | 20 | 53.9% | 39.0% | **53.3%** |
| XFUND forms (DE, ES, FR, IT, JA, PT, ZH) | 70 | 50.9% | 31.9% | **50.9%** |
| All | 198 | 64.2% | 49.7% | **63.9%** |

Form datasets (XFUND, FUNSD) are scored by strict key-value matching against the original linking annotations. Because those annotations split single logical fields into separate fragments (such as postcode, prefecture, and street listed as three values under the same key), an extraction that produces one clean key-value pair is scored as one true positive and multiple false negatives. As a result, treat the form scores as a lower bound. Japanese forms are currently our weakest case at 34.6% F1 and are the main area we are working to improve.

See artifacts/f1_by_language.png for form F1 broken down by language, and artifacts/f1_table.csv for the full table with results from each individual reader.

### Classification

The model correctly identified the document type on 92.4% of documents and the language on 88.9%.

### Calibration and review routing

We fitted calibration on documents with an even hash and evaluated it on the odd half (2162 fit fields, 2378 test fields).

| | Raw score | Calibrated |
|---|---|---|
| Expected calibration error (lower is better) | 0.157 | 0.017 |
| Brier score (lower is better) | 0.182 | 0.139 |

- Fields correct with no human review at all: 77.1%
- To reach 95 percent accuracy on auto-accepted fields: send 66.4% of fields to review (threshold 0.91)
- To reach 98 percent accuracy: send 80.7% of fields to review (threshold 0.95)
- At the default threshold 0.85: 54.8% of fields are reviewed, and auto-accepted fields reach 94.9% accuracy

What drives the confidence score: when both readers agree, the field is correct 93.8% of the time; when they disagree, that drops to 62.2%. When a validator fails, the field is correct only 14.0% of the time, which is why a failed rule sharply reduces confidence.

Detailed charts are available in artifacts/reliability.png and artifacts/review_curve.png.

### Cost and latency

| | Value |
|---|---|
| Tokens per document (both readers) | 2,435 in, 1,548 out |
| Model cost for the whole run | $0.91 at list prices (0.30 USD per million input tokens, 2.50 per million output tokens including thinking tokens) |
| Cost per 1,000 documents | $4.60 |
| Reader latency, p50 / p95 | 11.82 s / 43.05 s |
| End-to-end latency, p50 / p95 | 21.19 s / 63.81 s |

These latency figures reflect the Free Tier rate limit of 15 requests per minute, including wait times and retries on 429 responses, so they serve as an upper bound. Without rate limits, the same model processes a document end to end in about 7 seconds.

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

Components: Tesseract OCR (Apache 2.0), pypdfium2, pydantic, FastAPI, scikit-learn, rapidfuzz, matplotlib, reportlab, Next.js, Tailwind CSS, lucide-react, pptxgenjs. Models: Google Gemini API (the reported run used gemini-3.5-flash-lite for vision, OCR text, and classification; you can choose any Gemini or Claude model via environment variables).

## Limitations

- Reads up to 4 pages per document.
- OCR quality depends on installed Tesseract language packs; CJK word confidences are noisier than Latin scripts.
- Calibration is fit on the evaluation datasets; for a new document domain, label a sample and refit it with ll eval report.
- The reported run used the Gemini Free Tier (15 requests per minute, 500 per day on Flash-Lite), taking several hours across 2 workers. A paid key or larger model will change speed and quality; these numbers represent the smallest model.

## Author

Rishav Naskar, rishavnaskar.r@gmail.com
