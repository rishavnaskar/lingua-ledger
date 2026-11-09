// Builds the DataNova 2026 Round-1 deck for Lingua Ledger (DN-AI-01).
// Usage: node build_deck.js [out.pptx]
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const Lu = require("react-icons/lu");
const path = require("path");
const { applyTheme } = require(process.env.PPTX_SKILL_DIR + "/scripts/apply_theme.js");

const fs = require("fs");

const OUT = process.argv[2] || path.join(__dirname, "LinguaLedger-DataNova2026-Round1.pptx");
const ART = path.join(__dirname, "..", "artifacts");
const SUMMARY = fs.existsSync(path.join(ART, "summary.json"))
  ? JSON.parse(fs.readFileSync(path.join(ART, "summary.json"), "utf8"))
  : null;
const chart = (name) => (fs.existsSync(path.join(ART, `${name}.png`)) ? path.join(ART, `${name}.png`) : null);
const pct = (x, d = 0) => (x == null ? "n/a" : `${(x * 100).toFixed(d)}%`);

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
      { text: "Self-checking extraction for multilingual business documents. ", options: { color: H.accent5 } },
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
    s.addNotes("Lingua Ledger is our entry for DN-AI-01. The main takeaway: document extraction works in demos, but fails in production because no one trusts it. We make confidence scores honest and prove it with data.");
  }

  // ======================================================================
  pres.addSection({ title: "Problem" });
  // 2. Problem
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
    s.addText("Every layout arrives, but trust does not", { placeholder: "title" });
    text(s, "Official challenge DN-AI-01: extract, classify and structure information from multilingual invoices, contracts and forms with varying layouts and quality, and output structured, validated data with confidence scores.", { x: 0.5, y: 1.15, w: 9.0, h: 0.6, fontSize: 13, italic: true, color: C.text2 });
    const cols = [
      ["LuLanguages", "Multilingual by default", "Teams in India, the EU and South-East Asia handle invoices and contracts in 5 to 10 languages, often mixed on one page."],
      ["LuLayoutTemplate", "Layouts keep changing", "Template OCR breaks on new vendors. LLMs read anything, but they easily make up a VAT number when a scan is blurry."],
      ["LuUserX", "100% review or errors", "Without knowing what is accurate, teams must recheck every field or risk costly ledger errors."],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05, y = 1.95, w = 2.9, h = 2.95;
      card(s, x, y, w, h, { name: "problem card " + i });
      await iconCircle(s, x + 0.2, y + 0.2, 0.55, cols[i][0], H.accent4, H.lt1);
      text(s, cols[i][1], { x: x + 0.2, y: y + 0.9, w: w - 0.4, h: 0.5, fontSize: 15, bold: true, color: C.text1 });
      text(s, cols[i][2], { x: x + 0.2, y: y + 1.4, w: w - 0.4, h: 1.45, fontSize: 12, color: C.text2, valign: "top" });
    }
    s.addNotes("This problem comes straight from DN-AI-01. The hard part is not reading text; it is knowing which of the 40 extracted fields are safe to post without human review.");
  }

  // 3. Insight
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Problem" });
    s.addText("Confidence scores you can actually trust", { placeholder: "title" });
    const rows = [
      ["Template OCR", "Fragile; breaks on new layouts", "Basic word-level OCR confidence only", "Humans must check every exception", "A7B0BC"],
      ["Prompt-and-pray LLM", "Reads almost anything", "Self-reported, uncalibrated, and often wrong", "All or nothing", "A7B0BC"],
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
    text(s, "Our main metric: at a target field accuracy (like 98%), what share of fields still needs a human? Lower is better, and we measure it directly.", { x: 0.5, y: 4.6, w: 9.0, h: 0.45, fontSize: 13, italic: true, color: H.accent4 });
    s.addNotes("Current tools have big weaknesses. We do not just claim better reading; we deliver trustworthy output and prove it by measuring human review rates at a fixed accuracy target.");
  }

  // ======================================================================
  pres.addSection({ title: "Solution" });
  // 4. Solution overview
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
    s.addText("Read twice, validate, score and route", { placeholder: "title" });
    const steps = [
      ["LuScanLine", "Ingest and classify", "Drop in a PDF, scan or photo. We render pages and detect the language and document type (invoice, receipt, form, contract)."],
      ["LuCopy", "Extract twice independently", "Path A: a vision model reads the page against a JSON schema. Path B: multilingual OCR text + layout with a text model."],
      ["LuShieldCheck", "Check with strict rules", "Line items must sum, tax math must add up, dates must parse, and IBAN / VAT formats must match. Every rule is clear and explainable."],
      ["LuGauge", "Score confidence per field", "We combine reader agreement, OCR confidence, rule results and model estimates, then calibrate them on held-out test data."],
      ["LuUserCheck", "Route only doubtful fields", "Fields below the threshold go to a review queue with source crops highlighted. Everything else posts automatically with an audit trail."],
    ];
    for (let i = 0; i < steps.length; i++) {
      const y = 1.2 + i * 0.78;
      await iconCircle(s, 0.5, y + 0.05, 0.5, steps[i][0], i === 4 ? H.accent2 : H.accent1, H.lt1);
      text(s, steps[i][1], { x: 1.2, y: y, w: 2.6, h: 0.6, fontSize: 15, bold: true, color: C.text1, valign: "middle" });
      text(s, steps[i][2], { x: 3.85, y: y, w: 5.65, h: 0.62, fontSize: 12, color: C.text2, valign: "middle" });
    }
    s.addNotes("Five stages. The key innovations are extracting twice through separate paths and calibrating scores against held-out ground truth. The rest is solid engineering that most hackathons skip.");
  }

  // 5. Architecture
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
    s.addText("Two separate readers, one strict judge", { placeholder: "title" });
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
    text(s, "Stack: Python 3.13, pydantic schemas, Google Gemini (gemini-3.5-flash-lite for vision, text and classification, structured JSON output; switchable to Claude), Tesseract, scikit-learn (isotonic regression), FastAPI, Next.js on Vercel. Public repo, MIT licence, one command reproduces every metric.", { x: 0.5, y: 4.2, w: 9.0, h: 0.75, fontSize: 11.5, color: C.text2 });
    s.addNotes("Look from left to right. The two readers never see each other's work. The validators use clear deterministic rules. The confidence engine is trained on held-out ground truth so the scores stay honest.");
  }

  // 6. Confidence engine detail
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Solution" });
    s.addText("What makes 0.9 mean ninety percent", { placeholder: "title" });
    const sig = [
      ["Both readers agree", "Do the vision reader and the OCR reader return the exact same value?", H.accent1],
      ["Clear OCR evidence", "Average Tesseract word confidence inside the field box; drops on blur, skew or stamps.", H.accent1],
      ["Rule check outcome", "Passed, failed or not applicable for every deterministic rule checked against the field.", H.accent1],
      ["Raw model estimate", "The LLM's own 0 to 1 estimate, used as a small signal, never as the final answer.", H.accent2],
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
      "Signals combine through a small model, then calibrate against field accuracy on held-out data per document type.",
      "Shown on a reliability diagram with Expected Calibration Error (ECE) before and after calibration.",
      "A single threshold τ controls routing; operators use the curve to pick their own balance between accuracy and review load.",
      "Every field carries proof: which path found it, which rules passed, and the exact image crop.",
    ], 11.5, C.text2, 5), { x: 5.5, y: 1.7, w: 3.85, h: 3.1, isTextBox: true, margin: 0, valign: "top" });
    s.addNotes("This slide shows where our real innovation happens. Each signal is cheap, but the real power comes from fusing them and calibrating against ground truth so our numbers stay honest. Two slides later, the reliability diagram and review-rate curve show the result on real data.");
  }

  // ======================================================================
  pres.addSection({ title: "Evidence" });
  // 7. Data & evaluation plan
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
    s.addText("Public benchmarks tested by language and field", { placeholder: "title" });
    const rows = [
      [{ text: "Dataset", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }, { text: "Document type", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }, { text: "Languages", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }, { text: "What we measure", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } }],
      ["XFUND v1.0 (Microsoft)", "Forms", "ZH, JA, ES, FR, IT, DE, PT", "Key-value extraction F1 per language"],
      ["FUNSD", "Forms", "EN", "Key-value F1; English baseline"],
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
    text(s, "All datasets are public research benchmarks under open licences; no customer data is used. Synthetic multilingual invoices cover the invoice category across the same seven languages.", { x: 0.5, y: 4.65, w: 9.0, h: 0.45, fontSize: 10, italic: true, color: "7A8696" });
    s.addNotes("We cover nine languages across five datasets, synthetic invoices, and four document types. Every number on the next three slides is reproducible from our public repo with one command.");
  }

  // Results (only when the evaluation has been run)
  if (SUMMARY && SUMMARY.documents) {
    const f1 = SUMMARY.f1 || {};
    const stat = (s, x, y, big, label, color, w = 2.1, size = 30) => {
      text(s, big, { x, y, w, h: 0.65, fontSize: size, bold: true, color: color || H.accent1 });
      text(s, label, { x, y: y + 0.65, w, h: 0.5, fontSize: 10.5, color: C.text2, valign: "top" });
    };
    const datasets = ["xfund", "funsd", "cord", "sroie", "synth_invoices", "cuad"];
    const names = { xfund: "XFUND forms (7 langs)", funsd: "FUNSD forms (EN)", cord: "CORD receipts (ID)",
      sroie: "SROIE receipts (EN)", synth_invoices: "Synthetic invoices (7 langs)", cuad: "CUAD contracts (EN)" };

    // Results overview
    {
      const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
      s.addText(`Results on ${SUMMARY.documents} public benchmark documents`, { placeholder: "title" });
      const rows = [[
        { text: "Benchmark", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } },
        { text: "Vision only", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } },
        { text: "OCR + text only", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } },
        { text: "Both + validators", options: { bold: true, color: H.lt1, fill: { color: H.accent4 } } },
      ]];
      for (const d of datasets) {
        if (f1[`${d}/all/merged`] == null) continue;
        rows.push([names[d], pct(f1[`${d}/all/vision`]), pct(f1[`${d}/all/ocr_text`]),
          { text: pct(f1[`${d}/all/merged`]), options: { bold: true, color: H.accent1 } }]);
      }
      s.addTable(rows, { x: 0.5, y: 1.25, w: 5.6, colW: [2.3, 1.1, 1.1, 1.1], fontSize: 11, color: C.text2,
        border: { type: "solid", pt: 0.5, color: "D5DCE4" }, fill: { color: H.lt1 }, rowH: 0.36, valign: "middle",
        margin: 0.05, objectName: "results table" });
      if (chart("f1_by_language")) {
        s.addImage({ path: chart("f1_by_language"), x: 6.3, y: 1.25, w: 3.3, h: 1.76, objectName: "f1 by language" });
      }
      const cls = SUMMARY.classification || {};
      stat(s, 6.3, 3.3, pct(cls.doc_type_acc), "document type detected correctly", H.accent4, 1.55);
      stat(s, 8.0, 3.3, pct(cls.language_acc), "language detected correctly", H.accent4, 1.55);
      text(s, "Field F1 scored against published ground truth. Forms: key-value pairs. Receipts and invoices: every labeled field and line item. Contracts: parties, dates, governing law. Same prompts and schema throughout.",
        { x: 0.5, y: 4.3, w: 5.6, h: 0.7, fontSize: 10, italic: true, color: "7A8696" });
      s.addNotes("Every result comes from one command in the public repo. The last column is the full pipeline; the previous two show each reader running alone.");
    }

    // Calibration and review load
    {
      const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
      s.addText("Honest confidence creates a clear review budget", { placeholder: "title" });
      const cal = SUMMARY.calibration || {};
      const rev = SUMMARY.review || {};
      if (chart("reliability")) s.addImage({ path: chart("reliability"), x: 0.5, y: 1.2, w: 4.4, h: 2.08, objectName: "reliability" });
      if (chart("review_curve")) s.addImage({ path: chart("review_curve"), x: 5.1, y: 1.2, w: 4.4, h: 2.64, objectName: "review curve" });
      stat(s, 0.5, 3.5, cal.ece_calibrated != null ? `${cal.ece_raw.toFixed(3)} → ${cal.ece_calibrated.toFixed(3)}` : "n/a",
        "expected calibration error, raw score → calibrated (lower is better)", H.accent1, 2.2, 24);
      stat(s, 2.8, 3.5, pct(cal.field_accuracy), "fields correct with no human review at all", H.accent4);
      const r98 = rev.review_rate_at_98pct_accuracy;
      stat(s, 5.1, 3.95, pct(r98), "of fields need a human to reach 98% accuracy on what posts automatically", H.accent2);
      const r95 = rev.review_rate_at_95pct_accuracy;
      stat(s, 7.4, 3.95, pct(r95), "of fields need a human to reach 95% accuracy", H.accent2);
      s.addNotes("On the left is a reliability diagram scored with two-fold cross-fitting, so every field is scored by a calibrator that never saw its document. On the right is the operating curve an operator actually uses. The amber numbers are the headline, showing how much human work buys how much accuracy.");
    }

    // Cost and latency
    {
      const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
      s.addText("What it costs to run", { placeholder: "title" });
      const lat = SUMMARY.latency_s || {};
      const tok = SUMMARY.tokens || {};
      const cost = SUMMARY.cost_usd || {};
      if (chart("ablation")) s.addImage({ path: chart("ablation"), x: 0.5, y: 1.2, w: 5.4, h: 2.62, objectName: "ablation" });
      const rp50 = lat.reader_p50 != null ? lat.reader_p50 : lat.p50;
      stat(s, 6.3, 1.25, rp50 != null ? `${rp50.toFixed(1)} s` : "n/a", "median model reading time per document, both readers in parallel, Free Tier rate limits included", H.accent4, 3.2);
      stat(s, 6.3, 2.55, lat.p50 != null ? `${lat.p50.toFixed(1)} s` : "n/a", "median end to end, with OCR, classification and throttling waits", H.accent4, 3.2);
      stat(s, 6.3, 3.85, cost.per_1000_docs != null ? `$${cost.per_1000_docs.toFixed(2)}` : "n/a", "model cost per 1,000 documents at list prices", H.accent1, 3.2);
      text(s, `Tokens per document: about ${tok.per_doc_input || "n/a"} in, ${tok.per_doc_output || "n/a"} out across both readers. Review effort scales with low-confidence fields, not document volume.`,
        { x: 0.5, y: 4.0, w: 5.4, h: 0.9, fontSize: 11, color: C.text2 });
      s.addNotes("The left shows each reader alone versus the full pair with validators. The right shows standard list pricing without batching or caching, giving a realistic upper bound.");
    }
  }

  // 8. Demo
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Evidence" });
    s.addText("Demo: drop a file, watch it self-verify", { placeholder: "title" });
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
      ["LuUpload", "Upload any PDF or photo; sample files in seven languages are ready to test."],
      ["LuSplit", "Side-by-side view showing what each reader saw and where they disagreed."],
      ["LuBadgeCheck", "Validator panel: see which rules ran and which passed in plain words."],
      ["LuSlidersHorizontal", "Threshold slider: move τ and watch review workload and expected accuracy update live."],
      ["LuDownload", "Export verified JSON or CSV with a complete audit trail attached."],
    ];
    for (let i = 0; i < pts.length; i++) {
      const y = 1.3 + i * 0.72;
      await iconCircle(s, 6.2, y, 0.42, pts[i][0], H.accent4, H.lt1);
      text(s, pts[i][1], { x: 6.75, y: y - 0.02, w: 2.75, h: 0.62, fontSize: 11, color: C.text2, valign: "middle" });
    }
    s.addNotes("The hosted demo is linked in the submission. The interface makes trust visible: two readers, clear rules, and only the fields that truly need human eyes.");
  }

  // ======================================================================
  pres.addSection({ title: "Impact" });
  // 9. Impact & feasibility
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Impact" });
    s.addText("Fewer manual reviews, zero silent errors", { placeholder: "title" });
    const left = [
      ["LuBuilding2", "Who benefits", "Finance, accounts-payable, procurement and legal teams, plus BPOs working across India, the EU, South-East Asia and LATAM."],
      ["LuCoins", "Cost savings", "Review work scales with low-confidence fields, not document count. Document cost is just one or two model calls per page, as shown in our evaluation."],
      ["LuTrendingUp", "Easy scaling", "Stateless pipeline where every step runs in parallel. Supporting new document types just takes a schema and a rule file, not a new model."],
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
      "Humans step in only when confidence is low; nothing posts automatically below τ.",
      "Every field carries clear evidence, making every decision easy to audit later.",
      "Documents stay in memory and are never used for training; PII fields can be masked on export.",
      "Calibration is reported by language and document type to highlight, not hide, weaker areas.",
      "Built on public benchmarks, public code and verifiable numbers.",
    ], 11, C.text2, 5), { x: 5.7, y: 2.0, w: 3.6, h: 2.8, isTextBox: true, margin: 0, valign: "top" });
    s.addNotes("The impact is real: teams process more documents in more languages with fewer mistakes reaching the ledger. Responsible AI is not a buzzword; it is our core routing rule.");
  }

  // 10. Roadmap
  {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Impact" });
    s.addText("Roadmap: pipeline, evidence, then production", { placeholder: "title" });
    const phases = [
      ["Round 1 \u00b7 10 Nov", "Working pipeline with evidence", ["Runs both readers, validators, calibration, and review routing", "198 public benchmark documents, 9 languages; one command, all numbers", "Live hosted demo with sample documents", "225 unit tests under an MIT licence"], H.accent1],
      ["Round 2 \u00b7 by 25 Nov", "Better readers, same pipeline", ["Bigger Gemini, Claude readers; one environment variable; compared cost, accuracy", "Japanese and Chinese forms: layout-aware prompts, key normalisation", "Lenient form scoring right next to the strict one", "Corrections from the review UI feed the calibrator"], H.accent4],
      ["Beyond Round 2", "Moving into production", ["Active learning straight from reviewer corrections", "Open-weights model path for on-prem use", "Connectors for email inbox, SAP, and Tally", "Full table and handwriting extraction support"], H.dk2],
    ];
    for (let i = 0; i < 3; i++) {
      const x = 0.5 + i * 3.05, y = 1.3, w = 2.9, h = 3.6;
      card(s, x, y, w, h, { name: "phase " + i });
      s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.2, w: 0.42, h: 0.42, fill: { color: phases[i][4] }, line: { color: phases[i][4], width: 0 }, objectName: "num" });
      text(s, String(i + 1), { x: x + 0.2, y: y + 0.2, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: H.lt1, align: "center", valign: "middle" });
      text(s, phases[i][0], { x: x + 0.75, y: y + 0.2, w: w - 0.9, h: 0.22, fontSize: 10, bold: true, color: "9AA5B1", charSpacing: 1 });
      text(s, phases[i][1], { x: x + 0.75, y: y + 0.42, w: w - 0.9, h: 0.62, fontSize: 14, bold: true, color: C.text1, valign: "top" });
      s.addText(bullets(phases[i][2], 11.5, C.text2, 6), { x: x + 0.2, y: y + 1.15, w: w - 0.4, h: 2.35, isTextBox: true, margin: 0, valign: "top" });
    }
    s.addNotes("Round 1 already includes the evidence we promised. Round 2 focuses on boosting quality with bigger readers and fixing our weakest languages. Everything in production covers the obvious features enterprise buyers ask for.");
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
    text(s, "Third-party components acknowledged in the repository: XFUND, FUNSD, CORD, SROIE and CUAD datasets; Tesseract OCR; Google Gemini API; pypdfium2; scikit-learn; FastAPI; Next.js. All code released under the MIT licence.", { x: 0.6, y: 3.85, w: 8.6, h: 0.55, fontSize: 10, color: "9AA5B1" });
    text(s, "Lingua Ledger  ·  rishavnaskar.r@gmail.com  ·  repo and demo links in the submission form", { x: 0.6, y: 4.55, w: 8.4, h: 0.3, fontSize: 12, color: H.lt1 });
    s.addNotes("Solo project. All work is detailed per the submission rules. Links to the code repository and live demo are in the Devpost and Unstop forms.");
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
