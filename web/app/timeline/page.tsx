"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, type Case, type TimelineEntry } from "@/lib/api";

export default function TimelinePage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [caseId, setCaseId] = useState("");
  const [items, setItems] = useState<TimelineEntry[]>([]);
  const [filter, setFilter] = useState("");
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
      setItems(await apiGet<TimelineEntry[]>(`/api/v1/timeline/by-case/${caseId}`));
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

  const filtered = items.filter((e) => {
    const q = filter.toLowerCase();
    if (!q) return true;
    return (
      e.kind.toLowerCase().includes(q) ||
      e.summary.toLowerCase().includes(q) ||
      e.source.toLowerCase().includes(q)
    );
  });

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Timeline</h1>
        <p className="text-sm text-slate-400 mt-1">Labeled investigation events from the backend.</p>
      </header>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex-1 min-w-[180px]">
          <label className="text-xs text-slate-500">Case</label>
          <select
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
          >
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
            {cases.length === 0 && <option value="">No cases</option>}
          </select>
        </div>
        <div className="flex-1 min-w-[140px]">
          <label className="text-xs text-slate-500">Filter</label>
          <input
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="kind or text"
          />
        </div>
        <button type="button" onClick={() => void load()} className="rounded bg-accent px-4 py-2 text-sm text-white">
          Refresh
        </button>
      </div>
      {error && (
        <div className="rounded border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
      )}
      <ul className="rounded border border-surface-border bg-surface-raised divide-y divide-surface-border/50">
        {loading && <li className="p-4 text-sm text-slate-500">Loading…</li>}
        {!loading && filtered.length === 0 && <li className="p-4 text-sm text-slate-500">No timeline entries.</li>}
        {filtered.map((e) => (
          <li key={e.id} className="px-4 py-3 flex gap-3 text-sm">
            <span className="font-mono text-xs text-accent w-28 shrink-0">{e.kind}</span>
            <span className="text-slate-500 text-xs w-24 shrink-0">{e.source}</span>
            <span className="flex-1">{e.summary}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
