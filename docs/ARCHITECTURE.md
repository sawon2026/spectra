# Spectra Architecture

## Hard invariant

**PolicyEngine is the sole authorization gate for impactful actions.**

## Phase 13 — Production hardening & investigation depth

- Versioned migration steps (SCHEMA_VERSION=13); additive SQLite path; rollback via backup only
- Execution ledger (observability only; recovery_required never auto-replays)
- Structured audit (result, request_id, sanitized metadata)
- Graph bounded neighbors API (`depth` 1–3)
- Case list `status` + `q` search
- Plugin forbidden fields expanded (harvest_credentials, unrestricted_binary, …)

Invariants unchanged: PolicyEngine sole gate; ledger/audit never authorize execution.
