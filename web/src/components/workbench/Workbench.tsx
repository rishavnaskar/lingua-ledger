"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleAlert, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  DEFAULT_THRESHOLD,
  extractFile,
  extractSample,
  sampleFileUrl,
  type DocType,
  type ExtractResponse,
  type Sample,
} from "@/lib/api";
import { copy } from "@/lib/copy";
import { describeError } from "@/lib/errors";
import { buildExport, downloadText, exportBaseName, isPresent, routeFields, toCsv } from "@/lib/format";
import { DocumentViewer, PendingPreview } from "./DocumentViewer";
import { DropZone } from "./DropZone";
import { FieldsTable } from "./FieldsTable";
import { OptionsPanel } from "./OptionsPanel";
import { PipelineStepper } from "./PipelineStepper";
import { ReadersPanel } from "./ReadersPanel";
import { ResultHeader } from "./ResultHeader";
import { SampleChips } from "./SampleChips";
import { ValidatorsPanel } from "./ValidatorsPanel";
import type { Selection, SelectionSource } from "./types";

type Phase = "idle" | "loading" | "done" | "error";

interface Job {
  name: string;
  preview: string | null;
  sampleId: string | null;
  run: (signal: AbortSignal) => Promise<ExtractResponse>;
}

const IMAGE_FILE = /\.(png|jpe?g|webp|gif)$/i;

