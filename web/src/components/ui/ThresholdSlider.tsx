"use client";

import { useId } from "react";
import { fmt } from "@/lib/format";

export const THRESHOLD_MIN = 0.5;
export const THRESHOLD_MAX = 0.99;

export function ThresholdSlider({
  label,
  hint,
  value,
  onChange,
  disabled,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
        </label>
        <output htmlFor={id} className="font-mono text-sm font-semibold text-ink tabular-nums">
          {fmt.score(value)}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={THRESHOLD_MIN}
        max={THRESHOLD_MAX}
        step={0.01}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
      />
      <div className="mt-0.5 flex justify-between font-mono text-[11px] text-muted">
        <span>{fmt.score(THRESHOLD_MIN)}</span>
        <span>{fmt.score(THRESHOLD_MAX)}</span>
      </div>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}
