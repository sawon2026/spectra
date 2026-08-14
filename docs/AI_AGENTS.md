# AI Agents & Intelligence Layer

## Boundary

AI (or deterministic planners) **propose**.
PolicyEngine + adapters **decide and execute**.

Never:

- Emit raw shell for unrestricted execution
- Treat model text as evidence without structured Observation
- Skip PolicyEngine because a model is "confident"

## Providers

Classifier and Planner are interfaces:

- `DeterministicClassifier` / `DeterministicPlanner` — offline, testable
- Future: OpenAI-compatible, Anthropic, local models behind the same interfaces

Core tests must pass with **no external LLM**.

## Capability requests

Plans use capability names and structured inputs — not raw shell commands.
