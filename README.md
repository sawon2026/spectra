<p align="center">
  <img src="docs/assets/spectra-logo.svg" alt="Spectra" width="140" height="140" />
</p>

<h1 align="center">Spectra</h1>

<p align="center">
  <strong>AI-Powered Security Research & Engineering Platform</strong>
</p>

<p align="center">
  Authorization-first · Offline-capable · Tool-agnostic · Evidence-backed
</p>

<p align="center">
  <a href="https://github.com/sawon2026/spectra"><img src="https://img.shields.io/badge/status-phase%201%20alpha-blue" alt="status" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="license" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="python" /></a>
  <a href="SECURITY.md"><img src="https://img.shields.io/badge/security-policy-orange" alt="security" /></a>
</p>

---

## What is Spectra?

Spectra is an open-source platform for **authorized** security research and engineering.
It sits above existing tools as an intelligent workspace that understands tasks, enforces scope, selects capabilities, collects evidence, and keeps investigations auditable.

It is **not** a script dump, not a client-bound skill pack, and not designed for unauthorized access.

```
User → Task understanding → Scope & policy gate → Capability selection
     → Controlled execution → Evidence & findings → Report / knowledge
```

## Design principles

| Principle | Meaning |
|-----------|---------|
| **Authorization first** | No impactful action without an explicit granted scope |
| **Deterministic core** | Policy, hashing, and permissions are not AI-overridable |
| **Controlled execution** | Allowlisted binaries, shell=False, argument validation |
| **Offline-first** | Works without cloud or AI providers |
| **Privacy by default** | Local storage, secret redaction in logs |
| **Extensible** | Capability registry ready for plugins (later phases) |

## Status — Phase 1 (Foundation)

- Case lifecycle
- Scope and authorization policy engine
- Capability registry
- Controlled tool adapters
- Evidence storage with fixity (SHA-256)
- Event / audit log
- Professional CLI
- Test suite

Later phases: adaptive planning, knowledge graph, web workspace, plugin SDK.

## Quick start

```bash
git clone https://github.com/sawon2026/spectra.git
cd spectra
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

spectra doctor
spectra version
```

### Minimal investigation flow

```bash
spectra case create --name lab-demo -d "Authorized lab sample"
spectra scope set --case <CASE_UUID> --auth granted --network offline --activity hash-compute
spectra capabilities list
spectra analyze --case <CASE_UUID> --tool hash-compute --path ./sample.bin
spectra evidence add --case <CASE_UUID> --title "Hash observation" --excerpt "..."
```

Without auth=granted and ready_for_act, analysis is **denied** by the policy engine.

## CLI

| Command | Purpose |
|---------|---------|
| spectra doctor | Environment and adapter health |
| spectra case create / list / show / status | Case lifecycle |
| spectra scope set / show | Authorization and network profile |
| spectra capabilities list | Registered capabilities |
| spectra analyze | Run a built-in tool under policy |
| spectra evidence list / add | Evidence for a case |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| SPECTRA_DATA_DIR | ~/.spectra | Local data root |
| SPECTRA_LOG_LEVEL | INFO | Logging level |
| SPECTRA_REQUIRE_SCOPE_FOR_EXECUTION | true | Hard policy gate |
| SPECTRA_ALLOW_NETWORK_BY_DEFAULT | false | Network default |

## Architecture (Phase 1)

```
spectra/
├── models/          # Pydantic domain models
├── core/            # Config, DB, logging
├── policy/          # Authorization engine (deterministic)
├── cases/           # Case and scope lifecycle
├── capabilities/    # Machine-readable capability registry
├── tools/           # Adapters and safe execution
├── evidence/        # Evidence and fixity
├── events/          # Audit / observability bus
└── cli/             # Typer CLI
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

See CONTRIBUTING.md.

## Security

See SECURITY.md.

Spectra is intended for **authorized** research, labs, CTFs, and systems you own or have written permission to test.
Do not use it for unauthorized access.

## License

Apache License 2.0 — see LICENSE.

## Roadmap

1. Phase 1 — Foundation (current)
2. Phase 2 — Task classifier, planner, observation to replan
3. Phase 3 — Findings correlation, knowledge graph, case memory
4. Phase 4 — High-value tool adapters
5. Phase 5 — Web workspace
6. Phase 6 — Plugin SDK
7. Phase 7 — Public release hardening

---

<p align="center"><em>Professional security research infrastructure — not a toy.</em></p>
