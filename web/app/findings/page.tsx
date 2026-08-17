"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet, type Case, type Finding } from "@/lib/api";

const SEV_CLASS: Record<string, string> = {
  critical: "bg-red-900/60 text-red-100 border-red-700",
  high: "bg-orange-900/50 text-orange-100 border-orange-700",
  medium: "bg-amber-900/40 text-amber-100 border-amber-700",
  low: "bg-sky-900/40 text-sky-100 border-sky-700",
  info: "bg-zinc-800 text-zinc-200 border-zinc-600",
};

function severityBadge(sev: string) {
  const key = (sev || "").toLowerCase();
  const cls = SEV_CLASS[key] || SEV_CLASS.info;
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-mono uppercase ${cls}`}>
      {sev || "—"}
    </span>
  );
}

export default function FindingsPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [caseId, setCaseId] = useState("");
  const [items, setItems] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sevFilter, setSevFilter] = useState("all");
  const [q, setQ] = useState("");

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
      setItems(await apiGet<Finding[]>(`/api/v1/findings/by-case/${caseId}`));
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

  const filtered = useMemo(() => {
    return items.filter((f) => {
      if (sevFilter !== "all" && (f.severity || "").toLowerCase() !== sevFilter) return false;
      if (q && !`${f.title} ${f.status}`.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
  }, [items, sevFilter, q]);

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Findings</h1>
        <p className="text-sm text-slate-400 mt-1">
          Engine-produced findings. Findings do not authorize capability execution.
          Description text is classified as INFERENCE unless independently corroborated.
        </p>
      </header>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex-1 min-w-[180px]">
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
        <div className="w-36">
          <label className="text-xs text-slate-500">Severity</label>
          <select
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            value={sevFilter}
            onChange={(e) => setSevFilter(e.target.value)}
          >
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="info">Info</option>
          </select>
        </div>
        <div className="flex-1 min-w-[140px]">
          <label className="text-xs text-slate-500">Search</label>
          <input
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter title…"
          />
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded bg-accent px-4 py-2 text-sm text-white"
        >
          Refresh
        </button>
      </div>
      {error && (
        <div className="rounded border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      <div className="rounded border border-surface-border bg-surface-raised overflow-hidden">
        {loading ? (
          <p className="p-4 text-sm text-slate-500">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No findings match this filter.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-surface-border text-left text-xs text-slate-500">
              <tr>
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Severity</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => (
                <tr key={f.id} className="border-b border-surface-border/50">
                  <td className="px-4 py-2">
                    <div>{f.title}</div>
                    {caseId && (
                      <Link
                        href={`/evidence?case=${caseId}`}
                        className="text-xs text-sky-400 hover:underline"
                      >
                        View evidence
                      </Link>
                    )}
                  </td>
                  <td className="px-4 py-2">{severityBadge(f.severity)}</td>
                  <td className="px-4 py-2 font-mono text-xs">{f.status}</td>
                  <td className="px-4 py-2 font-mono text-xs">{f.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
