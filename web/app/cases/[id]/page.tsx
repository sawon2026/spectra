"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, type Case, type TimelineEntry } from "@/lib/api";

type Scope = {
  auth_status: string;
  network_profile: string;
  ready_for_act: boolean;
  allowed_activities: string[];
};

export default function CaseDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const [caseData, setCase] = useState<Case | null>(null);
  const [scope, setScope] = useState<Scope | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        setCase(await apiGet<Case>(`/api/v1/cases/${id}`));
        try {
          setScope(await apiGet<Scope>(`/api/v1/cases/${id}/scope`));
        } catch {
          setScope(null);
        }
        setTimeline(await apiGet<TimelineEntry[]>(`/api/v1/timeline/by-case/${id}`));
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed");
      }
    })();
  }, [id]);

  if (error) {
    return (
      <div className="p-6">
        <p className="text-red-400">{error}</p>
        <Link href="/cases" className="text-sm text-zinc-400 underline">
          Back to cases
        </Link>
      </div>
    );
  }

  if (!caseData) {
    return <div className="p-6 text-zinc-400">Loading case…</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Link href="/cases" className="text-xs text-zinc-500 hover:text-zinc-300">
            ← Cases
          </Link>
          <h1 className="text-xl font-semibold text-zinc-100 mt-1">{caseData.name}</h1>
          <p className="text-sm text-zinc-400 mt-1">{caseData.description || "No description"}</p>
        </div>
        <span className="rounded border border-zinc-700 px-2 py-1 text-xs uppercase tracking-wide text-zinc-300">
          {caseData.status}
        </span>
      </div>

      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <h2 className="text-sm font-medium text-zinc-200 mb-3">Scope</h2>
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

      <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <h2 className="text-sm font-medium text-zinc-200 mb-3">Recent timeline</h2>
        {timeline.length === 0 ? (
          <p className="text-sm text-zinc-500">No timeline entries.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {timeline.slice(0, 20).map((t) => (
              <li key={t.id} className="border-b border-zinc-800/80 pb-2">
                <span className="text-zinc-400 text-xs">{t.kind || "event"}</span>
                <div className="text-zinc-200">{t.summary || "—"}</div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link href={`/evidence?case=${id}`} className="text-sky-400 hover:underline">
          Evidence
        </Link>
        <Link href={`/findings?case=${id}`} className="text-sky-400 hover:underline">
          Findings
        </Link>
        <Link href={`/timeline?case=${id}`} className="text-sky-400 hover:underline">
          Timeline
        </Link>
        <Link href={`/reports?case=${id}`} className="text-sky-400 hover:underline">
          Reports
        </Link>
        <Link href={`/graph?case=${id}`} className="text-sky-400 hover:underline">
          Graph
        </Link>
      </div>
    </div>
  );
}
