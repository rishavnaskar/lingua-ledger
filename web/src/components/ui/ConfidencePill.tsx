import { cn, fmt } from "@/lib/format";

export function ConfidencePill({ value, threshold, present = true }: { value: number; threshold: number; present?: boolean }) {
  if (!present) {
    return (
      <span className="inline-flex min-w-[3.25rem] justify-center rounded-full border border-line px-2 py-0.5 font-mono text-xs text-muted">
        -
      </span>
    );
  }
  const ok = value >= threshold;
  return (
    <span
      className={cn(
        "inline-flex min-w-[3.25rem] justify-center rounded-full px-2 py-0.5 font-mono text-xs font-semibold tabular-nums",
        ok ? "bg-teal text-white" : "bg-amber text-ink",
      )}
    >
      {fmt.score(value)}
    </span>
  );
}
