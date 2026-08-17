"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiGet, type Case, type GraphNode, type GraphEdge } from "@/lib/api";

export default function GraphPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [caseId, setCaseId] = useState("");
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [nodeType, setNodeType] = useState("all");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<GraphNode | null>(null);
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
      const nt = nodeType !== "all" ? `&node_type=${encodeURIComponent(nodeType)}` : "";
      const qs = q ? `&q=${encodeURIComponent(q)}` : "";
      const [n, e] = await Promise.all([
        apiGet<GraphNode[]>(`/api/v1/graph/nodes/${caseId}?limit=200${nt}${qs}`),
        apiGet<GraphEdge[]>(`/api/v1/graph/edges/${caseId}?limit=500`),
      ]);
      setNodes(n);
      setEdges(e);
      setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
  }, [caseId, nodeType, q]);

  useEffect(() => {
    void load();
  }, [load]);

  const related = useMemo(() => {
    if (!selected) return [] as GraphEdge[];
    return edges.filter((e) => e.from_node_id === selected.id || e.to_node_id === selected.id);
  }, [selected, edges]);

  const types = useMemo(() => {
    const s = new Set(nodes.map((n) => n.node_type).filter(Boolean));
    return Array.from(s).sort();
  }, [nodes]);

  return (
    <div className="max-w-5xl space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Knowledge Graph</h1>
        <p className="text-sm text-slate-400 mt-1">
          Investigation relationships — filter, search, select nodes. Server-side limits apply.
        </p>
      </header>
      <div className="flex flex-wrap gap-2 items-end">
        <div className="min-w-[180px] flex-1">
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
          </select>
        </div>
        <div className="w-36">
          <label className="text-xs text-slate-500">Node type</label>
          <select
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            value={nodeType}
            onChange={(e) => setNodeType(e.target.value)}
          >
            <option value="all">All</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
            <option value="finding">finding</option>
            <option value="evidence">evidence</option>
            <option value="artifact">artifact</option>
          </select>
        </div>
        <div className="flex-1 min-w-[140px]">
          <label className="text-xs text-slate-500">Search label</label>
          <input
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter…"
          />
        </div>
        <button type="button" onClick={() => void load()} className="rounded bg-accent px-4 py-2 text-sm text-white">
          Refresh
        </button>
      </div>
      {error && (
        <div className="rounded border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">{error}</div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded border border-surface-border bg-surface-raised p-3 max-h-[28rem] overflow-auto">
          <h2 className="text-xs text-slate-500 mb-2">Nodes ({nodes.length})</h2>
          {loading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : nodes.length === 0 ? (
            <p className="text-sm text-slate-500">No nodes for this filter.</p>
          ) : (
            <ul className="space-y-1">
              {nodes.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(n)}
                    className={`w-full text-left rounded px-2 py-1.5 text-sm ${
                      selected?.id === n.id ? "bg-sky-900/40 text-sky-100" : "hover:bg-surface text-slate-200"
                    }`}
                  >
                    <span className="font-mono text-[10px] text-slate-500 mr-2">{n.node_type}</span>
                    {n.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded border border-surface-border bg-surface-raised p-3 max-h-[28rem] overflow-auto">
          <h2 className="text-xs text-slate-500 mb-2">Selection & relationships</h2>
          {!selected ? (
            <p className="text-sm text-slate-500">Select a node to inspect edges.</p>
          ) : (
            <div className="space-y-3 text-sm">
              <div>
                <div className="font-medium text-slate-100">{selected.label}</div>
                <div className="font-mono text-[11px] text-slate-500">
                  {selected.node_type} · {selected.id}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">Edges ({related.length})</div>
                {related.length === 0 ? (
                  <p className="text-slate-500">No edges.</p>
                ) : (
                  <ul className="space-y-1">
                    {related.map((e) => (
                      <li key={e.id} className="font-mono text-[11px] text-slate-400">
                        {e.from_node_id.slice(0, 8)}… —[{e.relation}]→ {e.to_node_id.slice(0, 8)}…
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
          <div className="mt-4 text-xs text-slate-500">Total edges in case view: {edges.length}</div>
        </div>
      </div>
    </div>
  );
}
