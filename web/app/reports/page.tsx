"use client";

import { useEffect, useState } from "react";
import { apiGet, reportUrl, type Case } from "@/lib/api";

export default function ReportsPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [caseId, setCaseId] = useState("");
  const [preview, setPreview] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const list = await apiGet<Case[]>("/api/v1/cases");
        setCases(list);
        if (list.length) setCaseId(list[0].id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed");
      }
    })();
  }, []);

  async function loadMarkdown() {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(reportUrl(caseId, "markdown"), {
        headers: { Accept: "text/plain" },
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      setPreview(await res.text());
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
      setPreview("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Reports</h1>
        <p className="text-sm text-slate-400 mt-1">
          Professional investigation reports with explicit FACT / OBSERVATION / INFERENCE
          classification. AI prose is never labeled as FACT.
        </p>
      </header>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex-1 min-w-[220px]">
          <label className="text-xs text-slate-500">Case</label>
          <select
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
          >
            {cases.length === 0 && <option value="">No cases</option>}
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => void loadMarkdown()}
          className="rounded bg-accent px-4 py-2 text-sm text-white"
          disabled={!caseId || loading}
        >
          {loading ? "Loading…" : "Preview Markdown"}
        </button>
        {caseId && (
          <>
            <a
              className="rounded border border-surface-border px-3 py-2 text-sm text-sky-400 hover:underline"
              href={reportUrl(caseId, "json")}
              target="_blank"
              rel="noreferrer"
            >
              JSON
            </a>
            <a
              className="rounded border border-surface-border px-3 py-2 text-sm text-sky-400 hover:underline"
              href={reportUrl(caseId, "html")}
              target="_blank"
              rel="noreferrer"
            >
              HTML
            </a>
            <a
              className="rounded border border-surface-border px-3 py-2 text-sm text-sky-400 hover:underline"
              href={reportUrl(caseId, "pdf")}
              target="_blank"
              rel="noreferrer"
            >
              PDF
            </a>
          </>
        )}
      </div>
      {error && (
        <div className="rounded border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      {preview ? (
        <pre className="whitespace-pre-wrap rounded border border-surface-border bg-surface-raised p-4 text-xs text-slate-200 max-h-[28rem] overflow-auto">
          {preview}
        </pre>
      ) : (
        <p className="text-sm text-slate-500">
          Select a case and preview a report. Reports include scope, findings with epistemic
          labels, limitations, and reproducibility notes.
        </p>
      )}
    </div>
  );
}
