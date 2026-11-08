"use client";

import { useRef, useState } from "react";
import { FileUp, Upload } from "lucide-react";
import { MAX_UPLOAD_BYTES } from "@/lib/api";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/format";

const ACCEPT = "application/pdf,image/png,image/jpeg";
const ALLOWED = /\.(pdf|png|jpe?g)$/i;

export function DropZone({
  onFile,
  compact,
  disabled,
}: {
  onFile: (file: File) => void;
  compact?: boolean;
  disabled?: boolean;
}) {
  const c = copy.workbench.input;
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const accept = (file: File | undefined) => {
    if (!file || disabled) return;
    if (!ALLOWED.test(file.name) && !ACCEPT.split(",").includes(file.type)) {
      setProblem(c.wrongType);
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setProblem(c.tooLarge);
      return;
    }
    setProblem(null);
    onFile(file);
  };

  const open = () => {
    if (!disabled) inputRef.current?.click();
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={c.dropLabel}
        aria-disabled={disabled}
        onClick={open}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            open();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files?.[0]);
        }}
        className={cn(
          "flex cursor-pointer items-center rounded-xl border-2 border-dashed bg-white transition-colors",
          compact ? "gap-3 px-4 py-3" : "flex-col justify-center gap-2 px-6 py-10 text-center",
          dragging ? "border-teal bg-teal/5" : "border-line hover:border-navy/40",
          disabled && "cursor-not-allowed opacity-60",
        )}
      >
        {compact ? (
          <>
            <FileUp className="h-5 w-5 shrink-0 text-navy" aria-hidden />
            <span className="text-sm text-muted">{dragging ? c.dropActive : c.dropCompact}</span>
          </>
        ) : (
          <>
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-paper">
              <Upload className="h-5 w-5 text-navy" aria-hidden />
            </span>
            <span className="text-base font-medium text-ink">{dragging ? c.dropActive : c.dropTitle}</span>
            <span className="text-sm text-muted">{c.dropHint}</span>
            <span className="mt-2 inline-flex rounded-lg bg-teal px-3 py-1.5 text-sm font-medium text-white">
              {c.dropBrowse}
            </span>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          accept(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {problem && (
        <p role="alert" className="mt-2 text-sm text-brick-ink">
          {problem}
        </p>
      )}
    </div>
  );
}
