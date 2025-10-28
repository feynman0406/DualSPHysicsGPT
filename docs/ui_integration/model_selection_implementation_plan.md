# UI Model Selection Implementation Plan

## Stage Overview

| Stage | Description | Status |
| --- | --- | --- |
| 1 | Establish shared model options on frontend and backend | Pending |
| 2 | Extend backend API and runner to accept per-run model selection | Pending |
| 3 | Update frontend dialog, types, and API client to send selected model | Pending |
| 4 | Refresh documentation to describe per-run model selection | Pending |
| 5 | Execute automated + manual validation | Pending |

## Detailed Tasks

### Stage 1 ¡V Shared Model Configuration
- Create a definitive list of allowed models (`gpt-5-mini`, `gpt-5-nano`, `gpt-5`) in backend (e.g. `ui_backend/model_options.py`).
- Mirror the list in the UI (new `ui/app/src/constants/models.ts`).
- (Optional) unit test to guard drift between frontend/backend lists.

### Stage 2 ¡V Backend Handling
- Update `CreateRunPayload` in `ui_backend/api.py` to accept optional `model`/`modelName`.
- Validate incoming model against allowed list; return HTTP 400 on invalid value.
- Store the selection in `RunRequest` (either via new field or `env`).
- Ensure `run_mvp` receives `OPENAI_MODEL` via environment merge.
- Persist `model_name` in history for queued/running/complete states.

### Stage 3 ¡V Frontend Wiring
- Extend `NewRunFormValues` with `model` and render a `<select>` in `NewRunDialog`.
- Thread the value through `RunListPage` create handler and React Query mutation.
- Update `CreateRunRequest` type and `apiClient.createRun` to send the field for JSON and multipart cases.
- Adjust component/API tests to cover the new behavior.

### Stage 4 ¡V Documentation
- Update `docs/ui_integration/api_contract.md`, `env_matrix.md`, and `ui_usage_guide.md` to capture the new selection flow.

### Stage 5 ¡V Validation
- Run backend tests (`pytest tests/ui_backend -k run`).
- Run frontend tests/lint (`npm test -- --runInBand`, `npm run lint`).
- Manual smoke: trigger runs with different models (document instructions only if credentials unavailable).

## Notes
- Do not modify baseline MVP assets or other read-only directories listed in `docs/ui_integration/baseline_manifest.md`.
- Update the status table above as stages complete.
