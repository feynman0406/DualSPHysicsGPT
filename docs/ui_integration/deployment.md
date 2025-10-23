# Phase 5 Deployment Guide

## Overview
- **Purpose**: Harden delivery for the UI stack so it can run alongside the immutable MVP CLI without touching frozen assets.
- **Components**:
  - `ui_backend/`: FastAPI router exposing run history and MVP orchestration endpoints.
  - `ui/app/`: Vite + React SPA that consumes the backend.
  - `scripts/ci/run_all.py`: Unified quality gate wrapping MVP smoke, backend tests/lint, and frontend lint/build/test.

## Environment Matrix
| Layer | Requirement |
| --- | --- |
| Python | 3.11 (minimum 3.10). Install deps with `pip install -r requirements.txt` plus `pip install pytest ruff uvicorn`.
| Node.js | 20.x LTS with `npm` available on PATH. Use `npm ci` inside `ui/app`.
| OS | Windows and Linux verified; Linux hosts are recommended for staging/production.
| GPU | Optional. Metrics collectors degrade gracefully when NVIDIA tooling is absent.

## Local Development
1. **Bootstrap toolchains**
   ```powershell
   # Python
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   pip install pytest ruff uvicorn

   # Frontend
   pushd ui/app
   npm ci
   popd
   ```
2. **Configure environment**
   - Copy `.env` and provide OpenAI credentials.
   - Mandatory vars: `OPENAI_API_KEY`, `OPENAI_RAG_VS_DESIGN_ID`, `DSPH_WORKDIR`, `OPENAI_MODEL` (optional override).
   - The MVP runner writes to `logs/mvp/`; ensure this remains writable.
3. **Run the backend**
   ```powershell
   uvicorn "ui_backend.api:create_router" --factory --host 0.0.0.0 --port 8000
   ```
   - `create_router` accepts an optional `HistoryStore` instance; by default the file-backed store lives under `ui_backend/data/history.json`.
4. **Run the SPA**
   ```powershell
   pushd ui/app
   npm run dev -- --host
   ```
   - Vite proxy is pre-configured to forward `/api` to `http://localhost:8000`.
5. **Quality gate before pushing**
   ```powershell
   python scripts/ci/run_all.py --skip-mvp --npm-ci
   ```
   - Add `--skip-mvp` only when environment variables are missing; the CI workflow will fail if the MVP smoke path is skipped in protected branches.

## Staging / Production Deployment
1. **Pre-flight checks**: run `python scripts/ci/run_all.py --npm-ci` locally with valid OpenAI credentials to exercise MVP, backend, and frontend suites.
2. **Build assets**
   ```powershell
   pushd ui/app
   npm ci
   npm run build
   popd
   ```
   - Static files land in `ui/app/dist`.
3. **Deploy backend service**
   - Install service dependencies inside a dedicated virtualenv.
   - Run under `uvicorn` or `gunicorn` with workers sized to concurrent MVP invocations (each run is CPU heavy while invoking the CLI pipeline).
   - Recommended systemd unit:
     ```ini
     [Unit]
     Description=DualSPHysics UI backend
     After=network.target

     [Service]
     WorkingDirectory=/opt/DualSPHysicsGPT
     EnvironmentFile=/opt/DualSPHysicsGPT/.env
     ExecStart=/opt/DualSPHysicsGPT/.venv/bin/uvicorn "ui_backend.api:create_router" --factory --host 127.0.0.1 --port 8000
     Restart=on-failure
     LimitNOFILE=8192

     [Install]
     WantedBy=multi-user.target
     ```
4. **Serve frontend**
   - Option A: `npm run preview -- --host 0.0.0.0 --port 4173` behind a reverse proxy.
   - Option B: Copy `ui/app/dist` into an nginx `root` and serve as static content.
5. **Reverse proxy layout**
   ```nginx
   server {
       listen 443 ssl;
       server_name dsp-ui.example.com;

       ssl_certificate /etc/letsencrypt/live/dsp-ui/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/dsp-ui/privkey.pem;

       location /api/ {
           proxy_pass http://127.0.0.1:8000/runs/;
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location / {
           root /srv/dualsphysics-ui;
           try_files $uri $uri/ /index.html;
       }
   }
   ```
   - The router is mounted at `/runs`; rewrite `/api` accordingly or adjust the FastAPI prefix.
6. **Security & observability**
   - Inject OpenAI credentials via environment, never via git-tracked files.
   - Enable TLS on the proxy and restrict backend exposure to localhost.
   - History store (`ui_backend/data/history.json`) contains run metadata; back this up or redirect `HistoryStore` to persistent storage.

## Docker Reference (Optional)
- **Backend** (`Dockerfile.backend` example):
  ```dockerfile
  FROM python:3.11-slim AS backend
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt && pip install uvicorn pytest ruff
  COPY ui_backend/ ui_backend/
  COPY tests/ui_backend/ tests/ui_backend/
  COPY scripts/ci/run_all.py scripts/ci/run_all.py
  CMD ["uvicorn", "ui_backend.api:create_router", "--factory", "--host", "0.0.0.0", "--port", "8000"]
  ```
- **Frontend** (`Dockerfile.frontend` example):
  ```dockerfile
  FROM node:20-alpine AS build
  WORKDIR /usr/src/app
  COPY ui/app/package*.json ./
  RUN npm ci
  COPY ui/app/ ./
  RUN npm run build

  FROM nginx:1.27-alpine
  COPY --from=build /usr/src/app/dist/ /usr/share/nginx/html/
  COPY docs/ui_integration/assets/nginx.conf /etc/nginx/conf.d/default.conf
  ```
- Compose services can share an `.env` file and a named volume for `logs/mvp/` so agents retain artifacts between container restarts.

## Promotion Checklist\n- Dry-run log captured at `docs/ui_integration/assets/phase5_ci_run.txt` (generated via `python scripts/ci/run_all.py --skip-mvp`).
1. Secrets present and encrypted (GitHub Actions secrets + deployment environment).
2. `python scripts/ci/run_all.py --npm-ci` succeeds with MVP smoke.
3. `npm run build` artifacts uploaded to CDN or web root.
4. Reverse proxy certificates renewed (Let¡¦s Encrypt or enterprise PKI).
5. Rollback plan updated (see `rollback_plan.md`).
6. Telemetry: verify `ui_backend/data/history.json` writes and is collected by monitoring.

## Operational Notes
- MVP smoke path still depends on OpenAI File Search; maintain network egress to api.openai.com.
- Long runs can take >7 minutes; reverse proxy/WebSocket idle timeouts should exceed 10 minutes.
- Rerun `python scripts/ci/run_all.py` whenever dependencies change; the GH workflow (`.github/workflows/ui_pipeline.yml`) mirrors the same steps.
- UI assets are static; bust caches by appending build hashes or toggling nginx `etag`.


