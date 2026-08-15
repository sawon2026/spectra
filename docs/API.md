# Spectra API

Base path: `/api/v1`

## Security

- PolicyEngine is the sole capability execution gate.
- Web UI and API clients cannot execute arbitrary shell commands.
- Optional `SPECTRA_API_TOKEN` enables Bearer authentication.
- Roles: `admin`, `researcher`, `viewer` (via `X-Spectra-Role` in offline mode).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | System health (no secrets) |
| GET | `/me` | Current principal |
| POST | `/cases` | Create case |
| GET | `/cases/{id}` | Get case |
| PUT | `/cases/{id}/scope` | Set scope |
| POST | `/cases/{id}/evidence` | Record evidence |
| POST | `/workflows/case/{id}/start` | Start investigation |
| POST | `/workflows/{id}/pause|resume|cancel|recover` | Control workflow |
| GET | `/timeline/by-case/{id}` | Timeline |
| GET | `/graph/nodes|edges/{id}` | Knowledge graph |
| GET | `/capabilities` | Registered capabilities |
| GET | `/providers` | AI providers |
| GET | `/reports/{id}/markdown` | Report export |
| GET | `/events/stream` | SSE event stream |

## Run

```bash
uvicorn spectra.api.app:app --host 127.0.0.1 --port 8000
```
