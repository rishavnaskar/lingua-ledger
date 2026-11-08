# DataNova 2026 Global Data-thon — Battle Plan

Owner: Rishav Naskar (rishavnaskar.r@gmail.com). Written 2026-11-09 01:40 IST.

## Hard facts (verified 2026-11-09)

| Item | Value |
|---|---|
| Devpost listing | https://datanova-2026-global-data-thon.devpost.com/ |
| Organizer site / problem statements | https://datanovathon.com/#problems |
| Unstop listing (registration + ₹100 fee) | https://unstop.com/o/I8wokZ9 |
| Unstop registration deadline | **Mon 10 Nov 2026, 12:00 AM IST** (tonight) |
| Unstop Round 1 deadline (PPT + demo) | **Tue 10 Nov 2026, 6:35 PM IST** |
| Devpost submission deadline | **Wed 11 Nov 2026, 3:30 AM IST** |
| Judging | 11 Nov 7:30 PM → 16 Nov 3:30 AM IST (Devpost); Round 2 live presentations over Google Meet until 25 Nov |
| Winners announced | 7 Dec 2026 (Devpost) / closing ceremony 30 Nov (site) |
| Team size | 1–5 (Unstop). Solo is allowed; teammates can be added later |
| Fee | ₹100 per participant on Unstop |
| Prizes | $1,000 / $500 / $250 + tool memberships |
| Round 1 deliverables | PPT (required), working demo link, optional video. Unstop says PPT is uploaded *at registration*. |
| Devpost deliverables | PPT, working demo link, optional video |
| Rules of note | Must own rights to code/data; acknowledge third-party components; no fabricated results; organizers may ask for a live demo to verify authenticity |

### Judging rubric (Devpost, weighted)

| Criterion | Weight | What it means for us |
|---|---|---|
| Technical Implementation | 25% | Real working pipeline, non-trivial engineering, clean code, hosted demo |
| Innovation & Originality | 20% | A clear differentiator vs. "LLM + prompt" or "XGBoost + SHAP" |
| Problem Relevance | 15% | Pick an official problem statement, cite it by ID, nail the framing |
| Data & Analytical Rigor | 15% | Public benchmark, per-language/per-field metrics, calibration, ablations |
| Impact & Feasibility | 15% | Quantified business value, deployment story, cost per document |
| Presentation & Documentation | 10% | Tight PPT, 2–3 min video, README that reproduces every number |

Judges and jury are mostly enterprise architects / data engineers (AWS, Google, Salesforce, Citi, Gap, Zscaler). They will reward production thinking: validation, confidence, cost, human-in-the-loop.

## Track decision: DN-AI-01 — Multilingual Intelligent Document Understanding

Official text: "Build an AI system that extracts, classifies and structures information from multilingual business documents (invoices, contracts, forms) with varying layouts and quality." Expected outcome: "A working pipeline that ingests raw documents and outputs structured, validated data with confidence scores." Requirements: code, docs, demo video, presentation, evaluation metrics.

Why this one:
- "Advanced" difficulty, GenAI-native, fits Rishav's LLM + web strengths; a live drag-and-drop demo is visually convincing.
- The expected outcome literally asks for *validated* data with *confidence scores*. Most entries will ship an LLM prompt and a JSON blob. We ship calibrated confidence and prove it with numbers. That is the differentiator.
- Public multilingual benchmarks exist (XFUND: 7 languages, FUNSD: EN forms, CORD/SROIE: receipts, CUAD: contracts), so Data & Analytical Rigor is attainable in a day.

Rejected: DN-HC-01 (crowded "XGBoost+SHAP on diabetes" space, low novelty ceiling), DN-FN-01 (same, PaySim fraud is a tutorial), DN-OR-01 (OR-Tools VRP demos are common and dataset must be invented).

## The product: **Lingua Ledger** (working name) — self-verifying multilingual document extraction

One-liner: Drop any invoice, receipt, form or contract in any language; get schema-conformant JSON where every field carries a *calibrated* confidence, so a human reviews only the fields that actually need it.

### Architecture

1. **Ingest**: PDF/image/scan → page images (pdf2image / pypdfium2). Auto language + document-type classification (LLM, one call).
2. **Dual-path extraction**:
   - Path A: vision-LLM reads the page directly against a document-type JSON schema (structured output).
   - Path B: OCR text + layout (Tesseract via pytesseract, multilingual traineddata) → text-only LLM extraction against the same schema.
