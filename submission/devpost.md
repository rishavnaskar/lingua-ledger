# Lingua Ledger - Devpost submission

Paste each part into the matching Devpost field.

## Project overview

Project name: Lingua Ledger

Elevator pitch (200 characters max):
Self-verifying extraction for multilingual business documents. Every field comes back with a confidence score you can actually trust.

Thumbnail: submission/thumbnail.png (1500 x 1000, 3:2)

## Project details

About the project (paste everything between the two lines):

---

## Inspiration
Businesses get invoices, receipts, forms, and contracts in many different languages. LLMs can pull data out quickly, but you never know which fields to trust, so someone still has to check everything by hand. We wanted a tool that looks at each field and decides to either "post this automatically" or say "a person should check this"—and actually knows how reliable its own guesses are.

## What it does
- Takes a PDF or image in 9 tested languages (English, German, French, Spanish, Italian, Portuguese, Japanese, Chinese, Indonesian) and figures out the document type (invoice, receipt, form, contract) and language.
- Reads the page twice in two independent ways: a vision model looks at the image directly, while Tesseract OCR feeds text into a language model. Both fill in the same strict schema.
- If the two readers disagree, an arbiter vision model zooms in on a tight crop around the disputed values to make a call. This adds only one extra call per document, and only when there is a disagreement.
- Checks basic facts with code rules: line items must add up to totals, dates must parse in valid order, IBAN checksums must match, VAT id formats must be valid, currency codes must exist, and receipt change math must work out.
- Combines five signals (reader agreement, arbiter verdict, OCR word confidence, validator results, and model self-confidence) into a single score per field. An isotonic regression calibration maps this score so 0.9 actually means about 90 percent correct.
- Sends low-confidence fields to a human reviewer. A simple slider shows the live balance between review workload and expected accuracy.
- Shows clear proof for every field: the bounding box on the page, which reader extracted it, and which rules confirmed it.
- Checks documents against a ledger memory of past records to catch duplicates, sudden bank account changes for known vendors, future dates, invalid tax rates for a vendor's country, or mismatched currencies.
- Learns right away from human feedback: whenever you accept or fix a field in the review panel, it recalculates calibration on the fly and shows before-and-after review rates and calibration error.
- Lets you open sample documents instantly from saved runs, or hit the Run live button to test a fresh extraction.

## How we built it
We built the backend with Python 3.13 and FastAPI, and the frontend with Next.js 15. For data and processing, we used pydantic v2 schemas, Tesseract, pypdfium2, scikit-learn for isotonic calibration, and matplotlib for charts. For AI, we used Google Gemini (specifically gemini-3.5-flash-lite for the reported run, though you can switch to Claude with a single environment variable). We deployed both the web app and a containerised API onto Vercel. We wrote 242 unit tests. To test calibration fairly, we used two-fold cross-fitting grouped by document, ensuring every one of the 3,961 scored fields was evaluated by a calibrator that had never seen that document. Every number and chart in our slides and README comes straight from running `uv run ll eval report`.

## Challenges we ran into
- Zero budget: we ran the entire evaluation on the Gemini Free Tier (15 requests per minute, 500 per day on Flash-Lite) using Google's smallest model. We had to build a custom rate limiter, handle 429 retries, and make runs resumable. Our daily limit ran out right in the middle of re-running forms, so we had to finish during the next window. These benchmark numbers are a true baseline floor, not a ceiling.
- Messy form benchmarks: datasets like XFUND and FUNSD label raw text fragments, meaning a single address can be split across three key-value pairs. Strict matching punishes models that cleanly combine text into one field. To stay fair, we report the official strict benchmark score alongside a more forgiving fragment-aware score.
- Forms are still tricky: updating our form prompt gave mixed results across all 90 form documents. Strict scores moved from 50.9% to 51.9% on XFUND, but slipped from 53.3% to 50.2% on FUNSD. However, lenient scores improved on both (63.5% to 64.3% on XFUND, and 57.8% to 67.5% on FUNSD). We kept the updated prompt and shared both sets of numbers.
- Strict schema rules: Gemini structured output does not support free-form dictionaries, so we had to return confidence scores as a list of {field, confidence} pairs.

## Accomplishments that we're proud of
Results across 198 public benchmark documents (synthetic multilingual invoices, CORD, SROIE, CUAD, FUNSD, XFUND):
- Field F1 scores combining readers and validators: synthetic invoices reached 98.6%, SROIE receipts reached 95.0%, CORD receipts reached 94.7%, CUAD contracts reached 60.2%, FUNSD forms scored 50.2% strict / 67.5% lenient, and XFUND forms scored 51.9% strict / 64.3% lenient.
- Document classification accuracy: correct document type on 92.4% of files, and correct language on 88.9%.
- Calibration really works: expected calibration error dropped from 0.190 raw down to 0.037 calibrated on held-out fields, and the Brier score dropped from 0.166 to 0.104.
- A practical operating curve instead of just one generic accuracy number: 87.6% of fields are accurate with zero human review. At our default 0.85 threshold, you review 31.8% of fields and the remaining automated fields are 92.6% accurate. Reviewing 65.2% brings automatic accuracy to 95%, and reviewing 72.1% hits 98%.
- Low cost: the entire benchmark run cost $1.12 at list prices, which works out to $5.64 per 1,000 documents (averaging about 3,873 input and 1,789 output tokens per document, including arbiter calls).
- Speed: median reader time (p50) was 9.98 s, and median total time (p50) was 18.06 s, even with Free Tier rate-limit pauses included.
- A live public demo where anyone can try real sample documents in seven languages.

## What we learned
- Agreement is king: when both independent readers agree on a field, it is right 94.0% of the time, compared to just 79.6% when they disagree.
- The arbiter works better as a confidence signal than as an editor. When we let it overwrite values across 109 labelled disputed fields, accuracy only nudged from 78.0% to 79.8%. When it picked the OCR reader, it was correct only 53.8% of the time. But when the arbiter confirmed a value, that value was right 88.6% of the time. Keeping the original extraction and using the arbiter's verdict to adjust the score lowered calibration error from 0.038 to 0.037.
- Failed rule checks are rarer and less fatal than we assumed: across 25 fields with failed checks, the extracted text was still right 84.0% of the time. Calibrating all signals together works much better than blindly trusting raw model confidence.
- Document types calibrate differently: calibration error is low on invoices and receipts (0.010 to 0.016) and forms (0.045 to 0.053), but higher on contracts (0.187), which had the fewest sample fields (123).

## What's next for Lingua Ledger
- Swap in larger reader models through the same pipeline (using a single environment variable) and try out a stronger arbiter model.
- Add layout data for forms by passing OCR bounding boxes directly to the text reader, and improve key normalisation for Japanese and Chinese.
- Build automatic three-way matching between purchase orders, invoices, and receipts.
- Move vendor memory from local files to a production database.
- Add bounding-box highlights for individual line items, plus clean CSV exports for accounting software.
- Collect more contract data to improve contract calibration.

---

Built with: python, fastapi, next.js, react, typescript, tailwindcss, pydantic, tesseract, pypdfium2, scikit-learn, matplotlib, google-gemini, docker, vercel

Try it out links:
- https://lingua-ledger-three.vercel.app
- https://github.com/rishavnaskar/lingua-ledger

Image gallery / files: deck/LinguaLedger-DataNova2026-Round1.pptx

Video demo link: optional
