import { copy } from "./copy";
import type { ExtractResponse, ExtractionResult, FieldResult, RuleResult } from "./api";

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function isPresent(v: unknown): boolean {
  return v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0);
}

export function routeFields(fields: FieldResult[], threshold: number): FieldResult[] {
  return fields.map((f) => ({ ...f, needs_review: isPresent(f.value) && f.confidence < threshold }));
}

export const fmt = {
  score: (x: number) => x.toFixed(2),
  ece: (x: number) => x.toFixed(3),
  pct: (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`,
  seconds: (x: number) => `${x < 10 ? x.toFixed(1) : Math.round(x)} s`,
  int: (n: number) => Math.round(n).toLocaleString("en-US"),
  usd: (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
};

export function formatValue(v: unknown): string {
  if (!isPresent(v)) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Math.round(v * 10000) / 10000);
  if (typeof v === "boolean") return String(v);
  return JSON.stringify(v);
}

export function sameValue(a: unknown, b: unknown): boolean {
  return formatValue(a).trim().toLowerCase() === formatValue(b).trim().toLowerCase();
}

let languageNames: Intl.DisplayNames | null = null;
try {
  languageNames = new Intl.DisplayNames(["en"], { type: "language" });
} catch {
  languageNames = null;
}

export function languageName(code: string): string {
  try {
    return languageNames?.of(code) ?? code;
  } catch {
    return code;
  }
}

export function humanize(key: string): string {
  const s = key.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const LIST_PATH = /^([A-Za-z_]+)\[(\d+)\](?:\.(.+))?$/;

function leafLabel(key: string): string {
  return copy.workbench.fields.names[key] ?? humanize(key);
}

export function fieldLabel(path: string, data?: Record<string, unknown>): string {
  const m = path.match(LIST_PATH);
  if (!m) return leafLabel(path);
  const [, list, idxText, sub] = m;
  const idx = Number(idxText);
  if (list === "fields" && sub === "value" && data && Array.isArray(data.fields)) {
    const key = (data.fields[idx] as { key?: unknown } | undefined)?.key;
    if (typeof key === "string" && key.trim()) return key.trim();
  }
  const base = `${copy.workbench.fields.listItem[list] ?? humanize(list)} ${idx + 1}`;
  return sub ? `${base} · ${leafLabel(sub)}` : base;
}

export function rulesForField(rules: RuleResult[], field: string): RuleResult[] {
  return rules.filter((r) =>
    r.fields.some((f) => f === field || field.startsWith(`${f}.`) || field.startsWith(`${f}[`)),
  );
}

export function ruleLabel(rule: string): string {
  return copy.workbench.validators.names[rule] ?? humanize(rule);
}

export function ruleStatus(r: RuleResult): "pass" | "fail" | "na" {
  return r.passed === true ? "pass" : r.passed === false ? "fail" : "na";
}

export function exportBaseName(filename: string): string {
  const base = filename
    .replace(/\.[^.]+$/, "")
    .replace(/[^\w.-]+/g, "-")
    .replace(/^-+/, "")
    .replace(/-+$/, "");
  return `${base || "document"}-lingua-ledger`;
}

export function buildExport(
  result: ExtractResponse,
  fields: FieldResult[],
  threshold: number,
): ExtractionResult & { filename: string } {
  const present = fields.filter((f) => isPresent(f.value));
  const review = present.filter((f) => f.needs_review).length;
  return {
    doc_id: result.doc_id,
    filename: result.filename,
    classification: result.classification,
    data: result.data,
    fields,
    rules: result.rules,
    paths: result.paths,
    review_threshold: threshold,
    review_rate: present.length ? Math.round((review / present.length) * 10000) / 10000 : 0,
    pages: result.pages,
    latency_s: result.latency_s,
  };
}

export function toCsv(fields: FieldResult[]): string {
  const esc = (s: string) => (/[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
  const rows = [
    ["field", "value", "confidence", "needs_review"],
    ...fields.map((f) => [f.field, formatValue(f.value), f.confidence.toFixed(4), String(f.needs_review)]),
  ];
  return rows.map((r) => r.map(esc).join(",")).join("\r\n") + "\r\n";
}

export function downloadText(filename: string, text: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
