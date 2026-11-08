"use client";

import { Eye, GitCompareArrows, ScanText } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/Card";
import type { FieldResult, PathOutput, ReaderPath } from "@/lib/api";
import { copy } from "@/lib/copy";
import { fieldLabel, fmt, formatValue, isPresent } from "@/lib/format";

const READERS: { path: ReaderPath; icon: typeof Eye; valueKey: "vision_value" | "ocr_value" }[] = [
  { path: "vision", icon: Eye, valueKey: "vision_value" },
  { path: "ocr_text", icon: ScanText, valueKey: "ocr_value" },
];

const MAX_DIFFS = 5;

export function ReadersPanel({
  paths,
  fields,
  data,
  onHover,
  onSelect,
}: {
  paths: PathOutput[];
  fields: FieldResult[];
  data: Record<string, unknown>;
  onHover: (field: string | null) => void;
  onSelect: (field: string) => void;
}) {
  const c = copy.workbench.readers;
  const compared = fields.filter((f) => f.agree !== null);
  const agreed = compared.filter((f) => f.agree === true).length;
  const onlyOne = compared.filter(
    (f) => f.agree === false && isPresent(f.vision_value) !== isPresent(f.ocr_value),
  ).length;
  const diffs = compared.filter(
    (f) => f.agree === false && isPresent(f.vision_value) && isPresent(f.ocr_value),
  );

  return (
    <Card>
      <CardTitle icon={GitCompareArrows}>{c.title}</CardTitle>
      <div className="grid gap-3 sm:grid-cols-2">
        {READERS.map(({ path, icon: Icon, valueKey }) => {
          const out = paths.find((p) => p.path === path);
          const found = fields.filter((f) => isPresent(f[valueKey])).length;
          return (
            <div key={path} className="rounded-xl border border-line bg-white p-4">
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4 text-navy" aria-hidden />
                <h3 className="text-sm font-semibold text-ink">{c.names[path]}</h3>
              </div>
              <p className="mt-0.5 text-xs text-muted">{c.descriptions[path]}</p>
              {!out ? (
                <p className="mt-3 text-sm text-muted">{c.notRun}</p>
              ) : (
                <>
                  {out.error && (
                    <p className="mt-3 rounded-lg bg-brick/10 px-2.5 py-1.5 text-xs break-words text-brick-ink">
                      {c.failed}: {out.error}
                    </p>
                  )}
                  <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                    <dt className="text-muted">{c.latency}</dt>
                    <dd className="text-right font-mono tabular-nums">{fmt.seconds(out.latency_s)}</dd>
                    <dt className="text-muted">{c.tokensIn}</dt>
                    <dd className="text-right font-mono tabular-nums">{fmt.int(out.input_tokens)}</dd>
                    <dt className="text-muted">{c.tokensOut}</dt>
                    <dd className="text-right font-mono tabular-nums">{fmt.int(out.output_tokens)}</dd>
                    <dt className="text-muted">{c.fieldsFound}</dt>
                    <dd className="text-right font-mono tabular-nums">{found}</dd>
                  </dl>
                </>
              )}
            </div>
          );
        })}
      </div>

      {compared.length > 0 && (
        <div className="mt-4 rounded-xl border border-line bg-white p-4">
          <p className="text-sm font-medium text-ink">{c.agreement(agreed, compared.length)}</p>
          <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-paper" aria-hidden>
            <div className="bg-teal" style={{ width: `${(agreed / compared.length) * 100}%` }} />
          </div>
          {onlyOne > 0 && <p className="mt-2 text-xs text-muted">{c.onlyOne(onlyOne)}</p>}
          <h4 className="mt-4 text-xs font-semibold tracking-wide text-muted uppercase">{c.differences}</h4>
          {diffs.length === 0 ? (
            <p className="mt-1 text-sm text-muted">{c.noDifferences}</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {diffs.slice(0, MAX_DIFFS).map((f) => (
                <li key={f.field}>
                  <button
                    type="button"
                    onMouseEnter={() => onHover(f.field)}
                    onMouseLeave={() => onHover(null)}
                    onClick={() => onSelect(f.field)}
                    className="w-full rounded-lg px-2 py-1.5 text-left text-sm hover:bg-paper"
                  >
                    <span className="block font-medium text-ink">{fieldLabel(f.field, data)}</span>
                    <span className="grid gap-x-3 font-mono text-xs text-muted sm:grid-cols-2">
                      <span className="break-words">
                        <span className="font-sans">{c.names.vision}:</span> {formatValue(f.vision_value)}
                      </span>
                      <span className="break-words">
                        <span className="font-sans">{c.names.ocr_text}:</span> {formatValue(f.ocr_value)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
              {diffs.length > MAX_DIFFS && (
                <li className="px-2 text-xs text-muted">{c.more(diffs.length - MAX_DIFFS)}</li>
              )}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}
