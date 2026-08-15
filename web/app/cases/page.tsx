export default function CasesPage() {
  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold">Cases</h1>
      <p className="text-sm text-slate-400">
        Create and manage research cases via the API. Scope must be authorized before capability
        execution. Use <code className="font-mono text-xs">POST /api/v1/cases</code>.
      </p>
    </div>
  );
}
