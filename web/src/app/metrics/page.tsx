import type { Metadata } from "next";
import { MetricsView } from "@/components/metrics/MetricsView";
import { copy } from "@/lib/copy";

export const metadata: Metadata = { title: copy.metrics.heading };

export default function MetricsPage() {
  return <MetricsView />;
}
