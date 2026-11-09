import type { Metadata } from "next";
import Link from "next/link";
import { ArrowDown, ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/format";

export const metadata: Metadata = { title: copy.about.heading };

type BoxTone = "plain" | "navy" | "teal" | "amber";

const boxTones: Record<BoxTone, string> = {
  plain: "border-line bg-white",
  navy: "border-navy/30 bg-navy/5",
  teal: "border-teal/40 bg-teal/10",
  amber: "border-amber/60 bg-amber/15",
};

function Box({ title, body, tone = "plain" }: { title: string; body: string; tone?: BoxTone }) {
  return (
    <div className={cn("rounded-xl border px-3.5 py-3", boxTones[tone])}>
      <div className="text-sm font-semibold text-ink">{title}</div>
      <div className="mt-0.5 text-xs text-muted">{body}</div>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex shrink-0 items-center justify-center text-muted" aria-hidden>
      <ArrowDown className="h-4 w-4 lg:hidden" />
      <ArrowRight className="hidden h-4 w-4 lg:block" />
    </div>
  );
}

export default function AboutPage() {
  const c = copy.about;
  const d = c.diagram;
  return (
    <div className="space-y-8">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{c.heading}</h1>
        <p className="mt-1.5 text-muted">{c.intro}</p>
      </header>

      <Card>
        <div role="figure" aria-label={c.diagramLabel} className="flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-3">
          <div className="lg:min-w-0 lg:flex-1">
            <Box {...d.document} />
          </div>
          <Arrow />
          <div className="flex flex-col gap-2 lg:min-w-0 lg:flex-1">
            <Box {...d.vision} tone="navy" />
            <Box {...d.ocr} tone="navy" />
          </div>
          <Arrow />
          <div className="flex flex-col gap-2 lg:min-w-0 lg:flex-1">
            <Box {...d.arbiter} tone="navy" />
            <Box {...d.validators} tone="navy" />
          </div>
          <Arrow />
          <div className="lg:min-w-0 lg:flex-1">
            <Box {...d.confidence} tone="teal" />
          </div>
          <Arrow />
          <div className="flex flex-col gap-2 lg:min-w-0 lg:flex-1">
            <Box {...d.accept} tone="teal" />
            <Box {...d.review} tone="amber" />
          </div>
        </div>
      </Card>

      <section>
        <h2 className="text-lg font-semibold text-ink">{c.signalsTitle}</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {c.signals.map((s, i) => (
            <Card key={s.title} as="article">
              <div className="font-mono text-xs text-navy">{String(i + 1).padStart(2, "0")}</div>
              <h3 className="mt-1 font-semibold text-ink">{s.title}</h3>
              <p className="mt-1.5 text-sm text-muted">{s.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card as="article">
          <h2 className="text-lg font-semibold text-ink">{c.memoryTitle}</h2>
          <p className="mt-2 text-sm text-muted">{c.memory}</p>
        </Card>
        <Card as="article">
          <h2 className="text-lg font-semibold text-ink">{c.calibrationTitle}</h2>
          <p className="mt-2 text-sm text-muted">{c.calibration}</p>
          <Link href="/metrics" className="mt-3 inline-block text-sm font-medium text-teal-ink hover:underline">
            {copy.site.nav.evidence}
          </Link>
        </Card>
        <Card as="article">
          <h2 className="text-lg font-semibold text-ink">{c.routingTitle}</h2>
          <p className="mt-2 text-sm text-muted">{c.routing}</p>
          <Link href="/" className="mt-3 inline-block text-sm font-medium text-teal-ink hover:underline">
            {copy.site.nav.workbench}
          </Link>
        </Card>
      </div>
    </div>
  );
}
