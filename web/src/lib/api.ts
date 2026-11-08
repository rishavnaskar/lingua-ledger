export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export const DEFAULT_THRESHOLD = 0.85;
export const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export type DocType = "invoice" | "receipt" | "form" | "contract";
export const DOC_TYPES: DocType[] = ["invoice", "receipt", "form", "contract"];

export type ReaderPath = "vision" | "ocr_text";
export type ValidatorOutcome = "pass" | "fail" | "na";

export interface Classification {
  doc_type: DocType;
  language: string;
  confidence: number;
}

export interface FieldResult {
  field: string;
  value: unknown;
  confidence: number;
  raw_score: number;
  agree: boolean | null;
  ocr_conf: number | null;
  validator: ValidatorOutcome;
  self_conf: number | null;
  vision_value: unknown;
  ocr_value: unknown;
  bbox: [number, number, number, number] | null;
  page?: number | null;
  needs_review: boolean;
}

export interface RuleResult {
  rule: string;
  fields: string[];
  passed: boolean | null;
  message: string;
}

export interface PathOutput {
  path: ReaderPath;
  data: Record<string, unknown>;
  self_confidence: Record<string, number>;
  latency_s: number;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
}

export interface ExtractionResult {
  doc_id: string;
  classification: Classification;
  data: Record<string, unknown>;
  fields: FieldResult[];
  rules: RuleResult[];
  paths: PathOutput[];
  review_threshold: number;
  review_rate: number;
  pages: number;
  latency_s: number;
}

export interface PagePreview {
  index: number;
  width: number;
  height: number;
  data_url: string;
}

export interface ExtractResponse extends ExtractionResult {
  pages_preview: PagePreview[];
  filename: string;
}

export interface Sample {
  id: string;
  title: string;
  doc_type: DocType;
  language: string;
  file: string;
}

export interface ThresholdOutcome {
  review_rate: number;
  auto_accuracy: number;
}

export interface MetricsSummary {
  documents?: number;
  failed_documents?: number;
  f1?: Record<string, number>;
  classification?: { n?: number; doc_type_acc?: number; language_acc?: number };
  calibration?: {
    ece_raw?: number;
    ece_calibrated?: number;
    brier_raw?: number;
    brier_calibrated?: number;
    field_accuracy?: number;
    fit_fields?: number;
    test_fields?: number;
  };
  review?: { baseline_accuracy_no_review?: number } & Record<string, number | ThresholdOutcome | undefined>;
  latency_s?: { p50?: number; p95?: number };
  tokens?: { input?: number; output?: number; per_doc_input?: number; per_doc_output?: number };
  cost_usd?: { total?: number; per_1000_docs?: number };
  signals?: Record<string, { n: number; accuracy: number }>;
}

export type ChartName = "review_curve" | "reliability" | "f1_by_language" | "ablation";
export const CHART_NAMES: ChartName[] = ["review_curve", "reliability", "f1_by_language", "ablation"];

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string | null,
  ) {
    super(detail ?? `HTTP ${status}`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, null);
  }
  if (!res.ok) {
    let detail: string | null = null;
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      detail = res.statusText || null;
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export interface ExtractOptions {
  threshold: number;
  docType?: DocType | null;
  language?: string | null;
  paths?: ReaderPath[];
  signal?: AbortSignal;
}

export function extractFile(file: File, opts: ExtractOptions): Promise<ExtractResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("threshold", String(opts.threshold));
  form.append("paths", (opts.paths ?? ["vision", "ocr_text"]).join(","));
  if (opts.docType) form.append("doc_type", opts.docType);
  if (opts.language) form.append("language", opts.language);
  return request<ExtractResponse>("/extract", { method: "POST", body: form, signal: opts.signal });
}

export function extractSample(id: string, opts: ExtractOptions): Promise<ExtractResponse> {
  const params = new URLSearchParams({
    threshold: String(opts.threshold),
    paths: (opts.paths ?? ["vision", "ocr_text"]).join(","),
  });
  return request<ExtractResponse>(`/samples/${encodeURIComponent(id)}/extract?${params}`, {
    method: "POST",
    signal: opts.signal,
  });
}

export function getSamples(signal?: AbortSignal): Promise<Sample[]> {
  return request<Sample[]>("/samples", { signal });
}

export function getMetrics(signal?: AbortSignal): Promise<MetricsSummary> {
  return request<MetricsSummary>("/metrics", { signal, cache: "no-store" });
}

export const sampleFileUrl = (id: string) => `${API_URL}/samples/${encodeURIComponent(id)}/file`;
export const chartUrl = (name: ChartName) => `${API_URL}/metrics/charts/${name}`;
