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
5. Arbiter. When both readers find a value but do not agree, we do not guess. We crop a tight image of both values using the OCR word boxes, then send all crops for that document to the vision model in a single call. For each disputed field, the model chooses candidate a, candidate b, a different printed value, or marks it unreadable. This adds just one model call per document, and only for documents with disputes. Forms are skipped because their key-value pairs do not line up across readers. Turn it off with LL_ARBITER=0, and select the model with LL_ARBITER_MODEL. By default, the arbiter only updates the confidence score (`LL_ARBITER_MODE=signal`). If you set `LL_ARBITER_MODE=override`, it also replaces the merged value. We tested both options on our benchmark and decided to ship signal mode (see Results).
6. Validate. We check deterministic rules without calling any models: line items sum to the subtotal, subtotal plus tax equals total, dates parse, due date comes after the invoice date, currency is a valid ISO 4217 code, IBAN checksum passes, VAT id format is valid, receipt change arithmetic matches, contract dates follow proper order, and form fields are non-empty.
7. Score. Every field gets a raw score based on five signals: whether both readers agree, the Tesseract word confidence for the text found, whether validation checks passed, the model's self-reported confidence, and the arbiter's choice if there was a dispute.
8. Calibrate. An isotonic regression (scikit-learn) turns raw scores into calibrated probabilities. We fit this per document type with a global fallback, training on half of the evaluation documents and testing on the other half.
9. Route. Any field below a threshold (default 0.85) is flagged for review. The output is a single JSON object with the data, per-field confidence, evidence box and page for each value, validator results, and raw outputs from both readers.

Provider: Gemini by default (GEMINI_API_KEY). Set ANTHROPIC_API_KEY instead to use Claude models. Optional: LL_FALLBACK_MODELS lists backup models to try if the main one hits a server error, and LL_GEMINI_RPM (default 15) caps requests per minute so a Free Tier key avoids 429 errors.

Document types: invoice, receipt, form, contract. Languages tested in the evaluation: English, German, French, Spanish, Italian, Portuguese, Japanese, Chinese, Indonesian. The Docker image also includes OCR packs for Hindi.

## Beyond one document

Extraction is only half the job. The Workbench runs three extra steps for every document, without making any new model calls.

Anomalies. Simple business rules in lingua_ledger/anomaly.py check for issues beyond a single page. They catch invoice dates set in the future or older than two years, payment terms past 180 days, contracts that have expired or are about to expire, wrong currencies, and invalid tax rates based on tables for 17 countries (matched using VAT id, IBAN, currency, or language). With ledger memory, the checks spot even more: repeated invoice numbers or identical vendor, date, and total combinations are flagged as duplicates, altered IBANs are marked as bank changes, and new currencies for known vendors are flagged. Every anomaly shows its affected fields and a severity: high, check, or note.

Ledger memory. When you approve a document in the review screen, the system saves its details under the vendor's VAT id or normalised name. It tracks past invoice numbers, date and total fingerprints, IBANs, currencies, and tax rates. Any future document from that vendor is checked against this history. This data is saved in one JSON file under state/ (LL_STATE_DIR). The hosted demo resets this storage on redeploy, which works fine for testing and takes only a one-line change to switch to a database.

Learning from review. Every accept or fix in the review panel serves as training data, tracking the field, raw score, and whether it was correct. The server adds each edit to the 4,540 labelled fields from the benchmark run with a weight of 10 (LL_CORRECTION_WEIGHT), then updates the isotonic calibrator right away. The response shows the review volume needed for 95% and 98% accuracy, the calibration error before and after, and the updated curve for that document type. Approving low-scoring fields that were actually right lowers your review load, while fixing incorrect fields sends more items for review where needed.

