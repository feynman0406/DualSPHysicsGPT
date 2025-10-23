# Phase 5 Rollback Plan

## Scope
- Applies to regressions introduced while deploying the UI backend / SPA or the consolidated CI pipeline.
- MVP CLI and referenced assets stay immutable; rely on `docs/ui_integration/baseline_manifest.md` to confirm protected paths.

## Trigger Conditions
- CI failure in `.github/workflows/ui_pipeline.yml` on protected branches.
- MVP smoke run (`python scripts/mvp_direct_file_search.py`) producing diffs against `logs/mvp/reference_run/` artifacts.
- Backend API regression (FastAPI 5xx, corrupted history store) detected by health checks.
- Frontend build failures or rendering errors after deployment.

## Immediate Response
1. **Freeze traffic**
   - Disable reverse proxy upstreams or scale replicas to zero.
   - Announce downtime in status channel.
2. **Capture diagnostics**
   - Archive `logs/ui_backend/*.log` (if configured) and `ui_backend/data/history.json`.
   - Store CI artefacts: rerun `python scripts/ci/run_all.py --skip-mvp --skip-frontend > docs/ui_integration/assets/rollback_smoke.txt` for evidence.
3. **Assess blast radius**
   - Compare new assets with manifest: `git status --short` should highlight only writable directories (docs/ui_integration, ui_backend, ui/app, scripts/ci, tests/ui_backend, ui/tests).

## Rollback Steps
1. **Restore binaries & configs**
   - Re-deploy the last known good release bundle (static UI + backend wheel/container).
   - Reset repo state on deployment host:
     ```bash
     git fetch origin
     git reset --hard origin/main
     git clean -fdx ui/app/dist ui_backend/data
     ```
2. **Rehydrate baseline artifacts**
   - Copy `logs/mvp/reference_run/` back to hot storage if agents need diffing support.
   - Validate with the Phase 0 command:
     ```powershell
     $env:PYTHONIOENCODING='utf-8'
     python docs/ui_integration/mvp_reference_runner.py
     ```
3. **Verify services**
   - Backend: `uvicorn --factory ui_backend.api:create_router --port 8000` (temporary foreground run) and hit `/runs` endpoint.
   - Frontend: serve last stable `dist/` snapshot; open `/` and ensure history loads with cached data.
4. **Re-enable traffic** after two consecutive CI passes and manual UI check.

## Data Considerations
- **History store**: copy `ui_backend/data/history.json` prior to resets; on rollback restore from backup, then restart service.
- **MVP artifacts**: never delete `logs/mvp/reference_run/*`; use manifest hash file (`artifact_manifest.csv`) to ensure integrity.

## Post-Rollback Actions
1. File incident report summarising root cause, CI output, and mitigation timeline.
2. Create hotfix branch to house entry that caused regression, keeping new commits quarantined.
3. Run `python scripts/ci/run_all.py --npm-ci` once fixes land; attach output to progress log.
4. Update `docs/ui_integration/progress_log.md` with rollback details and outstanding remediation actions.

## Regression Test Suite
- `python scripts/ci/run_all.py --npm-ci` (full pipeline including MVP smoke).
- `python -m pytest tests/ui_backend -q` (fast backend verification).
- `npm run lint && npm run test -- --run` from `ui/app` (frontend sanity).
- Optional: `python scripts/mvp_direct_file_search.py --query "2D dambreak case"` under controlled credentials for end-to-end verification.
