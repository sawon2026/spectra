"use client";

import { useState } from "react";
import { apiGet, apiPost, type TimelineEntry, type Workflow } from "@/lib/api";

/**
 * Investigation workspace — operators control pause/resume/cancel/recover.
 * Execution always goes through the backend policy boundary.
 */
export default function InvestigationsPage() {
  const [caseId, setCaseId] = useState("");
  const [goal, setGoal] = useState("Inspect artifact and compute hashes");
  const [path, setPath] = useState("");
  const [wf, setWf] = useState<Workflow | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const w = await apiPost<Workflow>(`/api/v1/workflows/case/${caseId}/start`, {
        goal,
        artifact_path: path,
        max_steps: 5,
      });
      setWf(w);
      const tl = await apiGet<TimelineEntry[]>(`/api/v1/timeline/by-case/${caseId}`);
      setTimeline(tl);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  async function action(kind: "pause" | "resume" | "cancel" | "recover") {
    if (!wf) return;
    setBusy(true);
    setError(null);
    try {
      const w = await apiPost<Workflow>(`/api/v1/workflows/${wf.id}/${kind}`, {});
      setWf(w);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Investigation Workspace</h1>
        <p className="text-sm text-slate-400 mt-1">
          Goal, plan outcomes, timeline, and operator controls. No direct command execution from the browser.
        </p>
      </header>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3 rounded border border-surface-border bg-surface-raised p-4">
          <label className="block text-xs text-slate-500">Case ID</label>
          <input
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm font-mono"
            value={caseId}
            onChange={(e) => setCaseId(e.target.value)}
            placeholder="uuid"
          />
          <label className="block text-xs text-slate-500">Research goal</label>
          <textarea
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm"
            rows={3}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
          <label className="block text-xs text-slate-500">Artifact path (server-side)</label>
          <input
            className="w-full rounded border border-surface-border bg-surface px-3 py-2 text-sm font-mono"
            value={path}
            onChange={(e) => setPath(e.target.value)}
          />
          <button
            type="button"
            disabled={busy || !caseId}
            onClick={start}
            className="rounded bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            Start investigation
          </button>
        </div>

        <div className="rounded border border-surface-border bg-surface-raised p-4 space-y-3">
          <h2 className="text-sm font-medium text-slate-300">Workflow status</h2>
          {wf ? (
            <>
              <dl className="text-sm space-y-1 font-mono">
                <div>
                  <span className="text-slate-500">id </span>
                  {wf.id}
                </div>
                <div>
                  <span className="text-slate-500">status </span>
                  {wf.status}
                </div>
                <div>
                  <span className="text-slate-500">decisions </span>
                  {wf.decision_count}
                </div>
                {wf.recovery_notes && (
                  <div className="text-amber-300/90">{wf.recovery_notes}</div>
                )}
              </dl>
              <div className="flex flex-wrap gap-2 pt-2">
                {(["pause", "resume", "cancel", "recover"] as const).map((k) => (
                  <button
                    key={k}
                    type="button"
                    disabled={busy}
                    onClick={() => action(k)}
                    className="rounded border border-surface-border px-3 py-1.5 text-xs capitalize hover:bg-surface"
                  >
                    {k}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">No active workflow loaded.</p>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      <section className="rounded border border-surface-border bg-surface-raised p-4">
        <h2 className="text-sm font-medium text-slate-300 mb-3">Timeline</h2>
        <ul className="space-y-2 text-sm">
          {timeline.length === 0 && <li className="text-slate-500">No entries yet.</li>}
          {timeline.map((e) => (
            <li key={e.id} className="flex gap-3 border-b border-surface-border/50 pb-2">
              <span className="shrink-0 font-mono text-xs text-accent w-28">{e.kind}</span>
              <span className="text-slate-300">{e.summary}</span>
              <span className="ml-auto text-xs text-slate-500">{e.source}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
