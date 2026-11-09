"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState } from "react";
import { ChartColumn, CircleAlert, LoaderCircle } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/Card";
import {
  CHART_NAMES,
  chartUrl,
  getMetrics,
  type ArbiterSignalEffect,
  type ChartName,
  type MetricsSummary,
  type ThresholdOutcome,
} from "@/lib/api";
import { copy } from "@/lib/copy";
import { describeError, isAbort } from "@/lib/errors";
import { fmt, languageName } from "@/lib/format";

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: MetricsSummary };

const PATH_ORDER = ["arbiter", "merged", "vision", "ocr_text"];

export function MetricsView() {
  const c = copy.metrics;
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    getMetrics(ctrl.signal)
      .then((data) => setState({ status: "ready", data: data ?? {} }))
      .catch((err) => {
        if (!isAbort(err)) setState({ status: "error", message: describeError(err) });
      });
    return () => ctrl.abort();
  }, []);

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{c.heading}</h1>
        <p className="mt-1.5 text-muted">{c.intro}</p>
      </header>

      {state.status === "loading" && (
        <Card className="flex items-center gap-3 text-muted">
          <LoaderCircle className="h-5 w-5 animate-spin text-navy" aria-hidden />
          {c.loading}
        </Card>
      )}

      {state.status === "error" && (
        <Card role="alert" className="flex items-start gap-3 border border-brick/30 bg-brick/5">
          <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-brick" aria-hidden />
          <div>
            <h2 className="font-semibold text-ink">{c.failedTitle}</h2>
            <p className="mt-1 text-sm text-muted">{state.message}</p>
          </div>
        </Card>
      )}

      {state.status === "ready" && !state.data.documents && <EmptyState />}
      {state.status === "ready" && !!state.data.documents && <Results data={state.data} />}
    </div>
  );
}

function EmptyState() {
  const c = copy.metrics.empty;
  return (
    <Card className="max-w-2xl">
      <h2 className="text-lg font-semibold text-ink">{c.title}</h2>
      <p className="mt-2 text-muted">{c.body}</p>
      <pre className="mt-4 overflow-x-auto rounded-lg border border-line bg-white px-3 py-2 font-mono text-sm text-ink">
        {c.command}
      </pre>
    </Card>
  );
}