3. **Validation layer** (deterministic): arithmetic (line items sum to subtotal, tax math, totals), date parsing/ordering, currency/IBAN/VAT-ID regexes, cross-field consistency, enum checks. Each rule emits pass/fail per field.
4. **Confidence engine**: per-field score = f(path agreement, OCR word confidence under the field's bbox, validator outcome, LLM self-reported confidence). Calibrated with isotonic regression on a held-out split so "0.9" means ~90% correct. Report ECE/reliability diagram.
5. **Review router**: fields below threshold τ go to a review queue; the UI highlights the source region. Headline metric: *at a 98% field-accuracy target, X% of fields need human review* (vs. 100% review today).
6. **Output**: validated JSON + audit trail (which path, which rules, which evidence), exportable CSV.

### Datasets (all public, licensed for research)

- XFUND (doc-analysis/XFUND v1.0): forms in ZH, JA, ES, FR, IT, DE, PT with key-value annotations → semantic entity + linking F1 per language.
- FUNSD: EN forms (same schema as XFUND).
- CORD v2 (naver-clova-ix/cord-v2 on HF): receipts with field-level labels → field F1, arithmetic validation hit-rate.
- SROIE (ICDAR 2019): English receipts, 4 key fields → exact-match F1.
- CUAD (TheAtticusProject): contracts, clause extraction → small subset (e.g., parties, dates, governing law, termination) for the "contracts" document type.
- "5 languages × 4 document types" claim is then true: forms (XFUND/FUNSD), receipts (CORD/SROIE), invoices (synthetic multilingual invoices rendered from templates + CORD), contracts (CUAD).

### Evaluation plan (what goes on the "Results" slide)

- Per-language field F1 on XFUND (7 langs) + FUNSD; per-field F1 on CORD/SROIE.
- Ablation: vision-only vs OCR-only vs dual-path + validation.
- Calibration: reliability diagram + ECE before/after isotonic calibration.
- Review-rate vs accuracy curve: the business chart.
- Latency and $/document.

### Stack

- Python 3.13 + uv; pydantic schemas; pytesseract + pypdfium2; Anthropic SDK (claude-sonnet-5-5 for vision + text; claude-haiku-5-5 for classification) with structured outputs; scikit-learn for calibration; FastAPI backend.
- Frontend: Next.js (App Router) + Tailwind; deployed on Vercel; backend on Fly.io/Render/Railway (needs Tesseract binary) or HF Space. Fallback: Gradio on HF Spaces if time gets tight.
- Repo: github.com/rishavnaskar/lingua-ledger (public, MIT). README reproduces every metric with one command.

## Schedule (IST)

| When | Milestone |
|---|---|
| Sun 9 Nov 02:00–06:00 | PPT v1 (proposal deck) so Rishav can register on Unstop; repo scaffold; dataset downloads |
| Sun 9 Nov day | Extraction pipeline (both paths), schemas for 4 doc types, validators, eval harness on CORD + XFUND subset |
| Sun 9 Nov evening | Confidence engine + calibration; first real numbers; FastAPI |
| **Sun 9 Nov before 23:30** | **Rishav registers + pays on Unstop, uploads PPT v1** |
| Mon 10 Nov morning | Next.js UI, deploy demo, record 2–3 min video |
| Mon 10 Nov afternoon | PPT v2 with real results; README; polish |
| **Mon 10 Nov 18:00** | **Unstop Round 1 submission updated (PPT v2 + demo + video)** |
| **Mon 10 Nov night** | **Devpost submission (before Wed 11 Nov 03:30)** |
| 11–25 Nov | Round 2 prep: 7-minute live pitch, live demo, Q&A bank |

## Blockers only Rishav can clear

1. Log in to Devpost in the browser pane and click "Join hackathon" (page already open).
2. Register + pay ₹100 on Unstop before midnight tonight; upload PPT v1 (I will produce it).
3. Provide an Anthropic API key (export ANTHROPIC_API_KEY) for the extraction pipeline and demo. ~$20–40 budget for eval + demo.
4. Confirm the track choice (DN-AI-01) or veto now; anything later costs hours.
