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

Sample documents in the hosted demo open instantly. We precompute their results using `uv run ll cache-samples` and store them in samples/cache with one JSON file per sample. Clicking a sample displays this saved run with its original date, while anomalies and ledger memory are still checked live against current data. A Run live button reruns the entire extraction with fresh model calls, and any file you upload always runs live. We created the stored sample runs with gemini-3.5-flash because the evaluation used up the daily flash-lite quota. Run `uv run ll cache-samples` again to refresh them with the default model.

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
uv run ll cache-samples
```

The report outputs artifacts/summary.json, artifacts/f1_table.csv, and four charts: review_curve.png (review rate needed for 95 and 98 percent accuracy on auto-accepted fields), reliability.png (calibration before and after isotonic fitting, with ECE and Brier score), f1_by_language.png, and ablation.png (vision only vs OCR-text only vs merged). summary.json records p50 and p95 latency plus cost per 1,000 documents. Costs follow config list prices: gemini-3.5-flash-lite at 0.30 USD per million input tokens and 2.50 USD per million output tokens (including thinking tokens); override these with LL_PRICE_IN_PER_M and LL_PRICE_OUT_PER_M. The --limit flag distributes documents evenly across languages, so the run above tests the exact same 198-document set every time. Runs are resumable: re-running the same command finishes any documents that failed.

Each dataset is scored only on the fields it labels: SROIE on merchant name, address, date and total; CORD on line items, subtotal, tax, service charge, discount, total, cash paid and change; CUAD on document name, parties, agreement date, effective date and governing law; XFUND and FUNSD on the title and the key-value fields. Matching is exact after normalization (amounts as numbers, dates in ISO format, text case and whitespace folded); list fields are matched pairwise.

## Results

We tested 198 public benchmark documents: 28 synthetic invoices, 30 CORD receipts, 30 SROIE receipts, 20 CUAD contracts, 20 FUNSD forms, and 70 XFUND forms. We ran everything on gemini-3.5-flash-lite for the vision reader, the OCR-text reader, and the classifier. All runs used the Gemini API Free Tier (no paid usage), running 2 parallel workers at 15 requests per minute. Scores show field-level F1 compared to published ground truth, scoring each dataset only on the fields it labels.

### Field extraction F1

| Benchmark | Documents | Vision only | OCR + text only | Both + validators | Lenient (forms) |
|---|---|---|---|---|---|
| synthetic invoices (DE, EN, ES, FR, IT, JA, PT) | 28 | 98.6% | 95.9% | **98.6%** |  |
| CORD receipts (ID) | 30 | 94.9% | 52.4% | **94.7%** |  |
| SROIE receipts (EN) | 30 | 95.0% | 88.6% | **95.0%** |  |
| CUAD contracts (EN) | 20 | 60.9% | 60.1% | **60.2%** |  |
| FUNSD forms (EN) | 20 | 53.9% | 39.0% | **53.3%** | 57.8% |
| XFUND forms (DE, ES, FR, IT, JA, PT, ZH) | 70 | 50.9% | 31.9% | **50.9%** | 63.4% |
| All | 198 | 64.2% | 49.7% | **63.9%** | |

The form benchmarks (XFUND and FUNSD) use strict key-value matching based on original annotations. Because these annotations split single fields into pieces (like splitting postcode, prefecture, and street into separate entries under one key), a reader that extracts one clean field gets counted as one true positive and multiple false negatives. Because of this, treat form numbers as a lower bound. Japanese forms scored lowest at 34.6% F1, which is our top priority for improvement.

We score forms in two ways. Strict scoring follows the published benchmark: every gold text fragment is treated as its own pair and must match a predicted pair on both label and value. Lenient scoring works more like a human grader. A gold fragment counts as found if its text matches or appears inside a predicted value under a similar label, and a predicted pair counts as correct if its value sits inside the gold text for that label. We keep strict scoring for official comparisons, but lenient scoring shows how people actually judge the results. Both come from the same predictions without any extra model calls.

We also changed how we read forms. The prompt now asks for one pair per printed label in reading order, the label exactly as printed without qualifiers or trailing colons, the whole filled value kept together even when it spans a postal code and an address, the ticked option text for checkbox groups instead of true or false, and no inserted spaces in Japanese or Chinese. We also clean keys after extraction by removing trailing colons and dropping boolean and empty values. These prompt changes did not improve the scores. On the 67 XFUND documents that re-ran before the Free Tier day quota ran out, strict F1 went from 50.8% to 51.9% and lenient F1 from 62.5% to 63.2%; on the 10 Japanese forms among them, strict went from 34.6% to 37.2% and lenient from 50.9% to 56.8%. The numbers in the tables are from the original full run, and the remaining form documents will re-run when the quota resets. The gap comes from what the model extracts rather than the prompt wording, so our next step is adding layout input (OCR word boxes passed to the text reader) rather than more prompt changes.

You can see the per-language form F1 in artifacts/f1_by_language.png, and the full table for each reader on its own in artifacts/f1_table.csv.

### Arbiter

Across 101 of 198 documents (forms excluded), our readers disagreed on 233 fields. The arbiter agreed with the vision reader 195 times, picked the OCR reader 24 times, read a different value 12 times, and marked 2 crops as unreadable.

We tested letting the arbiter overwrite values, but it did not help. On the 118 disputed fields with gold labels, accuracy went from 76.3% to 75.4%. The vision reader was usually right to begin with, and overrides were wrong more often than right (accuracy was 41.7% when it picked OCR, and 25.0% when it read a new value).

Where the arbiter really helps is with confidence scoring. Fields confirmed by the arbiter are right 81.4% of the time, compared to 62.2% for disagreements overall. So by default, we leave the original value alone and only let the verdict adjust the score. That cuts our calibration error from 0.022 to 0.016 and drops the review rate at 95% accuracy from 63.9% to 63.8%.

Median arbiter time is 8.3 s per document, using about 2,724 input tokens per document with disputes. We plan to test a stronger arbiter model in Round 2.

### Classification

The model identified document type correctly on 92.4% of documents, and language on 88.9%.

### Calibration and review routing

We tested calibration with two-fold cross-fitting by document hash. The calibrator trained on one half of the documents scored the other half (2480 and 2060 fields per half), so every one of the 4540 fields was evaluated by a model that had never seen that document. The calibrator included in the demo is fit on all of them.

| | Raw score | Calibrated |
|---|---|---|
| Expected calibration error (lower is better) | 0.146 | 0.016 |
| Brier score (lower is better) | 0.183 | 0.148 |

- Fields correct with no human review at all: 74.9%
- To reach 95 percent accuracy on auto-accepted fields: send 63.8% of fields to review (threshold 0.89)
- To reach 98 percent accuracy: send 76.0% of fields to review (threshold 0.94)
- At the default threshold 0.85: 57.1% of fields reviewed, 94.4% accuracy on what posts automatically

Signals behind the score: when both readers agree, the field is right 93.8% of the time. When they disagree, it is right 62.2% of the time. When a validator fails, the field is right only 14.0% of the time, which is why a failed rule pulls confidence down fast.

Charts: artifacts/reliability.png and artifacts/review_curve.png.

### Cost and latency

| | Value |
|---|---|
| Tokens per document (both readers) | 3,825 in, 1,595 out |
| Model cost for the whole run | $1.02 at list prices (0.30 USD per million input tokens, 2.50 per million output tokens including thinking tokens) |
| Cost per 1,000 documents | $5.14 |
| Reader latency, p50 / p95 | 11.82 s / 43.05 s |
| End-to-end latency, p50 / p95 | 21.19 s / 63.81 s |

These latency numbers include Free Tier rate limits (15 requests per minute, with wait times and retries on 429 responses), so they represent an upper bound. Without those rate limits, the same model takes about 7 seconds end to end per document.

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
