# Spectra API

Base path: `/api/v1`

## Security

- PolicyEngine is the sole capability execution gate.
- Web UI and API clients cannot execute arbitrary shell commands.
- Optional `SPECTRA_API_TOKEN` enables Bearer authentication.
- Roles: `admin`, `researcher`, `viewer` (via `X-Spectra-Role` in offline mode).
- Ledger and audit data never authorize capability execution.

## Phase 13 endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ledger/by-case/{id}` | Execution ledger (observability) |
| GET | `/ledger/by-workflow/{id}` | Workflow step ledger |
| GET | `/graph/neighbors/{node_id}` | Bounded neighborhood (`depth` 1–3) |
| GET | `/export/cases/{id}` | Case export bundle |
| GET | `/cases?status=&q=` | Filter/search cases |

## Run

```bash
uvicorn spectra.api.app:app --host 127.0.0.1 --port 8000
```
