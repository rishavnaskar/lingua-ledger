const plural = (n: number, one: string, many: string) => (n === 1 ? `1 ${one}` : `${n} ${many}`);

export const copy = {
  site: {
    name: "Lingua Ledger",
    tag: "DataNova 2026 · DN-AI-01",
    description:
      "Pulls data from documents in any language and checks its own work. Each field gets an honest score, and only unsure ones go to a person.",
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
      "Drop in an invoice, receipt, form, or contract in any language. Each field gets a score, and anything uncertain is flagged for review.",
    input: {
      title: "Document",
      dropTitle: "Drop a file here",
      dropHint: "PDF, PNG or JPG up to 15 MB. Any language.",
      dropBrowse: "Choose a file",
      dropActive: "Drop it here to read",
      dropCompact: "Drop another file or click to pick one",
      dropLabel: "Upload a document",
      wrongType: "Only PDF, PNG and JPG files work here.",
      tooLarge: "That file is larger than 15 MB.",
    },
    samples: {
      title: "Sample documents",
      loading: "Loading samples",
      empty: "No sample files on this server yet.",
      failed: "Could not load sample files from the API.",
    },
    options: {
      title: "Options",
      docType: "Document type",
      docTypeAuto: "Detect automatically",
      docTypeNote: "For uploads. Sample files already know their type.",
      threshold: "Review threshold",
      thresholdNote: "Fields scoring below this go to review.",
    },
    idle: {
      title: "Pick a document to start",
      body: "We read your document twice: once with a vision model, and once with OCR and a text model. Built-in checks verify the math and formats, we combine everything into one score for each field, and anything below your cutoff gets sent to a person.",
      points: [
        "See where each value came from and why it was trusted.",
        "Boxes on the page show where each value was found.",
        "Adjust the threshold to balance review work against accuracy.",
      ],
    },
    steps: [
      { label: "Reading pages", detail: "Turning each page into an image" },
      { label: "Vision reader", detail: "Reading the page image with a vision model" },
      { label: "OCR + text reader", detail: "Passing OCR text to a separate text model" },
      { label: "Validators", detail: "Checking math, dates, IBAN and VAT formats" },
      { label: "Confidence", detail: "Combining signals into a calibrated score for each field" },
      { label: "Routing", detail: "Sending unsure fields to human review" },
    ],
    progress: {
      title: (name: string) => `Reading ${name}`,
      elapsed: (s: string) => `${s} elapsed`,
      note: "Both readers run at the same time. Most of the wait happens here.",
    },
    error: {
      title: "Something went wrong",
      retry: "Try again",
      network: (url: string) =>
        `Could not reach the API at ${url}. Check that the backend is running and that NEXT_PUBLIC_API_URL points to it.`,
      server: (status: number, detail: string | null) =>
        detail ? `The server replied with ${status}: ${detail}` : `The server replied with ${status}.`,
    },
    result: {
      pages: (n: number) => plural(n, "page", "pages"),
      latency: (s: string) => `read in ${s}`,
      typeConfidence: (c: string) => `type confidence ${c}`,
      headline: (review: number, total: number) =>
        total === 0
          ? "No fields found"
          : review === 0
            ? `All ${total} fields accepted`
            : `${review} of ${total} fields need review`,
      subline: (accepted: number, threshold: string) =>
        `${accepted} accepted automatically at threshold ${threshold}.`,
      threshold: "Review threshold",
      thresholdHint: "Moving this updates routing right away. Nothing runs again.",
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
        n === 1 ? "Could not find 1 field on the page." : `Could not find ${n} fields on the page.`,
      alt: (i: number) => `Page ${i} of the document`,
      reading: "Reading",
      noPreview: "Preview appears once reading is done.",
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
        agree: "Both readers agree",
        disagree: "Readers disagree",
        single: "Only one reader",
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
        rules: "Rules for this field",
        noRules: "No rules check this field.",
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
      latency: "Time taken",
      tokensIn: "Input tokens",
      tokensOut: "Output tokens",
      fieldsFound: "Fields found",
      notRun: "Did not run for this document.",
      failed: "This reader failed",
      agreement: (a: number, n: number) => `Both readers agree on ${a} of ${n} fields`,
      onlyOne: (n: number) => `Only one reader found ${plural(n, "field", "fields")}.`,
      differences: "Where they differ",
      noDifferences: "Both readers agree on everything.",
      more: (n: number) => `and ${n} more`,
    },
  },

  metrics: {
    heading: "Evidence",
    intro:
      "Results from tests on public benchmarks. You can reproduce every number here using the code in the repository.",
    loading: "Loading results",
    failedTitle: "Could not load results",
    empty: {
      title: "No test results yet",
      body: "The backend has not published a summary yet. Run the tests on the backend, then reload this page.",
      command: "uv run ll eval run && uv run ll eval report",
    },
    cards: {
      documents: {
        label: "Documents tested",
        sub: (failed: number) => (failed ? `${failed} could not be processed` : "All processed"),
      },
      accuracy: {
        label: "Field accuracy",
        sub: (n: string) => `Across ${n} test fields, before any review`,
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
      latency: { label: "Median time", sub: (p95: string) => `p95 ${p95}, per document` },
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
      missing: "Chart is not available yet.",
      items: {
        review_curve: {
          title: "Review load versus accuracy",
          caption:
            "Share of fields sent to a person (x) against the accuracy of what saves automatically (y). The dashed line shows accuracy without any review.",
        },
        reliability: {
          title: "Reliability, before and after calibration",
          caption:
            "Predicted confidence against the share actually correct. On the diagonal line, a 0.9 is right about 90% of the time.",
        },
        f1_by_language: {
          title: "Form extraction by language",
          caption: "Key-value score by language on XFUND, with FUNSD for English, using the full pipeline.",
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
        "agree=True": "Both readers agree",
        "agree=False": "Readers disagree",
        "agree=None": "Only one reader",
        "validator=pass": "Check passed",
        "validator=fail": "Check failed",
        "validator=na": "No check applies",
      } as Record<string, string>,
    },
  },

  about: {
    heading: "How it works",
    intro:
      "Extraction models are usually confident, but sometimes wrong. Lingua Ledger never relies on a single reading. It collects independent evidence for every field and turns it into a clear confidence score you can trust.",
    diagramLabel: "Pipeline diagram",
    diagram: {
      document: { title: "Document", body: "PDF or image, any language" },
      vision: { title: "Vision reader", body: "Reads the page image directly" },
      ocr: { title: "OCR + text reader", body: "Reads OCR text with a separate model" },
      validators: { title: "Validators", body: "Checks sums, dates, IBAN, and VAT" },
      confidence: { title: "Confidence", body: "Four signals combined into one score" },
      accept: { title: "Accepted", body: "Saves automatically" },
      review: { title: "Review", body: "A person checks it" },
    },
    signalsTitle: "Four signals per field",
    signals: [
      {
        title: "Reader agreement",
        body: "The vision reader and the OCR + text reader work on their own. When they both return the same value, it is almost always right.",
      },
      {
        title: "OCR confidence",
        body: "We find the value on the page and use the OCR score for those words. This is also how we draw the boxes on the page.",
      },
      {
        title: "Validators",
        body: "Rule checks: line items add up to the subtotal, tax math is correct, dates make sense and are in order, and IBAN and VAT numbers are valid.",
      },
      {
        title: "Self-reported confidence",
        body: "Each reader reports how sure it feels. This is the weakest signal on its own, so it only gives the score a small push.",
      },
    ],
    calibrationTitle: "Calibration",
    calibration:
      "All signals are combined into a raw score and calibrated using isotonic regression tested on unseen documents. After that, a 0.9 confidence means the field is right about 90% of the time. The Evidence page shows the reliability curve before and after.",
    routingTitle: "Routing",
    routing:
      "Any field below the review threshold goes to a person, along with its box on the page and the evidence behind it. Raise the threshold for higher accuracy, or lower it to reduce human review. The Evidence page shows this trade-off on real data.",
  },
} as const;

export type Copy = typeof copy;
