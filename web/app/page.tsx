import { apiGet, type Health } from "@/lib/api";

export default async function DashboardPage() {
  let health: Health | null = null;
  let error: string | null = null;
  try {
    health = await apiGet<Health>("/api/v1/health");
  } catch (e) {
    error = e instanceof Error ? e.message : "API unreachable";
  }

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">
          Platform status and research entry points. The UI never executes shell commands.
        </p>
      </header>

      {error && (
        <div className="rounded border border-amber-700/50 bg-amber-950/40 px-4 py-3 text-sm text-amber-200">
          Backend offline: {error}. Start with{" "}
          <code className="font-mono text-xs">uvicorn spectra.api.app:app --port 8000</code>
        </div>
      )}

      {health && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ["Status", health.status],
            ["Version", health.version],
            ["Policy", health.policy_gate],
            ["Offline default", String(health.offline_default)],
          ].map(([k, v]) => (
            <div key={k} className="rounded border border-surface-border bg-surface-raised p-3">
              <div className="text-xs text-slate-500 uppercase tracking-wide">{k}</div>
              <div className="mt-1 font-mono text-sm">{v}</div>
            </div>
          ))}
        </div>
      )}

      <section className="rounded border border-surface-border bg-surface-raised p-4">
        <h2 className="text-sm font-medium text-slate-300">Security model</h2>
        <ul className="mt-2 text-sm text-slate-400 space-y-1 list-disc list-inside">
          <li>PolicyEngine is the sole capability execution gate</li>
          <li>AI, memory, findings, and UI cannot authorize execution</li>
          <li>Network remains offline unless scope allows it</li>
          <li>Timeline labels distinguish FACT from INFERENCE</li>
        </ul>
      </section>
    </div>
  );
}
