"use client";

import { CircleCheck, FileJson, FileSpreadsheet, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ThresholdSlider } from "@/components/ui/ThresholdSlider";
import type { ExtractResponse } from "@/lib/api";
import { copy } from "@/lib/copy";
import { fmt, languageName } from "@/lib/format";

export function ResultHeader({
  result,
  threshold,
  onThreshold,
  reviewCount,
  total,
  onExportJson,
  onExportCsv,
}: {
  result: ExtractResponse;
  threshold: number;
  onThreshold: (v: number) => void;
  reviewCount: number;
  total: number;
  onExportJson: () => void;
  onExportCsv: () => void;
}) {
  const c = copy.workbench.result;
  const { doc_type, language, confidence } = result.classification;
  const accepted = total - reviewCount;
  const acceptedPct = total ? (accepted / total) * 100 : 0;

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm text-muted" title={result.filename}>
            {result.filename}
          </p>
          <div className="mt-1.5 inline-flex flex-wrap items-center overflow-hidden rounded-lg border border-line bg-white text-sm">
            <span className="px-2.5 py-1 font-semibold text-navy" title={c.typeConfidence(fmt.score(confidence))}>
              {copy.docTypes[doc_type] ?? doc_type}
            </span>
            <span className="border-l border-line px-2.5 py-1 text-ink">
              {languageName(language)} <span className="font-mono text-xs text-muted">{language}</span>
            </span>
            <span className="border-l border-line px-2.5 py-1 text-muted">{c.pages(result.pages)}</span>
            <span className="border-l border-line px-2.5 py-1 text-muted">{c.latency(fmt.seconds(result.latency_s))}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button icon={FileJson} onClick={onExportJson}>
            {c.exportJson}
          </Button>
          <Button icon={FileSpreadsheet} onClick={onExportCsv}>
            {c.exportCsv}
          </Button>
        </div>
      </div>

      <div className="mt-5 grid items-end gap-6 md:grid-cols-[minmax(0,1fr)_minmax(220px,300px)]">
        <div aria-live="polite">
          <p className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            {reviewCount > 0 ? (
              <UserCheck className="h-7 w-7 shrink-0 text-amber" aria-hidden />
            ) : (
              <CircleCheck className="h-7 w-7 shrink-0 text-teal" aria-hidden />
            )}
            {c.headline(reviewCount, total)}
          </p>
          {total > 0 && <p className="mt-1 text-sm text-muted">{c.subline(accepted, fmt.score(threshold))}</p>}
          {total > 0 && (
            <div className="mt-3">
              <div className="flex h-2.5 overflow-hidden rounded-full bg-white" aria-hidden>
                <div className="bg-teal transition-[width] duration-300" style={{ width: `${acceptedPct}%` }} />
                <div className="bg-amber transition-[width] duration-300" style={{ width: `${100 - acceptedPct}%` }} />
              </div>
              <div className="mt-1.5 flex gap-4 text-xs text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm bg-teal" aria-hidden />
                  {c.accepted} {accepted}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-sm bg-amber" aria-hidden />
                  {c.needsReview} {reviewCount}
                </span>
              </div>
            </div>
          )}
        </div>
        <ThresholdSlider label={c.threshold} hint={c.thresholdHint} value={threshold} onChange={onThreshold} />
      </div>
    </Card>
  );
}