The API provides three extra routes: POST /review saves your edits, updates the calibrator, and logs the document to memory; GET /learning returns current state and operating points; and POST /learning/reset clears the demo memory. Every extraction response now includes an arbiter block, an anomalies list, and a memory block.

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
uv run ll eval arbiter --workers 2
uv run ll eval report --threshold 0.85
```

The report outputs artifacts/summary.json, artifacts/f1_table.csv, and four charts: review_curve.png (review rate needed for 95 and 98 percent accuracy on auto-accepted fields), reliability.png (calibration before and after isotonic fitting, with ECE and Brier score), f1_by_language.png, and ablation.png (vision only vs OCR-text only vs merged). summary.json records p50 and p95 latency plus cost per 1,000 documents. Costs follow config list prices: gemini-3.5-flash-lite at 0.30 USD per million input tokens and 2.50 USD per million output tokens (including thinking tokens); override these with LL_PRICE_IN_PER_M and LL_PRICE_OUT_PER_M. The --limit flag distributes documents evenly across languages, so the run above tests the exact same 198-document set every time. Runs are resumable: re-running the same command finishes any documents that failed.

Each dataset is scored only on the fields it labels: SROIE on merchant name, address, date and total; CORD on line items, subtotal, tax, service charge, discount, total, cash paid and change; CUAD on document name, parties, agreement date, effective date and governing law; XFUND and FUNSD on the title and the key-value fields. Matching is exact after normalization (amounts as numbers, dates in ISO format, text case and whitespace folded); list fields are matched pairwise.

## Results

We tested this on 198 public benchmark documents: 28 synthetic invoices, 30 CORD receipts, 30 SROIE receipts, 20 CUAD contracts, 20 FUNSD forms, and 70 XFUND forms. We ran the vision reader, the OCR-text reader, and the classifier on gemini-3.5-flash-lite, staying entirely within the Gemini API Free Tier (no paid usage). The run used 2 parallel workers capped at 15 requests per minute. Scores show field-level F1 against the published ground truth, scoring each dataset only on the fields it labels.

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

Form datasets (XFUND, FUNSD) are scored by strict key-value pair matching against the original linking annotations. Those annotations split a single field into several pieces (for example, marking the postcode, the prefecture, and the street as three separate values under the same key). Because of this, if a reader returns one clean key-value pair, it gets counted as one true positive and several false negatives. You should treat these form scores as a lower bound. Japanese forms are our weakest result (34.6% F1) and our top priority for improvement.

You can view the form F1 scores by language in artifacts/f1_by_language.png, and the complete table with standalone reader scores in artifacts/f1_table.csv.

### Arbiter

Across 101 of 198 documents (forms excluded), our readers disagreed on 233 fields. The arbiter agreed with the vision reader 195 times, picked the OCR reader 24 times, read a different value 12 times, and marked 2 crops as unreadable.

We tested letting the arbiter overwrite values, but it did not help. On the 118 disputed fields with gold labels, accuracy went from 76.3% to 75.4%. The vision reader was usually right to begin with, and overrides were wrong more often than right (accuracy was 41.7% when it picked OCR, and 25.0% when it read a new value).

Where the arbiter really helps is with confidence scoring. Fields confirmed by the arbiter are right 81.4% of the time, compared to 62.2% for disagreements overall. So by default, we leave the original value alone and only let the verdict adjust the score. That cuts our calibration error from 0.022 to 0.016 and drops the review rate at 95% accuracy from 63.9% to 63.8%.

Median arbiter time is 8.3 s per document, using about 2,724 input tokens per document with disputes. We plan to test a stronger arbiter model in Round 2.

### Classification

Document type was detected correctly on 92.4% of documents, and language was detected correctly on 88.9%.

### Calibration and review routing

We evaluated calibration using two-fold cross-fitting based on document hashes. We fit the calibrator on one half of the documents and scored the other half. That means each of the 4540 fields was evaluated by a calibrator that had never seen its document (2480 and 2060 fields per half). The calibrator included in the demo is fit on all of them.

| | Raw score | Calibrated |
|---|---|---|
| Expected calibration error (lower is better) | 0.146 | 0.016 |
| Brier score (lower is better) | 0.183 | 0.148 |

- Fields correct with no human review at all: 74.9%
- To reach 95 percent accuracy on auto-accepted fields: send 63.8% of fields to review (threshold 0.89)
- To reach 98 percent accuracy: send 76.0% of fields to review (threshold 0.94)
- At the default threshold 0.85: 57.1% of fields reviewed, 94.4% accuracy on what posts automatically

Signals behind the score: when the two readers agree, the field is correct 93.8% of the time; when they disagree, 62.2%. When a validator fails, the field is correct only 14.0% of the time, which is why a failed rule pulls the confidence down hard.

Charts: artifacts/reliability.png and artifacts/review_curve.png.

### Cost and latency

| | Value |
|---|---|
| Tokens per document (both readers) | 3,825 in, 1,595 out |
| Model cost for the whole run | $1.02 at list prices (0.30 USD per million input tokens, 2.50 per million output tokens including thinking tokens) |
| Cost per 1,000 documents | $5.14 |
| Reader latency, p50 / p95 | 11.82 s / 43.05 s |
| End-to-end latency, p50 / p95 | 21.19 s / 63.81 s |

These latency numbers include Free Tier rate limiting (15 requests per minute, plus waits and retries on 429 responses), so they are an upper bound. Without rate limits, a document takes about 7 seconds end to end on the same model.

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
