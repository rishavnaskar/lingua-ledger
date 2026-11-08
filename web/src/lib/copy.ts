const plural = (n: number, one: string, many: string) => (n === 1 ? `1 ${one}` : `${n} ${many}`);

export const copy = {
  site: {
    name: "Lingua Ledger",
    tag: "DataNova 2026 · DN-AI-01",
    description:
      "Multilingual document extraction that checks its own work. Every field gets a calibrated confidence, and only the doubtful ones go to a person.",
    nav: { workbench: "Workbench", evidence: "Evidence", about: "About" },
    navLabel: "Main",
    footer: "Lingua Ledger. Built for DataNova 2026, problem statement DN-AI-01.",
  },

  common: {
    empty: "empty",
    none: "none",
    notAvailable: "n/a",
  },

  docTypes: {
    invoice: "Invoice",
    receipt: "Receipt",
    form: "Form",
    contract: "Contract",
  } as Record<string, string>,

  workbench: {
    heading: "Workbench",
    intro:
      "Drop an invoice, receipt, form or contract in any language. Each field comes back with a confidence score, and the doubtful ones are flagged for review.",
    input: {
      title: "Document",
      dropTitle: "Drop a file here",
      dropHint: "PDF, PNG or JPG, up to 15 MB. Any language.",
      dropBrowse: "Choose a file",
      dropActive: "Release to read it",
      dropCompact: "Drop another file, or click to choose one",
      dropLabel: "Upload a document",
      wrongType: "Only PDF, PNG and JPG files are supported.",
      tooLarge: "That file is larger than 15 MB.",
    },
    samples: {
      title: "Sample documents",
      loading: "Loading samples",
      empty: "No samples on this server yet.",
      failed: "Could not load samples from the API.",
    },
    options: {
      title: "Options",
      docType: "Document type",
      docTypeAuto: "Detect automatically",
      docTypeNote: "Applies to uploads. Samples already know their type.",
      threshold: "Review threshold",
      thresholdNote: "Fields scoring below this go to review.",
    },
    idle: {
      title: "Pick a document to start",
      body: "The document is read twice, by a vision model and by OCR plus a text model. Validators check the numbers and formats, the signals are combined into one calibrated confidence per field, and anything below the threshold is flagged for a person.",
      points: [
        "Every value shows where it came from and why it was trusted.",
        "Boxes on the page show where each value was found.",
        "Move the threshold to trade review effort against accuracy.",
      ],
    },
    steps: [
      { label: "Reading pages", detail: "Turning each page into an image" },
      { label: "Vision reader", detail: "A vision model reads the page image" },
      { label: "OCR + text reader", detail: "OCR text goes to a separate text model" },
      { label: "Validators", detail: "Arithmetic, dates, IBAN and VAT formats" },
      { label: "Confidence", detail: "Signals combined and calibrated per field" },
      { label: "Routing", detail: "Low-confidence fields sent to review" },
    ],
    progress: {
      title: (name: string) => `Reading ${name}`,
      elapsed: (s: string) => `${s} elapsed`,
      note: "Both readers run at the same time. Most of the wait is spent there.",
    },
    error: {
      title: "That did not work",
      retry: "Try again",
      network: (url: string) =>
        `Could not reach the API at ${url}. Check that the backend is running and that NEXT_PUBLIC_API_URL points to it.`,
      server: (status: number, detail: string | null) =>
        detail ? `The server answered ${status}: ${detail}` : `The server answered ${status}.`,
    },
    result: {
      pages: (n: number) => plural(n, "page", "pages"),
      latency: (s: string) => `read in ${s}`,
      typeConfidence: (c: string) => `type confidence ${c}`,
      headline: (review: number, total: number) =>
        total === 0
          ? "No fields were found"
          : review === 0
            ? `All ${total} fields accepted`
            : `${review} of ${total} fields need review`,
      subline: (accepted: number, threshold: string) =>
        `${accepted} accepted automatically at threshold ${threshold}.`,
      threshold: "Review threshold",
      thresholdHint: "Moving it re-routes fields instantly. Nothing is re-run.",
      exportJson: "Download JSON",
      exportCsv: "Download CSV",
      accepted: "Accepted",
      needsReview: "Needs review",
      newDocument: "Read another document",
    },
    viewer: {
      title: "Document",
      showBoxes: "Show boxes",
      pageLabel: (i: number, n: number) => `Page ${i} of ${n}`,
      unlocated: (n: number) =>
        n === 1 ? "1 field could not be located on the page." : `${n} fields could not be located on the page.`,
      alt: (i: number) => `Page ${i} of the document`,
      reading: "Reading",
      noPreview: "Preview appears when reading finishes.",
    },
    fields: {
      title: "Fields",
      filterAll: "All",
      filterReview: "Needs review",
      filterLabel: "Filter fields",
      showEmpty: (n: number) => `Show ${plural(n, "empty field", "empty fields")}`,
      hideEmpty: "Hide empty fields",
      columns: { field: "Field", value: "Value", confidence: "Confidence", evidence: "Evidence" },
      none: "No fields to show.",
      noneReview: "Nothing needs review at this threshold.",
      expand: "Show details",
      collapse: "Hide details",
      evidence: {
        agree: "Readers agree",
        disagree: "Readers disagree",
        single: "One reader",
        ocr: (c: string) => `OCR ${c}`,
        noOcr: "Not found by OCR",
        pass: "Checks pass",
        fail: "Check failed",
        na: "No check",
      },
      detail: {
        readers: "What each reader saw",
        vision: "Vision reader",
        ocr: "OCR + text reader",
        kept: "kept",
        missing: "nothing",
        signals: "Signals",
        raw: "Raw score",
        calibrated: "Calibrated confidence",
        selfConf: "Model self-confidence",
        ocrConf: "OCR word confidence",
        location: "Location",
        locatedOn: (p: number) => `page ${p}`,
        notLocated: "not found on the page",
        rules: "Rules that touch this field",
        noRules: "No rule checks this field.",
      },
      listItem: { line_items: "Line item", fields: "Field", parties: "Party" } as Record<string, string>,
      names: {
        vendor_name: "Vendor",
        vendor_address: "Vendor address",
        vendor_tax_id: "Vendor tax ID",
        customer_name: "Customer",
        invoice_number: "Invoice number",
        invoice_date: "Invoice date",
        due_date: "Due date",
        currency: "Currency",
        subtotal: "Subtotal",
        tax_rate: "Tax rate (%)",
        tax_amount: "Tax amount",
        total: "Total",
        iban: "IBAN",
        payment_terms: "Payment terms",
        merchant_name: "Merchant",
        merchant_address: "Merchant address",
        date: "Date",
        time: "Time",
        service_charge: "Service charge",
        discount: "Discount",
        cash_paid: "Cash paid",
        change: "Change",
        payment_method: "Payment method",
        title: "Title",
        key: "Label",
        value: "Value",
        description: "Description",
        quantity: "Quantity",
        unit_price: "Unit price",
        document_name: "Document name",
        agreement_date: "Agreement date",
        effective_date: "Effective date",
        expiration_date: "Expiration date",
        governing_law: "Governing law",
        renewal_term: "Renewal term",
        notice_period_to_terminate: "Notice period",
        contract_type: "Contract type",
        line_items: "Line items",
        fields: "Fields",
        parties: "Parties",
      } as Record<string, string>,
    },
    validators: {
      title: "Validators",
      summary: (pass: number, fail: number, na: number) =>
        [`${pass} passed`, `${fail} failed`, na ? `${na} not applicable` : ""].filter(Boolean).join(" · "),
      empty: "No rules ran for this document.",
      status: { pass: "Pass", fail: "Fail", na: "Not applicable" },
      names: {} as Record<string, string>,
    },
    readers: {
      title: "Readers",
      names: { vision: "Vision reader", ocr_text: "OCR + text reader" } as Record<string, string>,
      descriptions: {
        vision: "Reads the page image directly.",
        ocr_text: "Reads OCR text only, without the image.",
      } as Record<string, string>,
      latency: "Latency",
      tokensIn: "Input tokens",
      tokensOut: "Output tokens",
      fieldsFound: "Fields found",
      notRun: "Not run for this document.",
      failed: "This reader failed",
      agreement: (a: number, n: number) => `Readers agree on ${a} of ${n} fields`,
      onlyOne: (n: number) => `${plural(n, "field", "fields")} found by only one reader.`,
      differences: "Where they differ",
      noDifferences: "No disagreements.",
      more: (n: number) => `and ${n} more`,
    },
  },

  metrics: {
    heading: "Evidence",
    intro:
      "Results from the offline evaluation on public benchmarks. Every number here is reproducible from the repository.",
    loading: "Loading results",
    failedTitle: "Could not load results",
    empty: {
      title: "No evaluation results yet",
      body: "The backend has not published a summary. Run the evaluation on the backend, then reload this page.",
      command: "uv run ll eval run && uv run ll eval report",
    },
    cards: {
      documents: {
        label: "Documents evaluated",
        sub: (failed: number) => (failed ? `${failed} could not be processed` : "All processed"),
      },
      accuracy: {
        label: "Field accuracy",
        sub: (n: string) => `On ${n} held-out fields, before any review`,
      },
      ece: {
        label: "Calibration error (ECE)",
        sub: "Raw score to calibrated confidence. Lower is better.",
      },
      review98: {
        label: "Review rate at 98% accuracy",
        sub: (t: string) => `Threshold ${t}. Everything else posts automatically.`,
        notReached: "Not reached",
        notReachedSub: "No threshold reached 98% accuracy on this run.",
      },
      latency: { label: "Median latency", sub: (p95: string) => `p95 ${p95}, per document` },
      cost: { label: "Cost per 1,000 documents", sub: (total: string) => `${total} for the whole evaluation` },
    },
    details: {
      title: "More numbers",
      docTypeAcc: "Document type accuracy",
      languageAcc: "Language detection accuracy",
      brier: "Brier score, raw to calibrated",
      review95: "Review rate at 95% accuracy",
      atThreshold: (t: string) => `At threshold ${t}`,
      atThresholdValue: (reviewed: string, accurate: string) => `${reviewed} reviewed, ${accurate} accurate`,
      tokens: "Tokens per document, in / out",
    },
    charts: {
      title: "Charts",
      missing: "Chart not available yet.",
      items: {
        review_curve: {
          title: "Review load versus accuracy",
          caption:
            "Share of fields sent to a person (x) against the accuracy of what posts automatically (y). The dashed line is accuracy with no review at all.",
        },
        reliability: {
          title: "Reliability, before and after calibration",
          caption:
            "Predicted confidence against the share actually correct. On the diagonal, a 0.9 is right about 90% of the time.",
        },
        f1_by_language: {
          title: "Form extraction by language",
          caption: "Key-value F1 per language on XFUND, with FUNSD for English, using the full pipeline.",
        },
        ablation: {
          title: "Ablation",
          caption: "Each reader alone against both readers plus validators, per dataset.",
        },
      },
    },
    f1: {
      title: "Field F1 by dataset and language",
      dataset: "Dataset",
      language: "Language",
      all: "all",
      paths: { vision: "Vision", ocr_text: "OCR + text", merged: "Both + validators" } as Record<string, string>,
    },
    signals: {
      title: "What each signal says about accuracy",
      body: "Accuracy of extracted fields, grouped by one signal at a time.",
      signal: "Signal",
      fields: "Fields",
      accuracy: "Accuracy",
      names: {
        "agree=True": "Readers agree",
        "agree=False": "Readers disagree",
        "agree=None": "Only one reader",
        "validator=pass": "Validator passed",
        "validator=fail": "Validator failed",
        "validator=na": "No validator applies",
      } as Record<string, string>,
    },
  },

  about: {
    heading: "How it works",
    intro:
      "Extraction models are usually confident and sometimes wrong. Lingua Ledger does not trust a single reading. It collects independent evidence for every field and turns it into a confidence you can set a policy on.",
    diagramLabel: "Pipeline diagram",
    diagram: {
      document: { title: "Document", body: "PDF or image, any language" },
      vision: { title: "Vision reader", body: "Model reads the page image" },
      ocr: { title: "OCR + text reader", body: "OCR text, separate model" },
      validators: { title: "Validators", body: "Sums, dates, IBAN, VAT" },
      confidence: { title: "Confidence", body: "Four signals, calibrated" },
      accept: { title: "Accepted", body: "Posts automatically" },
      review: { title: "Review", body: "A person checks it" },
    },
    signalsTitle: "Four signals per field",
    signals: [
      {
        title: "Reader agreement",
        body: "The vision reader and the OCR + text reader work independently. When they return the same value, it is rarely wrong.",
      },
      {
        title: "OCR confidence",
        body: "The value is located on the page and the OCR engine's confidence for those words is used. This is also where the boxes come from.",
      },
      {
        title: "Validators",
        body: "Deterministic checks: line items add up to the subtotal, tax math holds, dates parse and are in order, IBAN and VAT formats are valid.",
      },
      {
        title: "Self-reported confidence",
        body: "Each reader also says how sure it is. It is the weakest signal on its own, so it carries the least weight.",
      },
    ],
    calibrationTitle: "Calibration",
    calibration:
      "The signals are combined into a raw score, then mapped through an isotonic regression fitted on labelled fields from a held-out split. After that, a confidence of 0.9 means about 90% of such fields are correct. The Evidence page shows the reliability curve before and after.",
    routingTitle: "Routing",
    routing:
      "Any field below the review threshold goes to a person, with its box on the page and the evidence beside it. Raise the threshold for higher accuracy, lower it for less review. The Evidence page shows that trade-off on real data.",
  },
} as const;

export type Copy = typeof copy;
