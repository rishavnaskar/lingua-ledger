"use client";

import { CircleAlert, Info, Siren, TriangleAlert } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/Card";
import type { Anomaly, MemoryInfo, Severity } from "@/lib/api";
import { copy } from "@/lib/copy";
import { cn, fieldLabel } from "@/lib/format";

const ORDER: Record<Severity, number> = { high: 0, warn: 1, info: 2 };

const ICONS: Record<Severity, typeof Info> = { high: Siren, warn: TriangleAlert, info: Info };

const TONES: Record<Severity, { icon: string; label: string; row: string }> = {
  high: { icon: "text-brick", label: "text-brick-ink", row: "bg-brick/5" },
  warn: { icon: "text-amber-ink", label: "text-amber-ink", row: "bg-amber/10" },
  info: { icon: "text-navy", label: "text-muted", row: "" },
};

export function AnomaliesPanel({
  anomalies,
  memory,
  data,
  knownFields,
  onHover,
  onSelect,
  postedDocuments,
}: {
  anomalies: Anomaly[];
  memory?: MemoryInfo;
  data: Record<string, unknown>;
  knownFields: Set<string>;
  onHover: (field: string | null) => void;
  onSelect: (field: string) => void;
  postedDocuments: number | null;
}) {
  const c = copy.workbench.anomalies;
  const counts = { high: 0, warn: 0, info: 0 };
  anomalies.forEach((a) => counts[a.severity]++);
  const sorted = [...anomalies].sort((a, b) => ORDER[a.severity] - ORDER[b.severity]);
  const summary = c.summary(counts.high, counts.warn, counts.info);

  return (
    <Card>
      <CardTitle
        icon={CircleAlert}
        aside={summary ? <span className="text-xs text-muted">{summary}</span> : undefined}
      >
        {c.title}
      </CardTitle>
      {sorted.length === 0 ? (
        <p className="text-sm text-muted">{c.empty}</p>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-white">
          {sorted.map((a, i) => {
            const Icon = ICONS[a.severity];
            const tone = TONES[a.severity];
            return (
              <li key={`${a.code}-${i}`} className={cn("flex gap-3 px-4 py-3", tone.row)}>
                <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", tone.icon)} aria-hidden />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-sm font-medium text-ink">{c.names[a.code] ?? a.code}</span>
                    <span className={cn("text-xs", tone.label)}>{c.severity[a.severity]}</span>
                  </div>
                  <p className="mt-0.5 text-sm break-words text-muted">{a.message}</p>
                  {a.fields.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {a.fields.map((f) =>
                        knownFields.has(f) ? (
                          <button
                            key={f}
                            type="button"
                            onMouseEnter={() => onHover(f)}
                            onMouseLeave={() => onHover(null)}
                            onClick={() => onSelect(f)}
                            className="rounded-md border border-line px-1.5 py-0.5 text-[11px] text-ink hover:border-navy/40"
                          >
                            {fieldLabel(f, data)}
                          </button>
                        ) : (
                          <span key={f} className="rounded-md bg-ink/5 px-1.5 py-0.5 text-[11px] text-muted">
                            {fieldLabel(f, data)}
                          </span>
                        ),
                      )}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      <p className="mt-3 text-xs text-muted">
        {postedDocuments ? c.memoryNote(postedDocuments) : memory?.vendor_seen ? c.memoryNote(memory.vendor_documents ?? 1) : c.memoryEmpty}
      </p>
    </Card>
  );
}
