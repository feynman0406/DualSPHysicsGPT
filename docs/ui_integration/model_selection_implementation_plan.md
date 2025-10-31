# UI Model Selection Implementation Plan

## Stage Overview

| Stage | Description | Status |
| --- | --- | --- |
| 1 | Establish shared model options on frontend and backend | Completed |
| 2 | Extend backend API and runner to accept per-run model selection | Completed |
| 3 | Update frontend dialog, types, and API client to send selected model | Completed |
| 4 | Refresh documentation to describe per-run model selection | Completed |
| 5 | Execute automated + manual validation | Completed |

## Detailed Tasks

### Stage 1 ¡V Shared Model Configuration
Status: Completed
- Backend allow-list defined in ui_backend/model_options.py.
- Frontend constants exported from ui/app/src/constants/models.ts.
- Create a definitive list of allowed models (`gpt-5-mini`, `gpt-5-nano`, `gpt-5`) in backend (e.g. `ui_backend/model_options.py`).
- Mirror the list in the UI (new `ui/app/src/constants/models.ts`).
- (Optional) unit test to guard drift between frontend/backend lists.

### Stage 2 ¡V Backend Handling
Status: Completed
- API validates and stores per-run model selection.
- Runner/env + history now carry the chosen model.
- Update `CreateRunPayload` in `ui_backend/api.py` to accept optional `model`/`modelName`.
- Validate incoming model against allowed list; return HTTP 400 on invalid value.
- Store the selection in `RunRequest` (either via new field or `env`).
- Ensure `run_mvp` receives `OPENAI_MODEL` via environment merge.
- Persist `model_name` in history for queued/running/complete states.

### Stage 3 ¡V Frontend Wiring
Status: Completed
- Dialog adds model selector backed by shared constants (default gpt-5-mini).
- API client + request types send model for JSON and multipart flows.
- Extend `NewRunFormValues` with `model` and render a `<select>` in `NewRunDialog`.
- Thread the value through `RunListPage` create handler and React Query mutation.
- Update `CreateRunRequest` type and `apiClient.createRun` to send the field for JSON and multipart cases.
- Adjust component/API tests to cover the new behavior.

### Stage 4 ¡V Documentation
Status: Completed
- API contract/table now lists model_name and multipart expectations.
- Usage guide highlights the model dropdown and per-run recording.
- Update `docs/ui_integration/api_contract.md`, `env_matrix.md`, and `ui_usage_guide.md` to capture the new selection flow.

### Stage 5 ¡V Validation
Status: Completed
- Backend pytest (PYTHONPATH=.) passed for runner/api/history suites.
- Vitest suite succeeds; eslint still reports pre-existing react/no-unescaped-entities in ui/app/src/components/OverviewPanel.tsx.
- Manual smoke guidance remains unchanged when credentials are available.

## Notes
- Do not modify baseline MVP assets or other read-only directories listed in `docs/ui_integration/baseline_manifest.md`.
- Update the status table above as stages complete.














