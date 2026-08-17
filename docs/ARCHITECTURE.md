# Spectra Architecture

## Layers

```
Interfaces: CLI (Phase 1) · API/UI (later)
Intelligence (Phase 2)
  Classifier → State → Planner → Orchestrator
Application Services
  Cases · Evidence · Findings · Timeline · Workflows
  Auth · Audit · Events · Reporting
Policy + Capabilities
  PolicyEngine (sole execution gate)
  CapabilityRegistry · Tool Adapters
  Controlled Execution (shell=False, allowlist, metachar block)
Core (Phase 1)
  PolicyEngine · Cases · Scope · Evidence · Events
  CapabilityRegistry · Tool Adapters · Controlled Exec
```

## Hard invariant

**PolicyEngine is the sole authorization gate for impactful actions.**

## Phase 11 — Professional platform maturity

- Request ID middleware (`X-Request-ID`)
- Provenance API: `GET /api/v1/provenance/by-case/{id}`
- ReportExporter epistemic classification
- Findings UI severity filters; reports preview
- SCHEMA_VERSION=11

## Phase 12 — Production hardening & investigation workspace

- Case detail investigation hub (overview/scope/evidence/findings/timeline/graph/export)
- Interactive graph UI (filter, search, node selection, edge inspection)
- Graph API: `node_type`, `q`, `limit` filters
- Case export API: `GET /api/v1/export/cases/{id}` (`spectra.case.export.v1`)
- Plugin SDK v2: health, lifecycle, forbidden fields, `list_with_status`
- SCHEMA_VERSION=12
- DEPLOYMENT.md production guidance and backup path

Invariants unchanged: PolicyEngine sole gate; offline default; AI ≠ FACT.
