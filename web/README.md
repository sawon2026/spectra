# Spectra Web Workspace

TypeScript / Next.js / Tailwind frontend for the Spectra security research platform.

## Principles

- Python backend remains the sole execution path (PolicyEngine).
- The browser never runs shell commands or local tools.
- All investigation actions call `/api/v1/...`.

## Develop

```bash
# Terminal 1 — API
uvicorn spectra.api.app:app --reload --port 8000

# Terminal 2 — Web
cd web && npm install && npm run dev
```

Open http://localhost:3000

## Scripts

- `npm run dev` — development server
- `npm run build` — production build
- `npm run typecheck` — TypeScript check
- `npm run lint` — Next.js lint
