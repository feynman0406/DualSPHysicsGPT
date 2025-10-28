# External STL Integration Plan

## 0. Safety Net / Checkpoint
- Create a feature branch (e.g., `feature/external-stl-intake`).
- Capture current working tree in a lightweight checkpoint commit (`git commit -am "chore: checkpoint before external stl work"`) or stash if commit is not acceptable.
- Tag the commit if needed for rollback (`git tag external-stl-prep`).

## 1. Goals Recap
- Accept a user-supplied STL file in the MVP workflow and propagate it through agents.
- Force RAG retrieval to prioritise `externalstl` examples and rename the placeholder STL file to the user-provided filename.
- Keep XML generation changes minimal beyond swapping file references and required geometry tweaks.
- Update UI so the user can upload the STL alongside the textual query.

## 2. Pipeline & Data-Flow Changes
1. Extend CLI (`scripts/mvp_direct_file_search.py`) and backend invocation to accept `--external-stl <path>`.
   - Validate `.stl` extension and file existence.
   - Copy the file into the run-specific output directory (`logs/mvp/uploads/<run-id>/`) and expose a relative path for downstream agents.
2. Update `ui_backend` models and API:
   - `RunRequest` gains `external_stl: Optional[Path]`.
   - `CreateRunPayload` accepts a boolean flag and optional filename token; the actual file upload handled via multipart endpoint.
   - Save uploads under `logs/ui_backend/runs/<runId>/uploads/` and store metadata in the run record for later retrieval.
3. Ensure `ui_backend.runner._merge_env` or CLI arguments propagate the canonical relative STL path so downstream steps know where to read it.
4. Amend `agents/config.py` (or equivalent orchestrator config) so both Agent 1 and Agent 2 receive structured context about the STL (original name, stored relative path, basic transforms if provided).
5. Update schema / normaliser layers if the STL path must appear in the structured JSON (e.g., add `files` entry with `{ "path": "uploads/<name>.stl", "purpose": "external_geometry" }`).

## 3. Retrieval & Agent Prompt Updates
1. Modify `rag.openai_file_search` so when an external STL is present it automatically appends the keyword `externalstl` to the query text, adds a `must` token, and keeps the Responses include set to `["file_search_call.results"]` so snippet-rich results populate `sources[*].snippets`.
2. Extend `chains/rag_utils.build_metadata_filter` to force `features` or `case_type` search bias towards examples labelled with `externalstl`.
3. Document the include-derived payload: `_collect_tool_calls` and `_derive_sources` must emit `file_id`, `filename`, `score`, `snippets`, and `metadata.source_path`, plus `search_call_id`; update sanitizers (`scripts/mvp_direct_file_search`, `chains/generator`) to expect those keys and remove legacy `search_attempts` references.
4. Patch Agent 1 prompt templates (generator prompt + orchestrator glue):
   - Explicitly instruct replacements of `External.stl` (and variations like `Duck.stl`) with the user-uploaded filename.
   - Emphasise minimal edits elsewhere.
   - Provide handling instructions if multiple `<drawfilestl>` statements exist.
5. Patch Agent 2 instructions and schema alignment to enforce the same rename and to surface warnings when the STL file is missing.
6. Update any agent hand-off JSON structures so they carry `user_provided_stl` metadata (name, rel_path, transforms).

## 4. XML Generation Layer
1. Introduce helper in `AutoXml_script/generate_xml.py` that scans geometry commands for `<drawfilestl file="External.stl">` and swaps in the provided filename.
2. Ensure the helper applies to both `shapeout` preview list and main list to keep normals in sync.
3. For cases with multiple STL references, confirm each uses the same uploaded filename unless Agent 1 overrides it.
4. Extend generator tests to cover STL substitution path.

## 5. UI / UX Tasks
1. Frontend (`ui/app/src/components/NewRunDialog.tsx` and related services):
   - Add drag-and-drop / file picker limited to `.stl`.
   - Display selected filename and allow removal.
   - Validate size threshold (e.g., 25 MB) and show inline errors.
   - Include metadata in API request (likely via `FormData`).
2. Backend API route accepts `multipart/form-data` with `query`, `pauseAfterAgent1`, `execute`, and `externalStl` file field.
   - Continue supporting JSON-only requests when no STL is uploaded.
3. Update UI documentation and onboarding notes (`docs/ui_integration/*`) showing how to attach STL files.

## 6. Testing & Tooling
1. Add unit tests:
   - `tests/ui_backend/test_api.py` for uploads, verifying storage path and RunRequest propagation.
   - `tests/test_generator_json_pipeline.py` to confirm the STL rename occurs in emitted XML.
   - `tests/ui_backend/test_runner.py` to ensure CLI args include the `--external-stl` flag when provided.
   - Add include-flow coverage (`tests/test_openai_file_search.py`) asserting the Responses request sets `include=["file_search_call.results"]` and the persisted sources expose `snippets`, `metadata.source_path`, and `search_call_id`.
2. Include smoke test script update (`scripts/smoke_test_configs.py`) to optionally exercise STL flow.
3. Verify existing regression tests still pass without an STL (backward compatibility).

## 7. Documentation & Hand-off
1. Update `README.md` and `docs/AGENT_QUICK_REFERENCE.md` with STL workflow overview.
2. Produce a troubleshooting section for missing/invalid STL files and retrieval fallbacks.
3. Log new artefacts in `run_mvp` output summary so UI shows the uploaded STL under produced files.

## 8. Deployment / Rollback Considerations
- Ensure environment variables or feature flags gate the STL path until UI rollout is complete.
- Document rollback steps in `docs/ui_integration/rollback_plan.md` (revert to JSON-only flow, disable file input).

