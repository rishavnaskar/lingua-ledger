"use client";

import { useEffect, useState } from "react";
import { getSamples, type Sample } from "@/lib/api";
import { copy } from "@/lib/copy";
import { isAbort } from "@/lib/errors";
import { cn } from "@/lib/format";

type State = { status: "loading" } | { status: "error" } | { status: "ready"; samples: Sample[] };

export function SampleChips({
  onPick,
  activeId,
  disabled,
}: {
  onPick: (s: Sample) => void;
  activeId: string | null;
  disabled?: boolean;
}) {
  const c = copy.workbench.samples;
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    getSamples(ctrl.signal)
      .then((samples) => setState({ status: "ready", samples: Array.isArray(samples) ? samples : [] }))
      .catch((err) => {
        if (!isAbort(err)) setState({ status: "error" });
      });
    return () => ctrl.abort();
  }, []);

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">{c.title}</h3>
      {state.status === "loading" && <p className="text-sm text-muted">{c.loading}</p>}
      {state.status === "error" && <p className="text-sm text-muted">{c.failed}</p>}
      {state.status === "ready" && state.samples.length === 0 && <p className="text-sm text-muted">{c.empty}</p>}
      {state.status === "ready" && state.samples.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {state.samples.map((s) => {
            const active = s.id === activeId;
            return (
              <li key={s.id}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onPick(s)}
                  aria-pressed={active}
                  title={s.title}
                  className={cn(
                    "inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-1 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                    active
                      ? "border-teal bg-teal/10 text-ink"
                      : "border-line bg-white text-ink hover:border-navy/40",
                  )}
                >
                  <span className="max-w-[14rem] truncate">{s.title}</span>
                  <span className="text-xs text-muted">
                    {copy.docTypes[s.doc_type] ?? s.doc_type} · {s.language.toUpperCase()}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
