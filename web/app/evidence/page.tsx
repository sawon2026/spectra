"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, type Case, type Evidence } from "@/lib/api";

export default function EvidencePage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [caseId, setCaseId] = useState("");
  const [items, setItems] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const list = await apiGet<Case[]>("/api/v1/cases");
        setCases(list);
        if (list.length && !caseId) setCaseId(list[0].id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed");
      }
    })();
  }, [caseId]);

  const load = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      setItems(await apiGet<Evidence[]>(`/api/v1/cases/${caseId}/evidence`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Evidence</h1>
        <p className="text-sm text-slate-400 mt-1">Case evidence from the API. No secrets displayed.</p>
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
        <button type="button" onClick={() => void load()} className="rounded bg-accent px-4 py-2 text-sm text-white">
          Refresh
        </button>
      </div>
      {error && (
        <div className="rounded border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
      )}
      <div className="rounded border border-surface-border bg-surface-raised overflow-hidden">
        {loading ? (
          <p className="p-4 text-sm text-slate-500">Loading…</p>
        ) : items.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No evidence for this case.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-surface-border text-left text-xs text-slate-500">
              <tr>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Source</th>
                <th className="px-4 py-2">Hash</th>
                <th className="px-4 py-2">Conf</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="border-b border-surface-border/50">
                  <td className="px-4 py-2">{e.title}</td>
                  <td className="px-4 py-2 font-mono text-xs">{e.source_type}</td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-500">
                    {(e.content_hash || "—").slice(0, 16)}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">{e.confidence ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {caseId ? (
        <Link href={`/cases/${caseId}`} className="text-sm text-accent">
          Open case
        </Link>
      ) : null}
    </div>
  );
}
