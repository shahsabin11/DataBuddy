"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  deleteDataset,
  fetchDatasets,
  uploadDataset,
  type DatasetRow,
} from "@/lib/api";

const MAX_BYTES = 500 * 1024 * 1024;
const ACCEPT = ".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function formatBytes(n: number | null): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function DatasetUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setDatasets(await fetchDatasets());
    } catch {
      // Session gate handles auth; keep list empty on transient errors.
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setError(null);

    const lower = file.name.toLowerCase();
    if (!lower.endsWith(".csv") && !lower.endsWith(".xlsx")) {
      setError("Only CSV and XLSX files are accepted.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("File exceeds the 500 MB upload limit.");
      return;
    }

    setProgress(0);
    try {
      await uploadDataset(file, { onProgress: setProgress });
      setProgress(null);
      await reload();
    } catch (err) {
      setProgress(null);
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  return (
    <section className="rounded-lg border border-ink/10 bg-white/70 p-5 shadow-sm backdrop-blur">
      <h2 className="font-display text-2xl text-ink">Dataset</h2>
      <p className="mt-2 text-sm text-ink/70">
        Upload a CSV or XLSX (max 500 MB). The original file is stored privately
        and never overwritten.
      </p>

      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        onDragEnter={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void handleFile(e.dataTransfer.files?.[0]);
        }}
        onClick={() => inputRef.current?.click()}
        className={`mt-5 cursor-pointer rounded-md border border-dashed px-4 py-10 text-center transition ${
          dragging
            ? "border-accent bg-accent/5"
            : "border-ink/20 bg-paper/80 hover:border-accent/50"
        }`}
      >
        <p className="text-sm font-medium text-ink">
          Drag and drop a file here, or click to browse
        </p>
        <p className="mt-1 text-xs text-ink/50">CSV or XLSX · up to 500 MB</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            void handleFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>

      {progress != null ? (
        <div className="mt-4">
          <div className="h-2 overflow-hidden rounded-full bg-ink/10">
            <div
              className="h-full bg-accent transition-[width]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-ink/55">Uploading… {progress}%</p>
        </div>
      ) : null}

      {error ? (
        <p
          className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      {datasets.length > 0 ? (
        <ul className="mt-6 divide-y divide-ink/10 border-t border-ink/10">
          {datasets.map((ds) => (
            <li
              key={ds.id}
              className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"
            >
              <div>
                <div className="font-medium text-ink">{ds.name}</div>
                <div className="text-xs text-ink/55">
                  {ds.original_filename} · {formatBytes(ds.byte_size)}
                  {ds.row_count != null ? ` · ${ds.row_count} rows` : ""}
                  {ds.status !== "ready" ? ` · ${ds.status}` : ""}
                </div>
              </div>
              <button
                type="button"
                disabled={busyId === ds.id}
                className="rounded-md border border-ink/15 px-3 py-1.5 text-xs text-ink/70 hover:bg-ink/5 disabled:opacity-50"
                onClick={() => {
                  setBusyId(ds.id);
                  void deleteDataset(ds.id)
                    .then(reload)
                    .catch(() => setError("Could not delete dataset."))
                    .finally(() => setBusyId(null));
                }}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
