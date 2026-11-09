"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, CircleAlert, LoaderCircle, Pencil, RotateCcw, Send, Undo2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { ConfidencePill } from "@/components/ui/ConfidencePill";
import { resetLearning, submitReview, type Decision, type ExtractResponse, type FieldResult, type LearningState } from "@/lib/api";
import { copy } from "@/lib/copy";
import { describeError } from "@/lib/errors";
import { cn, fieldLabel, fmt, formatValue, isPresent } from "@/lib/format";

type Choice = { accepted: true } | { accepted: false; value: string };

export function ReviewPanel({
  result,
  fields,
  threshold,
  learning,
  onLearning,
  onHover,
  onSelect,
}: {
  result: ExtractResponse;
  fields: FieldResult[];
  threshold: number;
  learning: LearningState | null;
  onLearning: (state: LearningState | null) => void;
  onHover: (field: string | null) => void;
  onSelect: (field: string) => void;
}) {
  const c = copy.workbench.review;
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState<"idle" | "posting" | "posted" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setChoices({});
    setEditing(null);
    setStatus("idle");
    setError(null);
  }, [result.doc_id]);

  const present = useMemo(() => fields.filter((f) => isPresent(f.value)), [fields]);
  const toReview = useMemo(() => present.filter((f) => f.needs_review), [present]);
  const pending = toReview.filter((f) => !choices[f.field]).length;

  const decide = (field: string, choice: Choice) => {
    setChoices((prev) => ({ ...prev, [field]: choice }));
    setEditing(null);
  };

  const post = async () => {
    setStatus("posting");
    setError(null);
    const decisions: Decision[] = present.map((f) => {
      const ch = choices[f.field];
      if (ch && !ch.accepted) {
        return { field: f.field, raw_score: f.raw_score, accepted: false, value: f.value, corrected_value: ch.value };
      }
      return { field: f.field, raw_score: f.raw_score, accepted: true, value: f.value };
    });
    const data = applyCorrections(result.data, choices);
    try {
      const state = await submitReview({
        doc_id: result.doc_id,
        doc_type: result.classification.doc_type,
        data,
        decisions,
        post: true,
      });
      onLearning(state);
      setStatus("posted");
    } catch (err) {
      setError(describeError(err));
      setStatus("error");
    }
  };

  const reset = async () => {
    if (!window.confirm(copy.workbench.learning.resetConfirm)) return;
    try {
      onLearning(await resetLearning());
    } catch (err) {
      setError(describeError(err));
    }
  };

  return (
    <Card>
      <CardTitle
        icon={Pencil}
        aside={
          toReview.length > 0 && (
            <span className={cn("text-xs", pending ? "text-amber-ink" : "text-teal-ink")}>
              {pending ? c.pending(pending) : c.decided}
            </span>
          )
        }
      >
        {c.title}
      </CardTitle>
      <p className="text-sm text-muted">{toReview.length === 0 ? c.nothing : c.intro}</p>

      {toReview.length > 0 && (
        <ul className="mt-3 divide-y divide-line overflow-hidden rounded-xl border border-line bg-white">
          {toReview.map((f) => {
            const ch = choices[f.field];
            const isEditing = editing === f.field;
            return (
              <li
                key={f.field}
                className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5"
                onMouseEnter={() => onHover(f.field)}
                onMouseLeave={() => onHover(null)}
              >
                <button type="button" onClick={() => onSelect(f.field)} className="min-w-0 flex-1 text-left">
                  <span className="block text-sm font-medium text-ink">{fieldLabel(f.field, result.data)}</span>
                  <span className="block font-mono text-[13px] break-words text-muted">
                    {ch && !ch.accepted ? (
                      <>
                        <s className="opacity-60">{formatValue(f.value)}</s> <span className="text-ink">{ch.value}</span>
                      </>
                    ) : (
                      formatValue(f.value)
                    )}
                  </span>
                </button>
                <ConfidencePill value={f.confidence} threshold={threshold} />
                {ch ? (
                  <span className="flex items-center gap-2">
                    <Badge tone={ch.accepted ? "teal" : "navy"} icon={Check}>
                      {ch.accepted ? c.accepted : c.fixed}
                    </Badge>
                    <Button
                      variant="ghost"
                      icon={Undo2}
                      disabled={status === "posting"}
                      onClick={() =>
                        setChoices((prev) => {
                          const next = { ...prev };
                          delete next[f.field];
                          return next;
                        })
                      }
                    >
                      {c.undo}
                    </Button>
                  </span>
                ) : isEditing ? (
                  <form
                    className="flex items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (draft.trim()) decide(f.field, { accepted: false, value: draft.trim() });
                    }}
                  >
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      placeholder={c.placeholder}
                      aria-label={c.placeholder}
                      className="w-44 rounded-lg border border-line px-2.5 py-1 font-mono text-sm text-ink"
                    />
                    <Button variant="primary" type="submit">
                      {c.save}
                    </Button>
                    <Button variant="ghost" onClick={() => setEditing(null)}>
                      {c.cancel}
                    </Button>
                  </form>
                ) : (
                  <span className="flex items-center gap-2">
                    <Button icon={Check} disabled={status === "posting"} onClick={() => decide(f.field, { accepted: true })}>
                      {c.accept}
                    </Button>
                    <Button
                      icon={Pencil}
                      disabled={status === "posting"}
                      onClick={() => {
                        setDraft(formatValue(f.value));
                        setEditing(f.field);
                      }}
                    >
                      {c.fix}
                    </Button>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {pending > 0 && (
          <Button
            icon={Check}
            disabled={status === "posting"}
            onClick={() =>
              setChoices((prev) => {
                const next = { ...prev };
                toReview.forEach((f) => {
                  if (!next[f.field]) next[f.field] = { accepted: true };
                });
                return next;
              })
            }
          >
            {c.acceptRest(pending)}
          </Button>
        )}
        <Button
          variant="primary"
          icon={status === "posting" ? LoaderCircle : Send}
          disabled={status === "posting" || status === "posted" || pending > 0}
          onClick={post}
        >
          {status === "posting" ? c.posting : c.post}
        </Button>
        {status === "posted" && <span className="text-sm text-teal-ink">{c.posted}</span>}
        {status === "error" && (
          <span className="flex items-center gap-1.5 text-sm text-brick-ink">
            <CircleAlert className="h-4 w-4" aria-hidden />
            {c.failed}: {error}
          </span>
        )}
      </div>

      {learning && <LearningSummary state={learning} onReset={reset} />}
    </Card>
  );
}

function applyCorrections(data: Record<string, unknown>, choices: Record<string, Choice>): Record<string, unknown> {
  const out: Record<string, unknown> = JSON.parse(JSON.stringify(data));
  for (const [path, ch] of Object.entries(choices)) {
    if (ch.accepted) continue;
    const m = path.match(/^([A-Za-z_]+)\[(\d+)\](?:\.(.+))?$/);
    const value = coerce(path, ch.value);
    if (!m) {
      out[path] = value;
      continue;
    }
    const list = out[m[1]];
    if (!Array.isArray(list)) continue;
    const item = list[Number(m[2])];
    if (m[3] && item && typeof item === "object") (item as Record<string, unknown>)[m[3]] = value;
    else if (!m[3]) list[Number(m[2])] = value;
  }
  return out;
}

const NUMERIC = /(^|\.)(quantity|unit_price|total|subtotal|tax_rate|tax_amount|service_charge|discount|cash_paid|change)$/;

function coerce(path: string, text: string): unknown {
  if (NUMERIC.test(path)) {
    const n = Number(text.replace(/\s/g, "").replace(/,(?=\d{1,2}$)/, ".").replace(/[^\d.-]/g, ""));
    return Number.isFinite(n) ? n : text;
  }
  return text;
}

function LearningSummary({ state, onReset }: { state: LearningState; onReset: () => void }) {
  const c = copy.workbench.learning;
  const na = copy.common.notAvailable;
  const rows: { label: string; before: string; after: string; better: boolean | null }[] = [
    point(c.review95, state.before.review_rate_at_95, state.after.review_rate_at_95, fmt.pct, true),
    point(c.review98, state.before.review_rate_at_98, state.after.review_rate_at_98, fmt.pct, true),
    point(c.ece, state.before.ece, state.after.ece, fmt.ece, true),
  ];
  return (
    <div className="mt-5 rounded-xl border border-line bg-white p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{c.title}</h3>
        <span className="text-xs text-muted">{c.posted(state.memory.documents_posted, state.memory.vendors)}</span>
      </div>
      <p className="mt-1 text-sm text-muted">
        {c.corrections(state.corrections)}
        {state.fields_fixed > 0 ? `, ${c.fixed(state.fields_fixed)}` : ""}. {c.weight(state.weight)}
      </p>
      <div className="mt-3 grid gap-4 md:grid-cols-[minmax(0,1fr)_200px]">
        <table className="w-full text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-1 text-left font-medium" />
              <th className="py-1 pl-4 text-right font-medium">{c.before}</th>
              <th className="py-1 pl-4 text-right font-medium">{c.after}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-t border-line">
                <td className="py-1.5 pr-2 text-muted">{r.label}</td>
                <td className="py-1.5 pl-4 text-right font-mono tabular-nums">{r.before || na}</td>
                <td
                  className={cn(
                    "py-1.5 pl-4 text-right font-mono font-semibold tabular-nums",
                    r.better === true && "text-teal-ink",
                    r.better === false && "text-brick-ink",
                  )}
                >
                  {r.after || na}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Curve before={state.curve_before} after={state.curve_after} label={c.curve(copy.docTypes[state.doc_type] ?? state.doc_type)} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted">{c.note}</p>
        <Button variant="ghost" icon={RotateCcw} onClick={onReset}>
          {c.reset}
        </Button>
      </div>
    </div>
  );
}

function point(
  label: string,
  before: number | null | undefined,
  after: number | null | undefined,
  f: (x: number) => string,
  lowerIsBetter: boolean,
) {
  const b = typeof before === "number" ? before : null;
  const a = typeof after === "number" ? after : null;
  const better = b === null || a === null || f(a) === f(b) ? null : lowerIsBetter ? a < b : a > b;
  return { label, before: b === null ? "" : f(b), after: a === null ? "" : f(a), better };
}

function Curve({ before, after, label }: { before: [number, number][]; after: [number, number][]; label: string }) {
  const w = 200;
  const h = 120;
  const pad = 6;
  const path = (pts: [number, number][]) =>
    pts.map(([x, y], i) => `${i ? "L" : "M"}${pad + x * (w - 2 * pad)},${h - pad - y * (h - 2 * pad)}`).join(" ");
  return (
    <figure className="min-w-0">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label} className="h-auto w-full rounded-lg border border-line bg-paper/60">
        <line x1={pad} y1={h - pad} x2={w - pad} y2={pad} stroke="var(--color-line)" strokeWidth={1} />
        <path d={path(before)} fill="none" stroke="var(--color-navy)" strokeWidth={1.5} strokeDasharray="4 3" />
        <path d={path(after)} fill="none" stroke="var(--color-teal)" strokeWidth={2} />
      </svg>
      <figcaption className="mt-1 text-[11px] text-muted">{label}</figcaption>
    </figure>
  );
}
