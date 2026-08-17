# Spectra Deployment

## Local development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
mypy src/spectra
python -m spectra.cli.main doctor

uvicorn spectra.api.app:app --reload --host 127.0.0.1 --port 8000
cd web && npm install && npm run dev
```

Offline mode is default. Set `SPECTRA_API_TOKEN` to require Bearer auth.

## Production backend

```bash
pip install -e .
export SPECTRA_API_TOKEN="$(openssl rand -hex 32)"
uvicorn spectra.api.app:app --host 127.0.0.1 --port 8000 --workers 2
```

- Prefer binding to localhost and terminating TLS at a reverse proxy.
- Multi-worker SSE uses SQLite EventRow polling (`mode=hub+db`).
- Do not run as root in production.

## Frontend

```bash
cd web
npm ci
npm run typecheck
npm run build
npm run start
```

Proxy `/backend` to the API (see `next.config.js`).

## Environment

| Variable | Purpose |
|----------|---------|
| `SPECTRA_API_TOKEN` | Require Bearer auth when set |
| `SPECTRA_API_URL` | Frontend rewrite target |
| `SPECTRA_DATA_DIR` | Optional data directory for SQLite |

## Health

- `GET /api/v1/health` — process health (no secrets)
- `spectra doctor` — capability and tool availability

## Backup / export

1. **Case export (API):** `GET /api/v1/export/cases/{id}` — JSON metadata bundle (`spectra.case.export.v1`), no secrets.
2. **Database file:** copy the SQLite file from the Spectra data directory while the process is stopped or using a filesystem-consistent snapshot.
3. Restore: replace the DB file only from a trusted backup; re-run `spectra doctor`.

## Security notes

- PolicyEngine remains the sole capability execution gate
- Authentication ≠ capability execution authorization
- Never log tokens or passwords
- Sessions store HMAC digests only
- HTTPS via reverse proxy recommended
- Network remains OFFLINE by default

## Production readiness (honest)

**Ready for:** offline lab use, controlled research environments, single-host deployment behind TLS proxy.

**Not claimed:** multi-tenant SaaS isolation, HA clustering, managed plugin marketplace, autonomous offensive operations.
