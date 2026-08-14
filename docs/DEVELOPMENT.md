# Development

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quality gates

```bash
ruff check src tests
mypy src
pytest --cov=spectra -q
```

CI runs these on Ubuntu (3.11/3.12), Windows (3.12), and macOS (3.12).

## Tests

- Unit tests must run **offline** (no LLM keys).
- Adversarial tests prove PolicyEngine cannot be bypassed.

## Adding a capability

1. Register in CapabilityRegistry
2. Implement ToolAdapter subclass
3. Call policy in execute path
4. Use `run_safe_command` or pure Python only
5. Add tests
