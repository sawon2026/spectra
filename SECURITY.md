# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (alpha) |

## Reporting a vulnerability

Please report security issues privately. Do not open public issues for vulnerabilities that could enable unauthorized access, policy bypass, or data exposure.

Include:

- Description of the issue
- Steps to reproduce
- Affected component (policy, tools, CLI, storage, etc.)
- Suggested severity

## Design commitments (Phase 1)

- Policy engine is deterministic and is the sole gate for impactful actions
- Tool execution uses `shell=False` and an explicit binary allowlist
- Artifact paths are constrained to prevent path traversal
- Sensitive configuration keys are redacted from logs
- Default network posture is offline / deny

## Intended use

Spectra is for authorized security research, laboratory environments, CTFs, and systems you own or have written permission to test.
