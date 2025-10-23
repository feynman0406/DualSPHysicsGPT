# UI + MVP Execution Guide

Use this checklist whenever you need to drive the protected MVP pipeline from the web UI.

## 1. Environment Setup (one-time)
- Install Python dependencies from repo root:
  ```powershell
  pip install -r requirements.txt
  pip install fastapi uvicorn pytest ruff
  ```
- Install frontend dependencies:
  ```powershell
  cd ui/app
  npm install
  cd ../..
  ```
- Prepare required secrets for MVP smoke runs: set `OPENAI_API_KEY` and `OPENAI_RAG_VS_DESIGN_ID` (plus any other `.env` entries you normally use). Store them in your shell profile or load manually before launching the backend.

## 2. Launch Backend Wrapper
- From repo root run uvicorn (choose an unused port):
  ```powershell
  uvicorn ui_backend.server:app --host 0.0.0.0 --port 8000
  ```
- If you see `Errno 10048`, another process already uses that port. Either stop it (`netstat -ano | findstr :8000` ¡÷ `taskkill /PID <pid> /F`) or restart uvicorn on a different port, e.g. `--port 8001`.
- Backend stores history under `logs/ui_backend/data/run_history.json` and generated artifacts under `logs/ui_backend/runs/<run-id>/`.

## 3. Launch Frontend UI
- In a separate terminal:
  ```powershell
  cd ui/app
  npm run dev
  ```
- Vite prints a URL (default `http://127.0.0.1:5173`). If uvicorn runs on a different port or host, set `VITE_API_BASE_URL` in `ui/app/.env.local` (e.g. `VITE_API_BASE_URL=http://127.0.0.1:8001`) before `npm run dev`.

## 4. Run the MVP Pipeline via UI
1. Open the Vite URL in the browser.
2. The Run List loads existing executions from the history store.
3. Click **New Run** (or equivalent), enter your simulation query, and submit.
4. The backend shells out to the MVP CLI; UI updates the stage stepper, logs, metrics, and artifacts as telemetry arrives.
5. On completion, download artifacts (e.g. `generated_case.xml`, `agent1_output.json`) from the UI or directly from `logs/ui_backend/runs/<run-id>/`.

## 5. Regression & Validation (recommended)
- Credential-free dry run:
  ```powershell
  scripts/run_full_regression.ps1 -SkipMvp
  ```
- Full pipeline once secrets are configured:
  ```powershell
  scripts/run_full_regression.ps1
  ```
- Mac/Linux equivalent: `bash scripts/run_full_regression.sh [--skip-mvp]`. CMD wrapper: `scripts\run_full_regression.bat`.

## 6. Troubleshooting
- **Missing OpenAI credentials**: backend emits "Missing OPENAI_API_KEY"; export both variables and rerun.
- **Port already in use**: free the port or pick a new one for uvicorn/Vite.
- **UI cannot reach backend**: check browser dev tools; ensure API calls target the correct host/port and adjust `VITE_API_BASE_URL` if needed.
- **Stale history**: delete `logs/ui_backend/data/run_history.json` to reset the list (artifacts remain safe under `logs/ui_backend/runs`).

Keep this guide in sync when backend ports change or new governance requirements land.
