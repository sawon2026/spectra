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

The intelligence layer may *request* a capability. Execution only proceeds if:

1. Scope exists and `auth_status=granted`
2. `ready_for_act` is true
3. Activity is allowed / not forbidden
4. Asset is in scope (when listed)
5. Network profile permits network (when required)

## Phase 2 flow

```
Task text
  → DeterministicClassifier
  → Task { type, artifacts, capabilities, risk }
  → InvestigationState
  → DeterministicPlanner → Plan[PlanStep(capability, inputs, objective)]
  → For each step:
        PolicyEngine.evaluate
          ├─ DENY → Observation(BLOCKED)
          └─ ALLOW → Adapter.execute → Observation(...)
        → optional replan
  → COMPLETED | BLOCKED | FAILED
```

## Non-goals (this phase)

- Multi-agent orchestration
- Web UI
- Plugin marketplace
- Dozens of tool integrations

## Phase 10 — Product surface & platform maturity

Phase 10 completes the professional investigation UI surface against the existing APIs and hardens release engineering.

**Implemented**
- Web UI pages consume real `/api/v1` data (cases, evidence, findings, timeline, reports, capabilities, providers, settings, dashboard, case detail, graph).
- Typed API client (`web/lib/api.ts`); no browser-side tool execution.
- Cases list pagination: `limit` (1–500, default 50) and `offset` (≥0).
- Lightweight schema versioning (`SchemaVersionRow`, `SCHEMA_VERSION=10`) via idempotent `ensure_schema` on startup — SQLite-compatible, non-destructive.
- CI frontend job: `npm ci` (or install fallback), `typecheck`, `build`.
- Investigation depth APIs already present (graph, timeline, findings, workflows, provenance paths).

**Invariants preserved**
- PolicyEngine remains the sole execution gate.
- Authentication ≠ authorization for capability execution.
- UI → API → services → PolicyEngine → controlled adapters only.

**Not claimed**
- Full Alembic migration history (baseline stamp only; Alembic optional later).
- Multi-tenant authz beyond current principal model.
- Production-scale search/indexing.

## Phase 11 — Professional platform maturity

- Request ID middleware (`X-Request-ID`)
- Provenance API: `GET /api/v1/provenance/by-case/{id}`
- ReportExporter epistemic classification (FACT/OBSERVATION/INFERENCE/…)
- Findings UI severity filters; reports preview
- SCHEMA_VERSION=11
- PLUGIN_GUIDE safer contracts

Invariants preserved: PolicyEngine sole gate; UI never executes tools; AI ≠ FACT.
