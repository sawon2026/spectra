# Threat Model (Phase 1–2)

## Assets

- Case data, evidence, investigation state
- Host where Spectra runs
- Scope / authorization integrity

## Threats

| Threat | Mitigation |
|--------|------------|
| Planner emits shell | Plans only reference capability names; adapters use allowlist + shell=False |
| Policy bypass via AI | Orchestrator always calls PolicyEngine before adapter |
| Malicious artifact path | Scope asset checks; evidence path traversal validators |
| Compromised model output | Treated as untrusted input to structured Task/Plan schemas |
| Secret leakage in logs | structlog redaction filter |
| Unauthorized network | NetworkProfile + policy network_required check |

## Trust boundaries

1. User / AI text → Classifier (untrusted)
2. Plan steps → PolicyEngine (enforcement)
3. Adapter → OS (allowlisted binaries only)
