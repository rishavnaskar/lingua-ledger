"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, CircleCheck, CircleMinus, CircleX, Equal, EqualNot, ListChecks, ScanText } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardTitle } from "@/components/ui/Card";
import { ConfidencePill } from "@/components/ui/ConfidencePill";
import type { FieldResult, RuleResult } from "@/lib/api";
import { copy } from "@/lib/copy";
import {
  cn,
  fieldLabel,
  fmt,
  formatValue,
  isPresent,
  ruleLabel,
  rulesForField,
  ruleStatus,
  sameValue,
} from "@/lib/format";
import type { Selection } from "./types";

type Filter = "all" | "review";

export function FieldsTable({
  fields,
  data,
  rules,
  threshold,
  hovered,
  onHover,
  selection,
  onSelect,
}: {
  fields: FieldResult[];
  data: Record<string, unknown>;
  rules: RuleResult[];
  threshold: number;
  hovered: string | null;
  onHover: (field: string | null) => void;
  selection: Selection | null;
  onSelect: (field: string) => void;
}) {
  const c = copy.workbench.fields;
  const [filter, setFilter] = useState<Filter>("all");
  const [showEmpty, setShowEmpty] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const rowRefs = useRef(new Map<string, HTMLTableRowElement>());

  const present = useMemo(() => fields.filter((f) => isPresent(f.value)), [fields]);
  const emptyCount = fields.length - present.length;
  const reviewCount = present.filter((f) => f.needs_review).length;

  const rows = useMemo(() => {
    const base = showEmpty ? fields : present;
    return filter === "review" ? base.filter((f) => f.needs_review) : base;
  }, [fields, present, showEmpty, filter]);

  useEffect(() => {
    if (!selection || selection.source === "table") return;
    const target = fields.find((f) => f.field === selection.field);
    if (!target) return;
    setExpanded((prev) => new Set(prev).add(selection.field));
    if (filter === "review" && !target.needs_review) setFilter("all");
    if (!isPresent(target.value)) setShowEmpty(true);
    const t = setTimeout(() => {
      rowRefs.current.get(selection.field)?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 60);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  const toggle = (field: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
    onSelect(field);
  };

  return (
    <Card>
      <CardTitle
        icon={ListChecks}
        aside={
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label={c.filterLabel} className="inline-flex rounded-lg border border-line bg-white p-0.5 text-sm">
              {(["all", "review"] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={filter === key}
                  onClick={() => setFilter(key)}
                  className={cn(
                    "rounded-md px-2.5 py-1 transition-colors",
                    filter === key ? "bg-navy text-white" : "text-muted hover:text-ink",
                  )}
                >
                  {key === "all" ? c.filterAll : c.filterReview}{" "}
                  <span className="font-mono text-xs tabular-nums opacity-80">
                    {key === "all" ? present.length : reviewCount}
                  </span>
                </button>
              ))}
            </div>
            {emptyCount > 0 && (
              <button
                type="button"
                onClick={() => setShowEmpty((v) => !v)}
                className="rounded-lg px-2 py-1 text-sm text-muted underline-offset-2 hover:text-ink hover:underline"
              >
                {showEmpty ? c.hideEmpty : c.showEmpty(emptyCount)}
              </button>
            )}
          </div>
        }
      >
        {c.title}
      </CardTitle>

      <div className="overflow-x-auto rounded-xl border border-line bg-white">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="w-[28%] py-2.5 pr-2 pl-4 font-medium">
                {c.columns.field}
              </th>
              <th scope="col" className="px-2 py-2.5 font-medium">
                {c.columns.value}
              </th>
              <th scope="col" className="w-24 px-2 py-2.5 font-medium">
                {c.columns.confidence}
              </th>
              <th scope="col" className="w-[30%] px-2 py-2.5 font-medium">
                {c.columns.evidence}
              </th>
              <th scope="col" className="w-10 py-2.5 pr-3">
                <span className="sr-only">{c.expand}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr className="border-t border-line">
                <td colSpan={5} className="px-4 py-8 text-center text-muted">
                  {filter === "review" ? c.noneReview : c.none}
                </td>
              </tr>
            )}
            {rows.map((f) => {
              const open = expanded.has(f.field);
              const isHovered = hovered === f.field;
              const has = isPresent(f.value);
              const label = fieldLabel(f.field, data);
              return (
                <Fragment key={f.field}>
                  <tr
                    ref={(el) => {
                      if (el) rowRefs.current.set(f.field, el);
                      else rowRefs.current.delete(f.field);
                    }}
                    onMouseEnter={() => onHover(f.field)}
                    onMouseLeave={() => onHover(null)}
                    onClick={() => toggle(f.field)}
                    className={cn(
                      "cursor-pointer border-t border-line align-top transition-colors",
                      isHovered ? "bg-paper" : f.needs_review ? "bg-amber/5" : "",
                    )}
                  >
                    <td className="py-2.5 pr-2 pl-4">
                      <div className="flex items-start gap-2.5">
                        <span
                          className={cn(
                            "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                            !has ? "bg-line" : f.needs_review ? "bg-amber" : "bg-teal",
                          )}
                          aria-hidden
                        />
                        <div className="min-w-0">
                          <div className={cn("font-medium", has ? "text-ink" : "text-muted")}>{label}</div>
                          <div className="font-mono text-[11px] break-all text-muted">{f.field}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-2 py-2.5">
                      {has ? (
                        <span className="font-mono text-[13px] break-words text-ink">{formatValue(f.value)}</span>
                      ) : (
                        <span className="text-muted italic">{copy.common.empty}</span>
                      )}
                    </td>
                    <td className="px-2 py-2.5">
                      <ConfidencePill value={f.confidence} threshold={threshold} present={has} />
                    </td>
                    <td className="px-2 py-2.5">
                      <Evidence f={f} />
                    </td>
                    <td className="py-2 pr-3 text-right">
                      <button
                        type="button"
                        aria-expanded={open}
                        aria-label={`${open ? c.collapse : c.expand}: ${label}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggle(f.field);
                        }}
                        className="rounded-md p-1 text-muted hover:bg-ink/5 hover:text-ink"
                      >
                        <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} aria-hidden />
                      </button>
                    </td>
                  </tr>
                  {open && (
                    <tr
                      className={cn(isHovered && "bg-paper")}
                      onMouseEnter={() => onHover(f.field)}
                      onMouseLeave={() => onHover(null)}
                    >
                      <td colSpan={5} className="px-4 pb-4">
                        <FieldDetail f={f} rules={rulesForField(rules, f.field)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Evidence({ f }: { f: FieldResult }) {
  const e = copy.workbench.fields.evidence;
  if (!isPresent(f.value)) return <span className="text-xs text-muted">{copy.common.notAvailable}</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {f.agree === true && (
        <Badge tone="teal" icon={Equal}>
          {e.agree}
        </Badge>
      )}
      {f.agree === false && (
        <Badge tone="amber" icon={EqualNot}>
          {e.disagree}
        </Badge>
      )}
      {f.agree === null && <Badge tone="muted">{e.single}</Badge>}
      {f.ocr_conf !== null && f.ocr_conf !== undefined ? (
        <Badge tone={f.ocr_conf < 0.6 ? "amber" : "navy"} icon={ScanText}>
          {e.ocr(fmt.score(f.ocr_conf))}
        </Badge>
      ) : (
        <Badge tone="muted" icon={ScanText}>
          {e.noOcr}
        </Badge>
      )}
      {f.validator === "pass" && (
        <Badge tone="teal" icon={CircleCheck}>
          {e.pass}
        </Badge>
      )}
      {f.validator === "fail" && (
        <Badge tone="brick" icon={CircleX}>
          {e.fail}
        </Badge>
      )}
    </div>
  );
}

function FieldDetail({ f, rules }: { f: FieldResult; rules: RuleResult[] }) {
  const d = copy.workbench.fields.detail;
  const v = copy.workbench.validators;
  const has = isPresent(f.value);
  const located = f.bbox ? d.locatedOn((f.page ?? 0) + 1) : d.notLocated;

  return (
    <div className="grid gap-5 rounded-xl bg-paper/60 p-4 md:grid-cols-3">
      <div>
        <h4 className="text-xs font-semibold tracking-wide text-muted uppercase">{d.readers}</h4>
        <dl className="mt-2 space-y-2">
          <ReaderValue name={d.vision} value={f.vision_value} kept={has && sameValue(f.vision_value, f.value)} />
          <ReaderValue name={d.ocr} value={f.ocr_value} kept={has && sameValue(f.ocr_value, f.value)} />
        </dl>
      </div>
      <div>
        <h4 className="text-xs font-semibold tracking-wide text-muted uppercase">{d.signals}</h4>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted">{d.raw}</dt>
          <dd className="font-mono tabular-nums">{fmt.score(f.raw_score)}</dd>
          <dt className="text-muted">{d.calibrated}</dt>
          <dd className="font-mono font-semibold tabular-nums">{fmt.score(f.confidence)}</dd>
          <dt className="text-muted">{d.ocrConf}</dt>
          <dd className="font-mono tabular-nums">
            {f.ocr_conf !== null && f.ocr_conf !== undefined ? fmt.score(f.ocr_conf) : copy.common.notAvailable}
          </dd>
          <dt className="text-muted">{d.selfConf}</dt>
          <dd className="font-mono tabular-nums">
            {f.self_conf !== null && f.self_conf !== undefined ? fmt.score(f.self_conf) : copy.common.notAvailable}
          </dd>
          <dt className="text-muted">{d.location}</dt>
          <dd>{located}</dd>
        </dl>
      </div>
      <div>
        <h4 className="text-xs font-semibold tracking-wide text-muted uppercase">{d.rules}</h4>
        {rules.length === 0 ? (
          <p className="mt-2 text-sm text-muted">{d.noRules}</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {rules.map((r, i) => {
              const status = ruleStatus(r);
              return (
                <li key={`${r.rule}-${i}`} className="flex items-start gap-2 text-sm">
                  <RuleIcon status={status} />
                  <span className="min-w-0">
                    <span className="font-medium text-ink">{ruleLabel(r.rule)}</span>{" "}
                    <span className="text-xs text-muted">{v.status[status]}</span>
                    {r.message && <span className="block text-muted">{r.message}</span>}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function ReaderValue({ name, value, kept }: { name: string; value: unknown; kept: boolean }) {
  const d = copy.workbench.fields.detail;
  const has = isPresent(value);
  return (
    <div>
      <dt className="flex items-center gap-2 text-xs text-muted">
        {name}
        {kept && <Badge tone="teal">{d.kept}</Badge>}
      </dt>
      <dd className={cn("mt-0.5 font-mono text-[13px] break-words", has ? "text-ink" : "text-muted italic")}>
        {has ? formatValue(value) : d.missing}
      </dd>
    </div>
  );
}

export function RuleIcon({ status }: { status: "pass" | "fail" | "na" }) {
  if (status === "pass") return <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-teal" aria-hidden />;
  if (status === "fail") return <CircleX className="mt-0.5 h-4 w-4 shrink-0 text-brick" aria-hidden />;
  return <CircleMinus className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden />;
}
