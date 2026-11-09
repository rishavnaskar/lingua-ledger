"use client";

import { useEffect, useRef, useState } from "react";
import { Circle, CircleCheck, LoaderCircle } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { copy } from "@/lib/copy";
import { cn, fmt } from "@/lib/format";

const READERS_AFTER_MS = 1200;
const STEP_MS = 220;
const FINAL_STAGE = copy.workbench.steps.length - 1;

type Status = "done" | "active" | "pending";

function statusFor(step: number, stage: number): Status {
  if (stage === 0) return step === 0 ? "active" : "pending";
  if (step <= 2) {
    if (stage >= 2 || step === 0) return "done";
    return "active";
  }
  const at = step - 1;
  return at < stage ? "done" : at === stage ? "active" : "pending";
}

export function PipelineStepper({
  name,
  arrived,
  onComplete,
}: {
  name: string;
  arrived: boolean;
  onComplete: () => void;
}) {
  const c = copy.workbench;
  const [stage, setStage] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const completeRef = useRef(onComplete);
  const arrivedRef = useRef(arrived);

  useEffect(() => {
    completeRef.current = onComplete;
    arrivedRef.current = arrived;
  });

  useEffect(() => {
    const t0 = performance.now();
    const tick = setInterval(() => {
      if (!arrivedRef.current) setElapsed((performance.now() - t0) / 1000);
    }, 100);
    const toReaders = setTimeout(() => setStage((s) => Math.max(s, 1)), READERS_AFTER_MS);
    return () => {
      clearInterval(tick);
      clearTimeout(toReaders);
    };
  }, []);

  useEffect(() => {
    if (!arrived) return;
    const t = setTimeout(
      () => {
        if (stage >= FINAL_STAGE) completeRef.current();
        else setStage(stage + 1);
      },
      stage >= FINAL_STAGE ? 300 : STEP_MS,
    );
    return () => clearTimeout(t);
  }, [arrived, stage]);

  return (
    <Card aria-live="polite" aria-busy={stage < FINAL_STAGE}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="min-w-0 truncate text-lg font-semibold text-ink">{c.progress.title(name)}</h2>
        <span className="font-mono text-sm text-muted tabular-nums">{c.progress.elapsed(fmt.seconds(elapsed))}</span>
      </div>
      <ol className="mt-5 space-y-1">
        {c.steps.map((step, i) => {
          const status = statusFor(i, stage);
          const parallel = i === 1 || i === 2;
          return (
            <li
              key={step.label}
              className={cn(
                "flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors",
                status === "active" && "bg-white",
                parallel && "ml-0 sm:ml-4",
              )}
            >
              <span className="mt-0.5 shrink-0">
                {status === "done" && <CircleCheck className="h-5 w-5 text-teal" aria-hidden />}
                {status === "active" && <LoaderCircle className="h-5 w-5 animate-spin text-navy" aria-hidden />}
                {status === "pending" && <Circle className="h-5 w-5 text-line" aria-hidden />}
              </span>
              <span className="min-w-0">
                <span className={cn("block text-sm font-medium", status === "pending" ? "text-muted" : "text-ink")}>
                  {step.label}
                </span>
                <span className="block text-sm text-muted">{step.detail}</span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="mt-4 text-xs text-muted">{c.progress.note}</p>
    </Card>
  );
}
