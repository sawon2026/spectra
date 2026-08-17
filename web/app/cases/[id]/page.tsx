"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  apiGet,
  type Case,
  type TimelineEntry,
  type Finding,
  type Evidence,
  type GraphNode,
  type GraphEdge,
} from "@/lib/api";

type Scope = {
  auth_status: string;
  network_profile: string;
  ready_for_act: boolean;
  allowed_activities: string[];
  auth_basis?: string;
};

type Tab = "overview" | "scope" | "evidence" | "findings" | "timeline" | "graph" | "export";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "scope", label: "Scope" },
  { id: "evidence", label: "Evidence" },
  { id: "findings", label: "Findings" },
  { id: "timeline", label: "Timeline" },
  { id: "graph", label: "Graph" },
  { id: "export", label: "Export" },
];

export default function CaseDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [tab, setTab] = useState<Tab>("overview");
  const [caseData, setCase] = useState<Case | null>(null);
  const [scope, setScope] = useState<Scope | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [exportJson, setExportJson] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    (async () => {
      setLoading(true);
      try {
        setCase(await apiGet<Case>(`/api/v1/cases/${id}`));
        try {
          setScope(await apiGet<Scope>(`/api/v1/cases/${id}/scope`));
        } catch {
          setScope(null);
        }
        try {
          setTimeline(await apiGet<TimelineEntry[]>(`/api/v1/timeline/by-case/${id}`));
        } catch {
          setTimeline([]);
        }
        try {
          setFindings(await apiGet<Finding[]>(`/api/v1/findings/by-case/${id}`));
        } catch {
          setFindings([]);
        }
        try {
          setEvidence(await apiGet<Evidence[]>(`/api/v1/cases/${id}/evidence`));
        } catch {
          setEvidence([]);
        }
        try {
          setNodes(await apiGet<GraphNode[]>(`/api/v1/graph/nodes/${id}?limit=100`));
          setEdges(await apiGet<GraphEdge[]>(`/api/v1/graph/edges/${id}?limit=200`));
        } catch {
          setNodes([]);
          setEdges([]);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  async function loadExport() {
    try {
      const data = await apiGet<unknown>(`/api/v1/export/cases/${id}`);
      setExportJson(JSON.stringify(data, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : "export failed");
    }
  }

  if (error && !caseData) {
    return (
      <div className="p-6">
        <p className="text-red-400">{error}</p>
        <Link href="/cases" className="text-sm text-zinc-400 underline">
          Back to cases
        </Link>
      </div>
    );
  }

  if (loading || !caseData) {
    return <div className="p-6 text-zinc-400">Loading case workspace…</div>;
  }

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/cases" className="text-xs text-zinc-500 hover:text-zinc-300">
            ← Cases
          </Link>
          <h1 className="text-xl font-semibold text-zinc-100 mt-1">{caseData.name}</h1>
          <p className="text-sm text-zinc-400 mt-1">{caseData.description || "No description"}</p>
          <p className="text-[11px] font-mono text-zinc-600 mt-1">{caseData.id}</p>
        </div>
        <span className="rounded border border-zinc-700 px-2 py-1 text-xs uppercase tracking-wide text-zinc-300">
          {caseData.status}
        </span>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-zinc-800 pb-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setTab(t.id);
              if (t.id === "export") void loadExport();
            }}
            className={`rounded px-3 py-1.5 text-xs ${
              tab === t.id ? "bg-sky-900/50 text-sky-100" : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <section className="grid gap-3 sm:grid-cols-3">
          <div className="rounded border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="text-xs text-zinc-500">Evidence</div>
            <div className="text-2xl font-semibold text-zinc-100">{evidence.length}</div>
          </div>
          <div className="rounded border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="text-xs text-zinc-500">Findings</div>
            <div className="text-2xl font-semibold text-zinc-100">{findings.length}</div>
          </div>
          <div className="rounded border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="text-xs text-zinc-500">Timeline</div>
            <div className="text-2xl font-semibold text-zinc-100">{timeline.length}</div>
          </div>
          <div className="sm:col-span-3 rounded border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-400">
            Investigation hub — all data from API. PolicyEngine remains the sole execution gate.
            UI never executes tools.
          </div>
        </section>
      )}

      {tab === "scope" && (
        <section className="rounded border border-zinc-800 bg-zinc-900/40 p-4">
          {scope ? (
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-zinc-500">Auth</dt>
              <dd className="text-zinc-200">{scope.auth_status}</dd>
              <dt className="text-zinc-500">Network</dt>
              <dd className="text-zinc-200">{scope.network_profile}</dd>
              <dt className="text-zinc-500">Ready for act</dt>
              <dd className="text-zinc-200">{scope.ready_for_act ? "yes" : "no"}</dd>
              <dt className="text-zinc-500">Allowed</dt>
              <dd className="text-zinc-200">{(scope.allowed_activities || []).join(", ") || "—"}</dd>
            </dl>
          ) : (
            <p className="text-sm text-zinc-500">No scope configured.</p>
          )}
        </section>
      )}

      {tab === "evidence" && (
        <section className="rounded border border-zinc-800 bg-zinc-900/40 p-4 space-y-2">
          {evidence.length === 0 ? (
            <p className="text-sm text-zinc-500">No evidence.</p>
          ) : (
            evidence.map((e) => (
              <div key={e.id} className="border-b border-zinc-800/80 pb-2 text-sm">
                <div className="text-zinc-100">{e.title}</div>
                <div className="text-xs text-zinc-500 font-mono">
                  {e.source_type} · hash={e.content_hash || "—"} · conf={e.confidence ?? "—"}
                </div>
              </div>
            ))
          )}
        </section>
      )}

      {tab === "findings" && (
        <section className="rounded border border-zinc-800 bg-zinc-900/40 p-4 space-y-2">
          {findings.length === 0 ? (
            <p className="text-sm text-zinc-500">No findings.</p>
          ) : (
            findings.map((f) => (
              <div key={f.id} className="border-b border-zinc-800/80 pb-2 text-sm">
                <div className="text-zinc-100">{f.title}</div>
                <div className="text-xs text-zinc-500">
                  severity={f.severity} · status={f.status} · conf={f.confidence} · class=FINDING
                </div>
              </div>
            ))
          )}
        </section>
      )}

      {tab === "timeline" && (
        <section className="rounded border border-zinc-800 bg-zinc-900/40 p-4 space-y-2">
          {timeline.length === 0 ? (
            <p className="text-sm text-zinc-500">No timeline entries.</p>
          ) : (
            timeline.slice(0, 40).map((t) => (
              <div key={t.id} className="border-b border-zinc-800/80 pb-2 text-sm">
                <span className="text-zinc-500 text-xs font-mono">{t.kind}</span>
                <div className="text-zinc-200">{t.summary}</div>
              </div>
            ))
          )}
        </section>
      )}

      {tab === "graph" && (
        <section className="rounded border border-zinc-800 bg-zinc-900/40 p-4 text-sm space-y-2">
          <p className="text-zinc-500">
            {nodes.length} nodes · {edges.length} edges — open full graph for filters.
          </p>
          <Link href={`/graph?case=${id}`} className="text-sky-400 hover:underline text-sm">
            Open interactive graph →
          </Link>
          <ul className="space-y-1 max-h-48 overflow-auto">
            {nodes.slice(0, 20).map((n) => (
              <li key={n.id} className="font-mono text-xs text-zinc-400">
                [{n.node_type}] {n.label}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "export" && (
        <section className="rounded border border-zinc-800 bg-zinc-900/40 p-4 space-y-2">
          <p className="text-xs text-zinc-500">
            Offline case export — metadata only, no secrets. Format spectra.case.export.v1
          </p>
          <button
            type="button"
            onClick={() => void loadExport()}
            className="rounded bg-sky-800 px-3 py-1.5 text-xs text-white"
          >
            Refresh export
          </button>
          {exportJson ? (
            <pre className="text-[10px] text-zinc-300 max-h-80 overflow-auto whitespace-pre-wrap">
              {exportJson}
            </pre>
          ) : (
            <p className="text-sm text-zinc-500">Click refresh to load export bundle.</p>
          )}
        </section>
      )}
    </div>
  );
}
