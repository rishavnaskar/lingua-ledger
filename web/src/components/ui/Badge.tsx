import { cn } from "@/lib/format";

export type Tone = "teal" | "amber" | "brick" | "navy" | "muted";

const tones: Record<Tone, string> = {
  teal: "bg-teal/10 text-teal-ink",
  amber: "bg-amber/20 text-amber-ink",
  brick: "bg-brick/10 text-brick-ink",
  navy: "bg-navy/10 text-navy",
  muted: "bg-ink/5 text-muted",
};

export function Badge({
  tone = "muted",
  icon: Icon,
  children,
  title,
}: {
  tone?: Tone;
  icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] leading-4 font-medium whitespace-nowrap",
        tones[tone],
      )}
    >
      {Icon && <Icon className="h-3 w-3 shrink-0" aria-hidden />}
      {children}
    </span>
  );
}
