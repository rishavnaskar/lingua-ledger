"use client";

import { useId } from "react";
import { ChevronRight } from "lucide-react";
import { DOC_TYPES, type DocType } from "@/lib/api";
import { copy } from "@/lib/copy";
import { ThresholdSlider } from "@/components/ui/ThresholdSlider";

export function OptionsPanel({
  docType,
  onDocType,
  threshold,
  onThreshold,
  disabled,
}: {
  docType: DocType | "";
  onDocType: (v: DocType | "") => void;
  threshold: number;
  onThreshold: (v: number) => void;
  disabled?: boolean;
}) {
  const c = copy.workbench.options;
  const selectId = useId();
  return (
    <details className="group rounded-xl border border-line bg-white">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm font-medium text-ink [&::-webkit-details-marker]:hidden">
        <ChevronRight className="h-4 w-4 text-muted transition-transform group-open:rotate-90" aria-hidden />
        {c.title}
      </summary>
      <div className="space-y-5 border-t border-line px-4 py-4">
        <div>
          <label htmlFor={selectId} className="text-sm font-medium text-ink">
            {c.docType}
          </label>
          <select
            id={selectId}
            value={docType}
            disabled={disabled}
            onChange={(e) => onDocType(e.target.value as DocType | "")}
            className="mt-2 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink disabled:opacity-50"
          >
            <option value="">{c.docTypeAuto}</option>
            {DOC_TYPES.map((t) => (
              <option key={t} value={t}>
                {copy.docTypes[t]}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-muted">{c.docTypeNote}</p>
        </div>
        <ThresholdSlider
          label={c.threshold}
          hint={c.thresholdNote}
          value={threshold}
          onChange={onThreshold}
          disabled={disabled}
        />
      </div>
    </details>
  );
}
