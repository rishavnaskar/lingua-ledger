"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useMemo, useRef, useState } from "react";
import { FileText } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/Card";
import type { FieldResult, PagePreview } from "@/lib/api";
import { copy } from "@/lib/copy";
import { cn, fieldLabel, fmt, formatValue, isPresent } from "@/lib/format";
import type { Selection } from "./types";

const PAD = 3;

export function DocumentViewer({
  pages,
  fields,
  data,
  hovered,
  onHover,
  selection,
  onSelect,
}: {
  pages: PagePreview[];
  fields: FieldResult[];
  data: Record<string, unknown>;
  hovered: string | null;
  onHover: (field: string | null) => void;
  selection: Selection | null;
  onSelect: (field: string) => void;
}) {
  const c = copy.workbench.viewer;
  const [showBoxes, setShowBoxes] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const boxRefs = useRef(new Map<string, HTMLButtonElement>());

  const present = useMemo(() => fields.filter((f) => isPresent(f.value)), [fields]);
  const located = useMemo(
    () =>
      present
        .filter((f) => f.bbox && pages[f.page ?? 0])
        .sort((a, b) => area(b) - area(a)),
    [present, pages],
  );
  const unlocated = present.length - located.length;

  useEffect(() => {
    if (!selection || selection.source === "viewer") return;
    const box = boxRefs.current.get(selection.field);
    const container = scrollRef.current;
    if (!box || !container) return;
    const b = box.getBoundingClientRect();
    const r = container.getBoundingClientRect();
    if (b.top < r.top || b.bottom > r.bottom) {
      container.scrollBy({ top: b.top - r.top - r.height / 2 + b.height / 2, behavior: "smooth" });
    }
  }, [selection]);

  return (
    <Card>
      <CardTitle
        icon={FileText}
        aside={
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={showBoxes}
              onChange={(e) => setShowBoxes(e.target.checked)}
              className="h-4 w-4 accent-teal"
            />
            {c.showBoxes}
          </label>
        }
      >
        {c.title}
      </CardTitle>

      <div
        ref={scrollRef}
        className="max-h-[75vh] space-y-3 overflow-auto rounded-xl border border-line bg-white lg:max-h-[calc(100vh-15rem)]"
      >
        {pages.map((page) => (
          <figure key={page.index} className="relative">
            <img
              src={page.data_url}
              alt={c.alt(page.index + 1)}
              width={page.width}
              height={page.height}
              draggable={false}
              className="block h-auto w-full select-none"
            />
            {located
              .filter((f) => (f.page ?? 0) === page.index)
              .map((f) => {
                const [x0, y0, x1, y1] = f.bbox!;
                const active = hovered === f.field;
                const visible = showBoxes || active;
                const dim = hovered !== null && !active;
                const label = fieldLabel(f.field, data);
                const nearTop = y0 / page.height < 0.06;
                return (
                  <button
                    key={f.field}
                    type="button"
                    ref={(el) => {
                      if (el) boxRefs.current.set(f.field, el);
                      else boxRefs.current.delete(f.field);
                    }}
                    aria-label={`${label}: ${formatValue(f.value)}`}
                    onMouseEnter={() => onHover(f.field)}
                    onMouseLeave={() => onHover(null)}
                    onFocus={() => onHover(f.field)}
                    onBlur={() => onHover(null)}
                    onClick={() => onSelect(f.field)}
                    style={{
                      left: `${((x0 - PAD) / page.width) * 100}%`,
                      top: `${((y0 - PAD) / page.height) * 100}%`,
                      width: `${((x1 - x0 + 2 * PAD) / page.width) * 100}%`,
                      height: `${((y1 - y0 + 2 * PAD) / page.height) * 100}%`,
                    }}
                    className={cn(
                      "absolute rounded-[3px] border-2 transition-opacity",
                      f.needs_review ? "border-amber bg-amber/15" : "border-teal bg-teal/10",
                      active && (f.needs_review ? "z-10 bg-amber/30" : "z-10 bg-teal/25"),
                      !visible && "pointer-events-none opacity-0",
                      visible && dim && "opacity-30",
                    )}
                  >
                    {active && (
                      <span
                        className={cn(
                          "pointer-events-none absolute left-0 rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap text-white",
                          nearTop ? "top-full mt-1" : "bottom-full mb-1",
                          f.needs_review ? "bg-amber-ink" : "bg-teal-ink",
                        )}
                      >
                        {label} · {fmt.score(f.confidence)}
                      </span>
                    )}
                  </button>
                );
              })}
            {pages.length > 1 && (
              <figcaption className="absolute top-2 right-2 rounded bg-ink/75 px-1.5 py-0.5 text-[11px] text-white">
                {c.pageLabel(page.index + 1, pages.length)}
              </figcaption>
            )}
          </figure>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm border-2 border-teal" aria-hidden />
          {copy.workbench.result.accepted}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm border-2 border-amber" aria-hidden />
          {copy.workbench.result.needsReview}
        </span>
        {unlocated > 0 && <span>{c.unlocated(unlocated)}</span>}
      </div>
    </Card>
  );
}

function area(f: FieldResult): number {
  if (!f.bbox) return 0;
  const [x0, y0, x1, y1] = f.bbox;
  return (x1 - x0) * (y1 - y0);
}

export function PendingPreview({ src }: { src: string }) {
  const c = copy.workbench.viewer;
  return (
    <Card>
      <CardTitle icon={FileText}>{c.title}</CardTitle>
      <div className="relative overflow-hidden rounded-xl border border-line bg-white">
        <img src={src} alt={c.alt(1)} className="block h-auto w-full opacity-60" />
        <span className="absolute top-3 left-3 inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-navy shadow-sm">
          <span className="h-2 w-2 animate-pulse rounded-full bg-teal" aria-hidden />
          {c.reading}
        </span>
      </div>
    </Card>
  );
}