export function Workbench() {
  const c = copy.workbench;
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<Job | null>(null);
  const [runId, setRunId] = useState(0);
  const [arrived, setArrived] = useState<ExtractResponse | null>(null);
  const [result, setResult] = useState<ExtractResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [docType, setDocType] = useState<DocType | "">("");
  const [hovered, setHovered] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    },
    [],
  );

  const start = useCallback(async (next: Job) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setJob(next);
    setRunId((id) => id + 1);
    setArrived(null);
    setError(null);
    setPhase("loading");
    try {
      const res = await next.run(ctrl.signal);
      if (!ctrl.signal.aborted) setArrived(res);
    } catch (err) {
      if (ctrl.signal.aborted) return;
      setError(describeError(err));
      setPhase("error");
    }
  }, []);

  const handleFile = (file: File) => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
    objectUrlRef.current = preview;
    const opts = { threshold, docType: docType || null };
    start({
      name: file.name,
      preview,
      sampleId: null,
      run: (signal) => extractFile(file, { ...opts, signal }),
    });
  };

  const handleSample = (sample: Sample) => {
    const opts = { threshold };
    start({
      name: sample.title,
      preview: IMAGE_FILE.test(sample.file) ? sampleFileUrl(sample.id) : null,
      sampleId: sample.id,
      run: (signal) => extractSample(sample.id, { ...opts, signal }),
    });
  };

  const commit = useCallback(() => {
    if (!arrived) return;
    setResult(arrived);
    setThreshold(arrived.review_threshold ?? DEFAULT_THRESHOLD);
    setHovered(null);
    setSelection(null);
    setPhase("done");
  }, [arrived]);

  const select = useCallback((field: string, source: SelectionSource) => {
    setSelection({ field, source, nonce: Date.now() });
  }, []);

  const routed = useMemo(() => (result ? routeFields(result.fields, threshold) : []), [result, threshold]);
  const present = useMemo(() => routed.filter((f) => isPresent(f.value)), [routed]);
  const reviewCount = present.filter((f) => f.needs_review).length;
  const knownFields = useMemo(() => new Set(routed.map((f) => f.field)), [routed]);

  const exportJson = () => {
    if (!result) return;
    const body = JSON.stringify(buildExport(result, routed, threshold), null, 2);
    downloadText(`${exportBaseName(result.filename)}.json`, body, "application/json");
  };

  const exportCsv = () => {
    if (!result) return;
    downloadText(`${exportBaseName(result.filename)}.csv`, `﻿${toCsv(routed)}`, "text/csv;charset=utf-8");
  };

  const busy = phase === "loading";
  const showResult = phase === "done" && result;

  return (
    <div className="space-y-6">
      <header className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{c.heading}</h1>
        <p className="mt-1.5 text-muted">{c.intro}</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(320px,400px)_minmax(0,1fr)] xl:grid-cols-[minmax(360px,5fr)_minmax(0,7fr)]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-ink uppercase">{c.input.title}</h2>
            <div className="space-y-5">
              <DropZone onFile={handleFile} compact={phase !== "idle"} disabled={busy} />
              <SampleChips onPick={handleSample} activeId={job?.sampleId ?? null} disabled={busy} />
              <OptionsPanel
                docType={docType}
                onDocType={setDocType}
                threshold={threshold}
                onThreshold={setThreshold}
                disabled={busy}
              />
            </div>
          </Card>

          {showResult && (
            <div className="lg:sticky lg:top-20">
              <DocumentViewer
                pages={result.pages_preview ?? []}
                fields={routed}
                data={result.data}
                hovered={hovered}
                onHover={setHovered}
                selection={selection}
                onSelect={(f) => select(f, "viewer")}
              />
            </div>
          )}
          {busy && job?.preview && <PendingPreview key={job.preview} src={job.preview} />}
        </div>

        <div className="flex min-w-0 flex-col gap-6">
          {phase === "idle" && <IdleState />}

          {busy && job && (
            <PipelineStepper key={runId} name={job.name} arrived={arrived !== null} onComplete={commit} />
          )}

          {phase === "error" && (
            <Card role="alert" className="border border-brick/30 bg-brick/5">
              <div className="flex items-start gap-3">
                <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-brick" aria-hidden />
                <div className="min-w-0">
                  <h2 className="font-semibold text-ink">{c.error.title}</h2>
                  <p className="mt-1 text-sm break-words text-muted">{error}</p>
                  {job && (
                    <Button className="mt-3" icon={RotateCcw} onClick={() => start(job)}>
                      {c.error.retry}
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          )}

          {showResult && (
            <>
              <ResultHeader
                result={result}
                threshold={threshold}
                onThreshold={setThreshold}
                reviewCount={reviewCount}
                total={present.length}
                onExportJson={exportJson}
                onExportCsv={exportCsv}
              />
              <FieldsTable
                fields={routed}
                data={result.data}
                rules={result.rules}
                threshold={threshold}
                hovered={hovered}
                onHover={setHovered}
                selection={selection}
                onSelect={(f) => select(f, "table")}
              />
              <div className="grid gap-6 2xl:grid-cols-2">
                <ValidatorsPanel
                  rules={result.rules}
                  data={result.data}
                  knownFields={knownFields}
                  onHover={setHovered}
                  onSelect={(f) => select(f, "panel")}
                />
                <ReadersPanel
                  paths={result.paths}
                  fields={routed}
                  data={result.data}
                  onHover={setHovered}
                  onSelect={(f) => select(f, "panel")}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function IdleState() {
  const c = copy.workbench.idle;
  return (
    <Card className="flex min-h-[320px] flex-col justify-center">
      <h2 className="text-lg font-semibold text-ink">{c.title}</h2>
      <p className="mt-2 max-w-2xl text-muted">{c.body}</p>
      <ul className="mt-5 space-y-2">
        {c.points.map((p) => (
          <li key={p} className="flex items-start gap-2.5 text-sm text-ink">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal" aria-hidden />
            {p}
          </li>
        ))}
      </ul>
      <ol className="mt-6 flex flex-wrap gap-2" aria-label={copy.about.diagramLabel}>
        {copy.workbench.steps.map((s, i) => (
          <li key={s.label} className="rounded-lg border border-line bg-white px-2.5 py-1 text-xs text-muted">
            <span className="mr-1 font-mono text-navy">{i + 1}</span>
            {s.label}
          </li>
        ))}
      </ol>
    </Card>
  );
}