function Results({ data }: { data: MetricsSummary }) {
  const c = copy.metrics;
  const cal = data.calibration ?? {};
  const review = data.review ?? {};
  const accuracy = cal.field_accuracy ?? review.baseline_accuracy_no_review;
  const r98 = num(review.review_rate_at_98pct_accuracy);
  const t98 = num(review.threshold_at_98pct_accuracy);
  const r95 = num(review.review_rate_at_95pct_accuracy);
  const atThreshold = Object.entries(review).find(([k]) => k.startsWith("at_threshold_"));
  const atValue = atThreshold?.[1] as ThresholdOutcome | undefined;

  const na = copy.common.notAvailable;
  const cards = [
    {
      label: c.cards.documents.label,
      value: fmt.int(data.documents ?? 0),
      sub: c.cards.documents.sub(data.failed_documents ?? 0),
    },
    {
      label: c.cards.accuracy.label,
      value: accuracy !== undefined ? fmt.pct(accuracy) : na,
      sub: cal.test_fields ? c.cards.accuracy.sub(fmt.int(cal.test_fields)) : "",
    },
    {
      label: c.cards.ece.label,
      value:
        cal.ece_raw !== undefined && cal.ece_calibrated !== undefined
          ? `${fmt.ece(cal.ece_raw)} → ${fmt.ece(cal.ece_calibrated)}`
          : na,
      sub: c.cards.ece.sub,
    },
    {
      label: c.cards.review98.label,
      value: r98 !== undefined ? fmt.pct(r98) : c.cards.review98.notReached,
      sub: r98 !== undefined && t98 !== undefined ? c.cards.review98.sub(fmt.score(t98)) : c.cards.review98.notReachedSub,
    },
    {
      label: c.cards.latency.label,
      value: data.latency_s?.p50 !== undefined ? fmt.seconds(data.latency_s.p50) : na,
      sub: data.latency_s?.p95 !== undefined ? c.cards.latency.sub(fmt.seconds(data.latency_s.p95)) : "",
    },
    {
      label: c.cards.cost.label,
      value: data.cost_usd?.per_1000_docs !== undefined ? fmt.usd(data.cost_usd.per_1000_docs) : na,
      sub: data.cost_usd?.total !== undefined ? c.cards.cost.sub(fmt.usd(data.cost_usd.total)) : "",
    },
  ];

  const details: { label: string; value: string }[] = [];
  if (data.classification?.doc_type_acc !== undefined)
    details.push({ label: c.details.docTypeAcc, value: fmt.pct(data.classification.doc_type_acc) });
  if (data.classification?.language_acc !== undefined)
    details.push({ label: c.details.languageAcc, value: fmt.pct(data.classification.language_acc) });
  if (cal.brier_raw !== undefined && cal.brier_calibrated !== undefined)
    details.push({ label: c.details.brier, value: `${fmt.ece(cal.brier_raw)} → ${fmt.ece(cal.brier_calibrated)}` });
  if (r95 !== undefined) details.push({ label: c.details.review95, value: fmt.pct(r95) });
  if (atThreshold && atValue && typeof atValue === "object")
    details.push({
      label: c.details.atThreshold(atThreshold[0].replace("at_threshold_", "")),
      value: c.details.atThresholdValue(fmt.pct(atValue.review_rate), fmt.pct(atValue.auto_accuracy)),
    });
  if (data.tokens?.per_doc_input !== undefined && data.tokens?.per_doc_output !== undefined)
    details.push({
      label: c.details.tokens,
      value: `${fmt.int(data.tokens.per_doc_input)} / ${fmt.int(data.tokens.per_doc_output)}`,
    });

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.label} as="div">
            <p className="text-sm text-muted">{card.label}</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight text-ink tabular-nums">{card.value}</p>
            {card.sub && <p className="mt-1 text-xs text-muted">{card.sub}</p>}
          </Card>
        ))}
      </div>

      {details.length > 0 && (
        <Card>
          <CardTitle>{c.details.title}</CardTitle>
          <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
            {details.map((d) => (
              <div key={d.label} className="flex items-baseline justify-between gap-3 border-b border-line pb-2">
                <dt className="text-sm text-muted">{d.label}</dt>
                <dd className="font-mono text-sm text-ink tabular-nums">{d.value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold tracking-wide text-ink uppercase">
          <ChartColumn className="h-4 w-4 text-navy" aria-hidden />
          {c.charts.title}
        </h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {CHART_NAMES.map((name) => (
            <ChartCard key={name} name={name} />
          ))}
        </div>
      </section>

      {data.arbiter && <ArbiterCard a={data.arbiter} documents={data.documents ?? 0} />}

      <div className="grid items-start gap-6 xl:grid-cols-2">
        {data.f1 && Object.keys(data.f1).length > 0 && <F1Table f1={data.f1} />}
        {data.signals && Object.keys(data.signals).length > 0 && <SignalsTable signals={data.signals} />}
      </div>
    </>
  );
}

function ArbiterCard({ a, documents }: { a: NonNullable<MetricsSummary["arbiter"]>; documents: number }) {
  const c = copy.metrics.arbiter;
  const na = copy.common.notAvailable;
  const pct = (v: number | null | undefined) => (typeof v === "number" ? fmt.pct(v) : na);
  const ece = (e?: ArbiterSignalEffect) => (typeof e?.ece_calibrated === "number" ? fmt.ece(e.ece_calibrated) : na);
  const r95 = (e?: ArbiterSignalEffect) => pct(e?.review_rate_at_95pct_accuracy);
  const stats = [
    { label: c.disputes, value: fmt.int(a.disputes ?? 0) },
    { label: c.before, value: pct(a.disputed_accuracy_base) },
    { label: c.after, value: pct(a.disputed_accuracy_override) },
    { label: c.eceSignal, value: `${ece(a.without_signal)} → ${ece(a.with_signal)}` },
    { label: c.reviewSignal, value: `${r95(a.without_signal)} → ${r95(a.with_signal)}` },
    { label: c.latency, value: typeof a.latency_p50 === "number" ? fmt.seconds(a.latency_p50) : na },
  ];
  return (
    <Card>
      <CardTitle aside={<span className="text-xs text-muted">{c.documents(a.documents_with_disputes ?? 0, documents)}</span>}>
        {c.title}
      </CardTitle>
      <p className="-mt-1 mb-3 text-sm text-muted">{c.body}</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-line bg-white px-3 py-2.5">
            <p className="text-xs text-muted">{s.label}</p>
            <p className="mt-1 text-xl font-semibold text-ink tabular-nums">{s.value}</p>
          </div>
        ))}
      </div>
      {a.verdicts && (
        <p className="mt-3 text-xs text-muted">
          {c.verdicts}:{" "}
          {Object.entries(a.verdicts)
            .map(([k, v]) => `${c.choices[k] ?? k} ${fmt.int(v)}`)
            .join(" · ")}
        </p>
      )}
    </Card>
  );
}

function ChartCard({ name }: { name: ChartName }) {
  const c = copy.metrics.charts;
  const [failed, setFailed] = useState(false);
  const item = c.items[name];
  return (
    <Card as="article">
      <h3 className="font-semibold text-ink">{item.title}</h3>
      <p className="mt-1 text-sm text-muted">{item.caption}</p>
      <div className="mt-3 overflow-hidden rounded-xl border border-line bg-white">
        {failed ? (
          <p className="flex h-40 items-center justify-center text-sm text-muted">{c.missing}</p>
        ) : (
          <img
            src={chartUrl(name)}
            alt={item.title}
            loading="lazy"
            onError={() => setFailed(true)}
            className="block h-auto w-full"
          />
        )}
      </div>
    </Card>
  );
}

function F1Table({ f1 }: { f1: Record<string, number> }) {
  const c = copy.metrics.f1;
  const rows = new Map<string, { dataset: string; language: string; values: Record<string, number> }>();
  const paths = new Set<string>();
  for (const [key, value] of Object.entries(f1)) {
    const [dataset, language, path] = key.split("/");
    if (!dataset || !language || !path) continue;
    paths.add(path);
    const id = `${dataset}/${language}`;
    const row = rows.get(id) ?? { dataset, language, values: {} };
    row.values[path] = value;
    rows.set(id, row);
  }
  const cols = [...paths].sort((a, b) => rank(a) - rank(b));
  const sorted = [...rows.values()].sort(
    (a, b) =>
      Number(b.dataset === "all") - Number(a.dataset === "all") ||
      a.dataset.localeCompare(b.dataset) ||
      Number(b.language === "all") - Number(a.language === "all") ||
      a.language.localeCompare(b.language),
  );

  return (
    <Card>
      <CardTitle>{c.title}</CardTitle>
      <div className="overflow-x-auto rounded-xl border border-line bg-white">
        <table className="w-full min-w-[420px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="py-2 pr-2 pl-4 font-medium">
                {c.dataset}
              </th>
              <th scope="col" className="px-2 py-2 font-medium">
                {c.language}
              </th>
              {cols.map((p) => (
                <th key={p} scope="col" className="px-2 py-2 text-right font-medium last:pr-4">
                  {c.paths[p] ?? p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={`${r.dataset}/${r.language}`} className="border-t border-line">
                <td className="py-2 pr-2 pl-4 font-medium text-ink">{r.dataset === "all" ? c.all : r.dataset}</td>
                <td className="px-2 py-2 text-muted">
                  {r.language === "all" ? c.all : `${languageName(r.language)} (${r.language})`}
                </td>
                {cols.map((p) => (
                  <td key={p} className="px-2 py-2 text-right font-mono tabular-nums last:pr-4">
                    {r.values[p] !== undefined ? fmt.pct(r.values[p]) : copy.common.notAvailable}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function SignalsTable({ signals }: { signals: Record<string, { n: number; accuracy: number }> }) {
  const c = copy.metrics.signals;
  return (
    <Card>
      <CardTitle>{c.title}</CardTitle>
      <p className="-mt-1 mb-3 text-sm text-muted">{c.body}</p>
      <div className="overflow-x-auto rounded-xl border border-line bg-white">
        <table className="w-full min-w-[360px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="py-2 pr-2 pl-4 font-medium">
                {c.signal}
              </th>
              <th scope="col" className="px-2 py-2 text-right font-medium">
                {c.fields}
              </th>
              <th scope="col" className="py-2 pr-4 pl-2 text-right font-medium">
                {c.accuracy}
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(signals).map(([key, s]) => (
              <tr key={key} className="border-t border-line">
                <td className="py-2 pr-2 pl-4 text-ink">{c.names[key] ?? key}</td>
                <td className="px-2 py-2 text-right font-mono text-muted tabular-nums">{fmt.int(s.n)}</td>
                <td className="py-2 pr-4 pl-2 text-right font-mono tabular-nums">{fmt.pct(s.accuracy)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function rank(path: string): number {
  const i = PATH_ORDER.indexOf(path);
  return i === -1 ? PATH_ORDER.length : i;
}

function num(v: unknown): number | undefined {
  return typeof v === "number" ? v : undefined;
}
