# Plugin / Adapter Guide

## Writing an adapter

1. Subclass `ToolAdapter`
2. Define `capability` metadata (name, risk, inputs, auth)
3. Implement `is_available()` and `execute()`
4. Always call `_check_policy` before side effects
5. Use `run_safe_command` or pure Python only
6. Register capability in `CapabilityRegistry`
7. Emit structured events; record evidence via EvidenceService

## Never

- `shell=True`
- Arbitrary user strings in command construction without validation
- Bypass PolicyEngine
- Treat model text as evidence
