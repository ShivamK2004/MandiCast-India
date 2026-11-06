# Deployment notes

## Local development

Use two terminals as described in the root README: run the FastAPI backend on port 8000 and Vite on port 5173. Vite proxies `/api` to `http://127.0.0.1:8000`; confirm the connection at `http://localhost:5173/api/v1/health`.

If the backend uses another port, set `MANDICAST_API_TARGET` in the frontend terminal before starting Vite. For example, in PowerShell, for an API on port 8010:

```powershell
$env:MANDICAST_API_TARGET = "http://127.0.0.1:8010"
npm run dev
```

Restart Vite after changing the target; the proxy setting is read when the development server starts. Do not configure `VITE_API_BASE` for the local frontend: requests use the same-origin `/api/v1` path and the Vite proxy.

## Docker Compose

Compose starts PostgreSQL, FastAPI and the built React app served by Nginx. Nginx proxies `/api/` to the API service. The browser is served at `http://localhost:8080`; the API's OpenAPI docs are available at `http://localhost:8000/docs`, and its health endpoint is `http://localhost:8000/api/v1/health`. The Compose file publishes the API port for local inspection.

Change all sample credentials before any shared deployment. Use a managed secret store rather than committing `.env`.

## Production hardening checklist

- Authentication and authorisation; enforce ownership for dataset and job IDs.
- Rate limiting, request limits, upload scanning and secure file retention/deletion.
- Durable task queue and worker isolation; do not execute long model training inside an API web worker.
- Object storage for uploaded files and model artifacts.
- Database migrations (Alembic) and automated backup/restore.
- Structured logs, job tracing, model/dataset lineage and monitoring.
- HTTPS, restrictive CORS, secure cookies where applicable, CSP and reverse-proxy hardening.
- Model/data governance and clear warnings around forecast uncertainty and data provenance.
