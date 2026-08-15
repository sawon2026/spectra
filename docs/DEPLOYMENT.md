# Spectra Deployment

## Local development

```bash
pip install -e ".[dev]"
spectra doctor
uvicorn spectra.api.app:app --reload --port 8000
cd web && npm install && npm run dev
```

Offline mode is default. Set `SPECTRA_API_TOKEN` to require Bearer auth.

## Production backend

```bash
pip install -e .
export SPECTRA_API_TOKEN="$(openssl rand -hex 32)"
uvicorn spectra.api.app:app --host 0.0.0.0 --port 8000 --workers 2
```

Multi-worker SSE uses SQLite EventRow polling (`mode=hub+db`).

## Frontend

```bash
cd web
npm ci
npm run build
npm run start
```

Proxy `/backend` to the API (see `next.config.js`).

## Environment

| Variable | Purpose |
|----------|---------|
| `SPECTRA_API_TOKEN` | Require Bearer auth when set |
| `SPECTRA_API_URL` | Frontend rewrite target |

## Security notes

- PolicyEngine remains the sole capability execution gate
- Never log tokens
- Sessions store HMAC only
- HTTPS via reverse proxy recommended

## Backup

Copy the SQLite database file from the Spectra data directory.
