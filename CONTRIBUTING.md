# Contributing to Spectra

Thank you for your interest in contributing.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check src tests
```

## Guidelines

1. **Authorization first** — any path that executes tools must go through the policy engine.
2. **No arbitrary shell** — use `run_safe_command` or pure Python; extend the allowlist deliberately.
3. **Tests required** — add unit tests for policy, adapters, and models you change.
4. **Typing** — keep full type hints; run `mypy src` when practical.
5. **Commits** — clear messages; prefer small, focused PRs.

## Architecture notes

Phase 1 is the foundation (cases, scope, policy, capabilities, evidence, CLI).
Phase 2+ will add planning, knowledge graph, UI, and plugins.
Do not bypass deterministic controls with AI-only logic.

## Code of conduct

Be respectful. This project is for authorized security research and engineering.
