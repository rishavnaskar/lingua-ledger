"use client";

import { ShieldCheck } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/Card";
import type { RuleResult } from "@/lib/api";
import { copy } from "@/lib/copy";
import { cn, fieldLabel, ruleLabel, ruleStatus } from "@/lib/format";
import { RuleIcon } from "./FieldsTable";

const ORDER = { fail: 0, pass: 1, na: 2 } as const;

export function ValidatorsPanel({
  rules,
  data,
  knownFields,
  onHover,
  onSelect,
}: {
  rules: RuleResult[];
  data: Record<string, unknown>;
  knownFields: Set<string>;
  onHover: (field: string | null) => void;
  onSelect: (field: string) => void;
}) {
  const c = copy.workbench.validators;
  const counts = { pass: 0, fail: 0, na: 0 };
  rules.forEach((r) => counts[ruleStatus(r)]++);
  const sorted = [...rules].sort((a, b) => ORDER[ruleStatus(a)] - ORDER[ruleStatus(b)]);

  return (
    <Card>
      <CardTitle
        icon={ShieldCheck}
        aside={rules.length > 0 && <span className="text-xs text-muted">{c.summary(counts.pass, counts.fail, counts.na)}</span>}
      >
        {c.title}
      </CardTitle>
      {rules.length === 0 ? (
        <p className="text-sm text-muted">{c.empty}</p>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-white">
          {sorted.map((r, i) => {
            const status = ruleStatus(r);
            return (
              <li key={`${r.rule}-${i}`} className={cn("flex gap-3 px-4 py-3", status === "fail" && "bg-brick/5")}>
                <RuleIcon status={status} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-sm font-medium text-ink">{ruleLabel(r.rule)}</span>
                    <span
                      className={cn(
                        "text-xs",
                        status === "fail" ? "text-brick-ink" : status === "pass" ? "text-teal-ink" : "text-muted",
                      )}
                    >
                      {c.status[status]}
                    </span>
                  </div>
                  {r.message && <p className="mt-0.5 text-sm break-words text-muted">{r.message}</p>}
                  {r.fields.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {r.fields.map((f) =>
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
    </Card>
  );
}
