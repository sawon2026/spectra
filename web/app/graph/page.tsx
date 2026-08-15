export default function GraphPage() {
  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold">Knowledge Graph</h1>
      <p className="text-sm text-slate-400">
        Visualizes nodes (Case, Artifact, Observation, Evidence, Finding, Capability) and edges
        (SUPPORTS, PRODUCED, ANALYZED_BY, …). Data from{" "}
        <code className="font-mono text-xs">/api/v1/graph/nodes|edges/{"{"}"{case_id}"{'}'}</code>. The
        graph never authorizes execution.
      </p>
    </div>
  );
}
