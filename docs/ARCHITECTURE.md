# Spectra Architecture

## Layers

```
Interfaces: CLI (Phase 1) · API/UI (later)
Intelligence (Phase 2)
  Classifier → State → Planner → Observation → Replan
  * Requests capability executions only
  * Never runs unrestricted shell
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
