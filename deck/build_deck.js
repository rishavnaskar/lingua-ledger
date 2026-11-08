// Builds the DataNova 2026 Round-1 deck for Lingua Ledger (DN-AI-01).
// Usage: node build_deck.js [out.pptx]
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const Lu = require("react-icons/lu");
const path = require("path");
const { applyTheme } = require(process.env.PPTX_SKILL_DIR + "/scripts/apply_theme.js");

const OUT = process.argv[2] || path.join(__dirname, "LinguaLedger-DataNova2026-Round1.pptx");

const THEME = {
  name: "Lingua Ledger",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "121A2B", // ink
    lt1: "FFFFFF",
    dk2: "4A5568", // slate text
    lt2: "EEF2F6", // paper tint
    accent1: "0F8B8D", // verdigris (verified)
    accent2: "E8A33D", // amber (needs review)
    accent3: "C8553D", // brick (rejected)
    accent4: "1F3A5F", // deep blue-ink
    accent5: "9FD3C7", // mint tint
    accent6: "F6E7C8", // amber tint
    hlink: "0F8B8D",
    folHlink: "4A5568",
  },
};
const H = THEME.colors;

async function iconPng(name, hex, px = 256) {
  const Comp = Lu[name];
  if (!Comp) throw new Error("no icon " + name);
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color: "#" + hex, size: px, strokeWidth: 1.75 })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // 10 x 5.625
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.author = "Rishav Naskar";
  pres.title = "Lingua Ledger — DataNova 2026 (DN-AI-01)";
  const C = pres.SchemeColor;

  const FOOT = "DataNova 2026 Global Data-thon  ·  DN-AI-01 Multilingual Intelligent Document Understanding  ·  Lingua Ledger";

  // ---------- layouts ----------
  pres.defineSlideMaster({
    title: "DARK",
    background: { color: H.dk1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 8.8, h: 1.4, fontSize: 40, bold: true, color: H.lt1, align: "left", valign: "bottom", margin: 0 } } },
      { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.05, w: 8.4, h: 1.2, fontSize: 18, color: H.accent5, align: "left", valign: "top", margin: 0 } } },
      { text: { text: FOOT, options: { x: 0.6, y: 5.15, w: 8.0, h: 0.3, fontSize: 9, color: H.dk2, margin: 0 } } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: H.lt1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.35, w: 9.0, h: 0.75, fontSize: 26, bold: true, color: H.dk1, align: "left", valign: "middle", margin: 0 } } },
      { placeholder: { options: { name: "body", type: "body", x: 0.5, y: 1.2, w: 9.0, h: 3.8, fontSize: 15, color: H.dk2, align: "left", valign: "top", margin: 0 } } },
      { text: { text: FOOT, options: { x: 0.5, y: 5.2, w: 8.4, h: 0.25, fontSize: 8, color: "9AA5B1", margin: 0 } } },
    ],
    slideNumber: { x: 9.1, y: 5.18, w: 0.4, h: 0.3, fontSize: 9, color: "9AA5B1", align: "right" },
  });

  // ---------- helpers ----------
  const icons = {};
  async function ic(name, hex) {
    const k = name + hex;
    if (!icons[k]) icons[k] = await iconPng(name, hex);
    return icons[k];
  }
  async function iconCircle(slide, x, y, d, name, fill, stroke) {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name + " badge" });
    const pad = d * 0.24;
    slide.addImage({ data: await ic(name, stroke), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, objectName: name + " icon" });
  }
  function card(slide, x, y, w, h, opts = {}) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w, h, rectRadius: 0.08,
      fill: { color: opts.fill || H.lt2 },
      line: { color: opts.line || H.lt2, width: 0.75 },
      shadow: { type: "outer", color: "000000", blur: 4, offset: 1, angle: 90, opacity: 0.08 },
      objectName: opts.name || "card",
    });
  }
  function text(slide, t, o) {
    slide.addText(t, Object.assign({ isTextBox: true, margin: 0, fontSize: 14, color: C.text2 }, o));
  }
  function bullets(items, size = 14, color = C.text2, after = 6) {
    return items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, fontSize: size, color, breakLine: i < items.length - 1, paraSpaceAfter: after } }));
  }
  function pill(slide, x, y, label, fill, color = H.lt1) {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 0.95, h: 0.3, rectRadius: 0.15, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: "pill " + label });
    text(slide, label, { x, y, w: 0.95, h: 0.3, fontSize: 10, bold: true, color, align: "center", valign: "middle" });
  }

  // ======================================================================
  pres.addSection({ title: "Opening" });
  // 1. Title
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Opening" });
    text(s, "DATANOVA 2026 GLOBAL DATA-THON  ·  TRACK DN-AI-01", { x: 0.6, y: 0.6, w: 8, h: 0.3, fontSize: 11, bold: true, color: H.accent2, charSpacing: 2 });
    s.addText("Lingua Ledger", { placeholder: "title" });
    s.addText([
      { text: "Self-verifying extraction for multilingual business documents. ", options: { color: H.accent5 } },
      { text: "Every field comes back with a confidence score you can actually trust.", options: { color: H.lt1 } },
    ], { placeholder: "body" });
    // document motif: three stacked "doc" cards with pills
    const docs = [["Invoice · DE", H.accent1, "0.97"], ["Form · JA", H.accent2, "0.71"], ["Contract · ES", H.accent1, "0.94"]];
    docs.forEach(([lbl, col, conf], i) => {
      const x = 7.0 + i * 0.35, y = 0.85 + i * 0.3;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.9, h: 1.0, rectRadius: 0.06, fill: { color: H.accent4 }, line: { color: "2B4A75", width: 0.75 }, objectName: "doc card " + lbl });
      text(s, lbl, { x: x + 0.12, y: y + 0.08, w: 1.4, h: 0.25, fontSize: 9, color: H.lt1, bold: true });
      [0.3, 0.45, 0.6].forEach((dy, j) => s.addShape(pres.shapes.RECTANGLE, { x: x + 0.12, y: y + dy, w: j === 2 ? 0.8 : 1.2, h: 0.06, fill: { color: "3B5C8A" }, line: { color: "3B5C8A", width: 0 }, objectName: "line" }));
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 1.25, y: y + 0.66, w: 0.55, h: 0.24, rectRadius: 0.12, fill: { color: col }, line: { color: col, width: 0 }, objectName: "conf pill" });
      text(s, conf, { x: x + 1.25, y: y + 0.66, w: 0.55, h: 0.24, fontSize: 9, bold: true, color: H.dk1, align: "center", valign: "middle" });
    });
    text(s, "Rishav Naskar  ·  rishavnaskar.r@gmail.com  ·  Round 1 submission, November 2026", { x: 0.6, y: 4.55, w: 8.4, h: 0.3, fontSize: 12, color: H.lt1 });
    s.addNotes("Lingua Ledger is our entry for DN-AI-01. The one idea to remember: extraction is a solved demo and an unsolved product, because nobody trusts the output. We make the confidence score mean something and prove it with numbers.");
  }

  // ======================================================================
  pres.addSection({ title: "Problem" });
  // 2. Problem
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
    s.addText("Every language and layout arrives. Trust does not", { placeholder: "title" });
    text(s, "Official challenge DN-AI-01: extract, classify and structure information from multilingual invoices, contracts and forms with varying layouts and quality, and output structured, validated data with confidence scores.", { x: 0.5, y: 1.15, w: 9.0, h: 0.6, fontSize: 13, italic: true, color: C.text2 });
    const cols = [
      ["LuLanguages", "Multilingual by default", "Finance, legal and operations teams in India, the EU and South-East Asia process invoices and contracts in 5–10 languages, often mixed on a single page."],
      ["LuLayoutTemplate", "No two layouts alike", "Template-based OCR breaks on every new vendor. LLMs read anything, but they also confidently invent a VAT number when the scan is blurry."],
      ["LuUserX", "100% human review, or silent errors", "Because nobody can tell which fields are right, teams either re-key everything or accept errors into the ledger. Both are expensive."],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05, y = 1.95, w = 2.9, h = 2.95;
      card(s, x, y, w, h, { name: "problem card " + i });
      await iconCircle(s, x + 0.2, y + 0.2, 0.55, cols[i][0], H.accent4, H.lt1);
      text(s, cols[i][1], { x: x + 0.2, y: y + 0.9, w: w - 0.4, h: 0.5, fontSize: 15, bold: true, color: C.text1 });
      text(s, cols[i][2], { x: x + 0.2, y: y + 1.4, w: w - 0.4, h: 1.45, fontSize: 12, color: C.text2, valign: "top" });
    }
    s.addNotes("Problem framing straight from the DN-AI-01 statement. The pain is not reading the document; it is knowing which of the 40 fields you just extracted can be posted to the ledger without a human looking.");
  }

  // 3. Insight
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
    s.addText("A confidence score that actually means something", { placeholder: "title" });
    const rows = [
      ["Template OCR", "Brittle; fails on new layouts", "Word-level OCR confidence only", "Every exception to a human", "A7B0BC"],
      ["Prompt-and-pray LLM", "Reads anything", "Self-reported, uncalibrated, often wrong", "All or nothing", "A7B0BC"],
      ["Lingua Ledger", "Vision LLM + OCR LLM, cross-checked", "Calibrated per field: 0.9 means ~90% correct", "Only low-confidence fields", H.accent1],
    ];
    const hdr = ["Approach", "Layout robustness", "Confidence", "Human review"];
    const cx = [0.5, 2.6, 4.9, 7.4], cw = [2.0, 2.2, 2.4, 2.1];
    hdr.forEach((h, i) => text(s, h, { x: cx[i], y: 1.3, w: cw[i], h: 0.3, fontSize: 11, bold: true, color: "9AA5B1", charSpacing: 1 }));
    rows.forEach((r, ri) => {
      const y = 1.7 + ri * 0.95;
      const strong = ri === 2;
      card(s, 0.5, y, 9.0, 0.82, { fill: strong ? H.accent5 : H.lt2, line: strong ? H.accent1 : H.lt2, name: "row " + r[0] });
      text(s, r[0], { x: cx[0] + 0.15, y, w: cw[0] - 0.15, h: 0.82, fontSize: 14, bold: true, color: strong ? H.dk1 : C.text1, valign: "middle" });
      for (let i = 1; i < 4; i++) text(s, r[i], { x: cx[i], y, w: cw[i] - 0.15, h: 0.82, fontSize: 12, color: strong ? H.dk1 : C.text2, valign: "middle" });
    });
    text(s, "Our headline metric: at a target field accuracy (e.g. 98%), what share of fields still needs a human? Lower is better, and it is measurable.", { x: 0.5, y: 4.6, w: 9.0, h: 0.45, fontSize: 13, italic: true, color: H.accent4 });
    s.addNotes("Two incumbent approaches, each with a real weakness. We are not claiming better reading; we are claiming trustworthy reading, and we define the metric that proves it: review rate at a fixed accuracy target.");
  }

  // ======================================================================
  pres.addSection({ title: "Solution" });
  // 4. Solution overview
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
    s.addText("Read twice, validate, calibrate, route", { placeholder: "title" });
    const steps = [
      ["LuScanLine", "Ingest and classify", "PDF, photo or scan in. Pages rendered, language and document type detected (invoice, receipt, form, contract)."],
      ["LuCopy", "Extract twice, independently", "Path A: a vision model reads the page against a strict JSON schema. Path B: multilingual OCR text + layout, same schema, text-only model."],
      ["LuShieldCheck", "Validate deterministically", "Line items must sum, tax maths must hold, dates must parse and order, IBAN / VAT / currency formats must match. Every rule is explainable."],
      ["LuGauge", "Calibrate confidence per field", "Path agreement, OCR word confidence under the field, validator outcome and model self-report are fused, then isotonic-calibrated on held-out data."],
      ["LuUserCheck", "Route only what needs eyes", "Fields under the threshold go to a review queue with the source region highlighted. Everything else posts automatically, with an audit trail."],
    ];
    for (let i = 0; i < steps.length; i++) {
      const y = 1.2 + i * 0.78;
      await iconCircle(s, 0.5, y + 0.05, 0.5, steps[i][0], i === 4 ? H.accent2 : H.accent1, H.lt1);
      text(s, steps[i][1], { x: 1.2, y: y, w: 2.6, h: 0.6, fontSize: 15, bold: true, color: C.text1, valign: "middle" });
      text(s, steps[i][2], { x: 3.85, y: y, w: 5.65, h: 0.62, fontSize: 12, color: C.text2, valign: "middle" });
    }
    s.addNotes("Five stages. The two that are unusual are extracting twice through independent paths and calibrating the fused confidence against held-out ground truth. The rest is engineering discipline that most hackathon entries skip.");
  }

  // 5. Architecture
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
    s.addText("Two independent readers, one deterministic judge", { placeholder: "title" });
    const box = (x, y, w, h, title, sub, fill, fg) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: title });
      text(s, title, { x: x + 0.1, y: y + 0.08, w: w - 0.2, h: 0.3, fontSize: 12, bold: true, color: fg });
      if (sub) text(s, sub, { x: x + 0.1, y: y + 0.38, w: w - 0.2, h: h - 0.45, fontSize: 9.5, color: fg, valign: "top" });
    };
    const arrow = (x1, y1, x2, y2) => s.addShape(pres.shapes.LINE, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color: H.dk2, width: 1.25, endArrowType: "triangle" }, objectName: "arrow" });
    // row 1
    box(0.5, 1.45, 1.55, 1.1, "Ingest", "pypdfium2 render · deskew · language + doc-type classifier (small model)", H.lt2, H.dk1);
    arrow(2.05, 2.0, 2.4, 2.0);
    box(2.4, 1.25, 2.1, 0.75, "Path A · Vision LLM", "Page image → schema-constrained JSON", H.accent4, H.lt1);
    box(2.4, 2.2, 2.1, 0.75, "Path B · OCR + text LLM", "Tesseract (multilingual) → text + boxes → same schema", H.accent4, H.lt1);
    arrow(4.5, 1.62, 4.9, 1.95);
    arrow(4.5, 2.57, 4.9, 2.25);
    box(4.9, 1.45, 1.75, 1.1, "Validators", "Arithmetic · dates · regex (IBAN, VAT, currency) · cross-field · enums", H.lt2, H.dk1);
    arrow(6.65, 2.0, 7.0, 2.0);
    box(7.0, 1.45, 2.5, 1.1, "Confidence engine", "Agreement + OCR confidence + validator + self-report → isotonic calibration (held-out)", H.accent1, H.lt1);
    // row 2
    arrow(8.25, 2.55, 8.25, 3.0);
    box(7.0, 3.0, 2.5, 0.9, "Review router (threshold τ)", "Low-confidence fields → queue with evidence crop; rest auto-posts", H.accent2, H.dk1);
    arrow(7.0, 3.45, 6.65, 3.45);
    box(4.9, 3.0, 1.75, 0.9, "Validated JSON", "+ per-field confidence + audit trail (path, rules, evidence)", H.lt2, H.dk1);
    arrow(4.9, 3.45, 4.5, 3.45);
    box(2.4, 3.0, 2.1, 0.9, "Review UI", "Next.js · highlights source region · one-click accept/fix", H.lt2, H.dk1);
    arrow(2.4, 3.45, 2.05, 3.45);
    box(0.5, 3.0, 1.55, 0.9, "Eval harness", "XFUND · FUNSD · CORD · SROIE · CUAD", H.lt2, H.dk1);
    text(s, "Stack: Python 3.13, pydantic schemas, Anthropic Claude (vision + text, structured outputs), Tesseract, scikit-learn (isotonic regression), FastAPI, Next.js on Vercel. Public repo, MIT licence, one-command reproduction of every metric.", { x: 0.5, y: 4.2, w: 9.0, h: 0.75, fontSize: 11.5, color: C.text2 });
    s.addNotes("Walk left to right. Two readers never see each other's output. The validators are pure functions. The confidence engine is the only learned component on top of the LLMs, and it is trained on held-out ground truth so the number is honest.");
  }

  // 6. Confidence engine detail
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
    s.addText("What makes 0.9 mean ninety percent", { placeholder: "title" });
    const sig = [
      ["Path agreement", "Do the vision reader and the OCR reader return the same normalised value?", H.accent1],
      ["OCR evidence", "Mean Tesseract word confidence inside the field's bounding box; low on blur, skew, stamps.", H.accent1],
      ["Validator outcome", "Passed, failed or not applicable for each deterministic rule touching the field.", H.accent1],
      ["Model self-report", "The LLM's own 0–1 estimate, used as a weak feature, never as the answer.", H.accent2],
    ];
    text(s, "SIGNALS PER FIELD", { x: 0.5, y: 1.2, w: 4.4, h: 0.3, fontSize: 10, bold: true, color: "9AA5B1", charSpacing: 1 });
    for (let i = 0; i < sig.length; i++) {
      const y = 1.55 + i * 0.82;
      card(s, 0.5, y, 4.4, 0.72, { name: "signal " + i });
      s.addShape(pres.shapes.OVAL, { x: 0.65, y: y + 0.24, w: 0.24, h: 0.24, fill: { color: sig[i][2] }, line: { color: sig[i][2], width: 0 }, objectName: "dot" });
      text(s, sig[i][0], { x: 1.0, y: y + 0.06, w: 3.8, h: 0.28, fontSize: 13, bold: true, color: C.text1 });
      text(s, sig[i][1], { x: 1.0, y: y + 0.34, w: 3.8, h: 0.36, fontSize: 10.5, color: C.text2 });
    }
    text(s, "CALIBRATION AND ROUTING", { x: 5.3, y: 1.2, w: 4.2, h: 0.3, fontSize: 10, bold: true, color: "9AA5B1", charSpacing: 1 });
    card(s, 5.3, 1.55, 4.2, 3.35, { fill: H.lt2, name: "calibration card" });
    s.addText(bullets([
      "Signals are fused by a small model, then isotonic-regressed against field correctness on a held-out split, per document type.",
      "Reported on a reliability diagram with Expected Calibration Error (ECE) before and after calibration.",
      "A single threshold τ turns confidence into a routing decision; we publish the full review-rate versus accuracy curve so an operator picks their own point.",
      "Evidence travels with every field: which path, which rules fired, the crop of the page it came from.",
    ], 11.5, C.text2, 5), { x: 5.5, y: 1.7, w: 3.85, h: 3.1, isTextBox: true, margin: 0, valign: "top" });
    s.addNotes("This is the innovation slide. Each signal is cheap; the value is in fusing them and calibrating against ground truth so the number is honest. The reliability diagram and the review-rate curve are the two charts that will appear in the Round 2 update with real numbers.");
  }

  // ======================================================================
  pres.addSection({ title: "Evidence" });
  // 7. Data & evaluation plan
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
    s.addText("Public benchmarks, scored per language and per field", { placeholder: "title" });
    const rows = [
      [{ text: "Dataset", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }, { text: "Document type", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }, { text: "Languages", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }, { text: "What we measure", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }],
      ["XFUND v1.0 (Microsoft)", "Forms", "ZH, JA, ES, FR, IT, DE, PT", "Key–value extraction F1 per language"],
      ["FUNSD", "Forms", "EN", "Key–value F1; English baseline"],
      ["CORD v2 (Naver Clova)", "Receipts", "ID (Latin script)", "Field F1; arithmetic validator hit-rate"],
      ["SROIE (ICDAR 2019)", "Receipts / invoices", "EN", "Exact-match F1 on company, date, address, total"],
      ["CUAD (Atticus Project)", "Contracts", "EN", "Clause extraction F1 on parties, dates, governing law, termination"],
    ];
    s.addTable(rows, {
      x: 0.5, y: 1.2, w: 9.0, colW: [2.2, 1.6, 2.1, 3.1],
      fontSize: 10.5, color: C.text2, border: { type: "solid", pt: 0.5, color: "D5DCE4" },
      fill: { color: H.lt1 }, rowH: 0.34, valign: "middle", margin: 0.05, objectName: "datasets table",
    });
    const kp = [
      ["LuTarget", "Ablation", "Vision-only vs OCR-only vs dual-path + validators, same prompts, same schema."],
      ["LuGauge", "Calibration", "Reliability diagram, ECE, Brier score; before vs after isotonic fit, per doc type."],
      ["LuTimer", "Cost and latency", "p50 / p95 seconds per page and dollars per 1,000 documents, by path."],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05, y = 3.6;
      await iconCircle(s, x, y, 0.45, kp[i][0], H.accent1, H.lt1);
      text(s, kp[i][1], { x: x + 0.6, y: y - 0.02, w: 2.3, h: 0.28, fontSize: 13, bold: true, color: C.text1 });
      text(s, kp[i][2], { x: x + 0.6, y: y + 0.28, w: 2.35, h: 0.75, fontSize: 10.5, color: C.text2, valign: "top" });
    }
    text(s, "All datasets are public research benchmarks used under their published licences; no customer documents are used. Synthetic multilingual invoices rendered from templates cover the invoice type across the same seven languages.", { x: 0.5, y: 4.65, w: 9.0, h: 0.45, fontSize: 10, italic: true, color: "7A8696" });
    s.addNotes("Seven languages from XFUND alone, four document types across the five datasets. Every number in the Round 2 update will be reproducible from the public repo with one command.");
  }

  // 8. Demo
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
    s.addText("Demo: drop a document, watch it verify itself", { placeholder: "title" });
    // mock UI frame
    const fx = 0.5, fy = 1.25, fw = 5.4, fh = 3.7;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: fx, y: fy, w: fw, h: fh, rectRadius: 0.08, fill: { color: H.lt2 }, line: { color: "D5DCE4", width: 0.75 }, objectName: "demo frame" });
    s.addShape(pres.shapes.RECTANGLE, { x: fx + 0.2, y: fy + 0.2, w: 2.3, h: 3.3, fill: { color: H.lt1 }, line: { color: "D5DCE4", width: 0.5 }, objectName: "page preview" });
    [0.45, 0.65, 0.85, 1.15, 1.35, 1.55, 1.75, 2.15, 2.35].forEach((dy, j) => s.addShape(pres.shapes.RECTANGLE, { x: fx + 0.35, y: fy + dy, w: j % 3 === 2 ? 1.1 : 1.9, h: 0.07, fill: { color: "CBD3DC" }, line: { color: "CBD3DC", width: 0 }, objectName: "text line" }));
    s.addShape(pres.shapes.RECTANGLE, { x: fx + 0.35, y: fy + 2.75, w: 1.2, h: 0.3, fill: { color: H.accent6 }, line: { color: H.accent2, width: 1 }, objectName: "highlight region" });
    text(s, "Rechnung · DE", { x: fx + 0.35, y: fy + 0.22, w: 2, h: 0.2, fontSize: 8, bold: true, color: H.dk2 });
    const fields = [["Vendor", "Müller GmbH", "0.98", H.accent1], ["Invoice no.", "RE-2026-0412", "0.96", H.accent1], ["Date", "03.11.2026", "0.95", H.accent1], ["Net", "1 240,00 EUR", "0.97", H.accent1], ["VAT 19%", "235,60 EUR", "0.97", H.accent1], ["Total", "1 475,60 EUR", "0.99", H.accent1], ["IBAN", "DE89 3704 ···· 3000", "0.62", H.accent2]];
    fields.forEach((f, i) => {
      const y = fy + 0.25 + i * 0.44;
      text(s, f[0], { x: fx + 2.7, y, w: 0.9, h: 0.3, fontSize: 9.5, color: H.dk2, valign: "middle" });
      text(s, f[1], { x: fx + 3.6, y, w: 1.15, h: 0.3, fontSize: 9.5, bold: true, color: H.dk1, valign: "middle" });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: fx + 4.75, y: y + 0.04, w: 0.45, h: 0.22, rectRadius: 0.11, fill: { color: f[3] }, line: { color: f[3], width: 0 }, objectName: "conf" });
      text(s, f[2], { x: fx + 4.75, y: y + 0.04, w: 0.45, h: 0.22, fontSize: 8, bold: true, color: H.lt1, align: "center", valign: "middle" });
    });
    text(s, "1 field routed to review: IBAN (OCR evidence low on stamp overlap)", { x: fx + 2.7, y: fy + 3.35, w: 2.6, h: 0.3, fontSize: 8.5, italic: true, color: H.accent3 });
    // right column
    const pts = [
      ["LuUpload", "Upload any PDF or photo; sample documents in seven languages provided."],
      ["LuSplit", "Side-by-side view of what each reader saw and where they disagreed."],
      ["LuBadgeCheck", "Validator panel: which rules fired, which passed, in plain words."],
      ["LuSlidersHorizontal", "Threshold slider: move τ and watch review load and expected accuracy change live."],
      ["LuDownload", "Export validated JSON or CSV with the audit trail attached."],
    ];
    for (let i = 0; i < pts.length; i++) {
      const y = 1.3 + i * 0.72;
      await iconCircle(s, 6.2, y, 0.42, pts[i][0], H.accent4, H.lt1);
      text(s, pts[i][1], { x: 6.75, y: y - 0.02, w: 2.75, h: 0.62, fontSize: 11, color: C.text2, valign: "middle" });
    }
    s.addNotes("The demo is hosted and linked in the submission. The point of the UI is to make the trust story visible: readers, rules, and the one field that genuinely needs a human.");
  }

  // ======================================================================
  pres.addSection({ title: "Impact" });
  // 9. Impact & feasibility
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Impact" });
    s.addText("Impact: fewer eyes per document, no silent errors", { placeholder: "title" });
    const left = [
      ["LuBuilding2", "Who benefits", "Accounts-payable and procurement teams, legal operations, and BPOs serving multilingual markets (India, EU, South-East Asia, LATAM)."],
      ["LuCoins", "Economics", "Review effort scales with low-confidence fields, not with document volume. Cost per document is dominated by one or two model calls per page and is reported in the evaluation."],
      ["LuTrendingUp", "Scalability", "Stateless pipeline; each stage is independently parallel. New document types are a schema and a validator file, not a retrained model."],
    ];
    for (let i = 0; i < 3; i++) {
      const y = 1.25 + i * 1.2;
      await iconCircle(s, 0.5, y, 0.5, left[i][0], H.accent1, H.lt1);
      text(s, left[i][1], { x: 1.15, y: y - 0.03, w: 3.9, h: 0.3, fontSize: 14, bold: true, color: C.text1 });
      text(s, left[i][2], { x: 1.15, y: y + 0.3, w: 3.9, h: 0.85, fontSize: 11, color: C.text2, valign: "top" });
    }
    card(s, 5.5, 1.25, 4.0, 3.65, { fill: H.lt2, name: "responsible ai card" });
    await iconCircle(s, 5.7, 1.45, 0.45, "LuShieldCheck", H.accent2, H.dk1);
    text(s, "Responsible by design", { x: 6.3, y: 1.47, w: 3.0, h: 0.4, fontSize: 14, bold: true, color: C.text1, valign: "middle" });
    s.addText(bullets([
      "Human stays in the loop exactly where the system is unsure; no autonomous posting below τ.",
      "Every field carries its evidence, so decisions are auditable after the fact.",
      "Documents are processed in memory and never used for training; PII fields can be masked in exports.",
      "Calibration is reported per language and per document type to expose, not hide, weaker segments.",
      "Public benchmarks, public code, public numbers.",
    ], 11, C.text2, 5), { x: 5.7, y: 2.0, w: 3.6, h: 2.8, isTextBox: true, margin: 0, valign: "top" });
    s.addNotes("Impact is operational: the same team handles more documents in more languages with fewer errors reaching the ledger. Responsible AI is not a slide; it is the routing rule.");
  }

  // 10. Roadmap
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Impact" });
    s.addText("Roadmap: pipeline, then evidence, then production", { placeholder: "title" });
    const phases = [
      ["Round 1 · 10 Nov", "Working pipeline", ["Both extraction paths and validators", "Four document-type schemas", "Hosted demo with sample documents", "Eval harness wired to XFUND, CORD, SROIE"], H.accent1],
      ["Round 2 · by 25 Nov", "Evidence", ["Per-language F1 and ablations", "Calibration curves and ECE", "Review-rate vs accuracy curve", "Cost and latency per page"], H.accent4],
      ["Beyond", "Production", ["Active learning from reviewer corrections", "Open-weights model path for on-prem", "Connectors: email inbox, SAP, Tally", "Table and handwriting extraction"], H.dk2],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05, y = 1.3, w = 2.9, h = 3.6;
      card(s, x, y, w, h, { name: "phase " + i });
      s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.2, w: 0.42, h: 0.42, fill: { color: phases[i][4] }, line: { color: phases[i][4], width: 0 }, objectName: "num" });
      text(s, String(i + 1), { x: x + 0.2, y: y + 0.2, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: H.lt1, align: "center", valign: "middle" });
      text(s, phases[i][0], { x: x + 0.75, y: y + 0.2, w: w - 0.9, h: 0.22, fontSize: 10, bold: true, color: "9AA5B1", charSpacing: 1 });
      text(s, phases[i][1], { x: x + 0.75, y: y + 0.4, w: w - 0.9, h: 0.3, fontSize: 15, bold: true, color: C.text1 });
      s.addText(bullets(phases[i][2], 11.5, C.text2, 6), { x: x + 0.2, y: y + 0.95, w: w - 0.4, h: 2.5, isTextBox: true, margin: 0, valign: "top" });
    }
    s.addNotes("Honest about what exists at Round 1 and what Round 2 adds. The production items are the obvious asks from an enterprise buyer and show the path beyond the hackathon.");
  }

  // ======================================================================
  pres.addSection({ title: "Team" });
  // 11. Team + close
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Team" });
    text(s, "TEAM AND CONTRIBUTIONS", { x: 0.6, y: 0.6, w: 8, h: 0.3, fontSize: 11, bold: true, color: H.accent2, charSpacing: 2 });
    s.addShape(pres.shapes.OVAL, { x: 0.6, y: 1.15, w: 1.1, h: 1.1, fill: { color: H.accent1 }, line: { color: H.accent1, width: 0 }, objectName: "avatar" });
    text(s, "RN", { x: 0.6, y: 1.15, w: 1.1, h: 1.1, fontSize: 28, bold: true, color: H.lt1, align: "center", valign: "middle" });
    text(s, "Rishav Naskar", { x: 1.95, y: 1.15, w: 6, h: 0.45, fontSize: 24, bold: true, color: H.lt1 });
    text(s, "Software engineer · AI agents, LLM applications and full-stack web · Solo entrant", { x: 1.95, y: 1.6, w: 7, h: 0.35, fontSize: 13, color: H.accent5 });
    s.addText(bullets([
      "Problem framing, architecture and schema design",
      "Dual-path extraction pipeline, validators and confidence engine",
      "Evaluation harness, calibration and reporting",
      "Review UI, hosted demo, documentation and video",
    ], 13, H.lt1, 5), { x: 1.95, y: 2.05, w: 7, h: 1.6, isTextBox: true, margin: 0, valign: "top" });
    text(s, "Third-party components acknowledged in the repository: XFUND, FUNSD, CORD, SROIE and CUAD datasets; Tesseract OCR; Anthropic Claude models; pypdfium2; scikit-learn; FastAPI; Next.js. All code released under the MIT licence.", { x: 0.6, y: 3.85, w: 8.6, h: 0.55, fontSize: 10, color: "9AA5B1" });
    text(s, "Lingua Ledger  ·  rishavnaskar.r@gmail.com  ·  repo and demo links in the submission form", { x: 0.6, y: 4.55, w: 8.4, h: 0.3, fontSize: 12, color: H.lt1 });
    s.addNotes("Solo entry. Contributions listed per the submission rules. Links to the repository and hosted demo are in the Devpost and Unstop forms.");
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
