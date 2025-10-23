# External STL Integration – Agent Prompt Pack

This document provides ready-to-send prompts for the agents that will implement the External STL workflow. Each prompt references the shared implementation plan at `docs/external_stl_integration_plan.md` and highlights the requirement that any retrieved reference using `External.stl` must be rewritten to use the user-supplied STL filename while keeping all other edits minimal.

## Agent A – Repository Safety Checkpoint
**Mission**: Create a reversible checkpoint before the feature work starts.

**Key Files**: Entire repo (no code edits expected).

**Prompt**:
```
You are acting as a release engineer. Before other agents start work, create a safety checkpoint for the current repository state.

1. Read `docs/external_stl_integration_plan.md` for context.
2. Create a feature branch named `feature/external-stl-intake` (if it does not already exist).
3. Stage and commit the current working tree with message `chore: checkpoint before external stl work`. If committing is not acceptable, capture an equivalent stash and document it in `logs/ui_backend/runs/`.
4. (Optional) Tag the commit `external-stl-prep` if policy allows.
5. Report the resulting git status and checkpoint details.

Do not modify source files or run tests.
```

## Agent B – Backend & CLI Integration
**Mission**: Wire the external STL file through CLI, backend API, runner, and RunRequest model.

**Key Files**: `scripts/mvp_direct_file_search.py`, `ui_backend/api.py`, `ui_backend/models.py`, `ui_backend/runner.py`, `tests/ui_backend/test_api.py`, `tests/ui_backend/test_runner.py`.

**Prompt**:
```
You are the backend engineer for the DualSPHysics MVP.

Reference plan: `docs/external_stl_integration_plan.md` (sections 2 & 5 & 6).

Scope:
1. Accept a `--external-stl <path>` argument in `scripts/mvp_direct_file_search.py`; validate extension, copy the file into `logs/mvp/uploads/<run-id>/`, and pass the canonical relative path downstream.
2. Update `ui_backend` models and API to accept an optional STL upload (multipart form) and propagate it via `RunRequest` and CLI args. Save uploaded files under the per-run directory.
3. Ensure the runner environment exposes the stored relative path (e.g., via env var or CLI flag) and record the uploaded file as a produced artifact.
4. Keep backward compatibility when no STL is provided.
5. Add/adjust backend tests to cover both with-STL and without-STL flows.

Deliverables:
- Updated code with inline validation and clear error messages.
- Tests demonstrating CLI argument propagation and API upload handling.
- Notes in commit or PR description if filesystem permissions are required.

Remember: minimal edits outside the described scope.
```

## Agent C – Retrieval & Agent Prompt Updates
**Mission**: Force RAG to search `externalstl` examples and update Agent 1/2 instructions to rename STL files.

**Key Files**: `rag/openai_file_search.py`, `chains/rag_utils.py`, `chains/generator.py`, `prompts/generator_system_prompt.md`, `prompts/fixer_system_prompt.md`, `docs/agent1_prompt_request.md`, `docs/agent2_prompt_request.md`, relevant tests under `tests/`.

**Prompt**:
```
You are responsible for retrieval strategy and prompt governance.

Reference plan: `docs/external_stl_integration_plan.md` (sections 3 & 4 & 7).

Tasks:
1. When the pipeline indicates a user-uploaded STL (check the new context field), ensure file search queries and filters include the `externalstl` keyword. Update `_compose_query_text` or equivalent helper plus metadata filters in `chains/rag_utils.build_metadata_filter`.
2. Expose the STL metadata (original filename, stored relative path) to both Agent 1 and Agent 2. Update `chains/generator.py` (or orchestrator glue) so the LLM payload includes this context.
3. Edit `prompts/generator_system_prompt.md` and related docs so Agent 1 MUST replace any occurrence of `External.stl`, `Duck.stl`, or similar placeholders with the user-provided filename and otherwise perform minimal edits. Reinforce that both `<list>` and `<mainlist>` blocks must stay in sync.
4. Update Agent 2 prompts/schema helpers so the generated JSON also swaps the STL filename and warns if the file path is missing.
5. Add or adjust tests (unit or golden) to confirm: (a) retrieval queries append `externalstl`; (b) the generator prompt text contains the new instructions.

Output requirements:
- Keep instructions concise but explicit.
- Do not break non-STL flows; keyword injection should only occur when STL metadata is present.
```

## Agent D – XML Generator Enhancements
**Mission**: Swap placeholder STL filenames in the generated XML using the uploaded filename.

**Key Files**: `AutoXml_script/generate_xml.py`, `tests/test_generate_xml.py`, reference XML templates under `AutoXml_script/`.

**Prompt**:
```
You are working on the XML generator layer.

Reference plan: `docs/external_stl_integration_plan.md` (sections 4 & 6).

Objectives:
1. Detect when the case definition includes `<drawfilestl file="External.stl">` (or similar placeholder) and replace it with the user-provided STL filename delivered via the config or context.
2. Ensure both the normals list and the main geometry list use the same filename, preserving autofill/advanced attributes.
3. Keep other geometry commands untouched unless absolutely required by the rename.
4. Extend `tests/test_generate_xml.py` to cover: (a) no STL provided (no change); (b) STL provided and both occurrences are swapped.
5. Verify generated XML remains valid and minimal differences exist relative to the template.
```

## Agent E – UI / Frontend Updates
**Mission**: Add STL upload support to the MVP UI.

**Key Files**: `ui/app/src/components/NewRunDialog.tsx`, `ui/app/src/services/*`, CSS counterparts, frontend tests (if any), `docs/ui_integration/*`.

**Prompt**:
```
You are the frontend engineer.

Reference plan: `docs/external_stl_integration_plan.md` (sections 5 & 7).

Tasks:
1. Add a file picker (drag-and-drop optional) to `NewRunDialog` for `.stl` files. Display selected filename, size, and provide a remove button.
2. Validate extension and size (<25 MB by default). Surface inline error messages without blocking other validations.
3. Update API service calls to send `FormData`, including the query payload and the optional STL file, matching the backend contract implemented by Agent B.
4. Update UI state handling so the run history or confirmation screen indicates that an STL was attached (if current UI supports it).
5. Refresh documentation in `docs/ui_integration/*.md` describing how to upload STL files in the MVP UI.

Keep styling consistent with existing components and avoid regressions when no file is selected.
```

## Agent F – QA & Regression
**Mission**: Validate end-to-end behaviour and document findings.

**Key Files**: Tests across repo, `scripts/smoke_test_configs.py`, `docs/ui_integration/rollback_plan.md`.

**Prompt**:
```
You are the QA engineer.

Reference plan: `docs/external_stl_integration_plan.md` (sections 6 & 8).

Checklist:
1. Run updated automated tests (backend, generator, UI where applicable) and ensure they pass.
2. Execute the MVP pipeline twice: once without an STL (baseline) and once with a sample STL (place `samples/Duck.stl`), verifying:
   - File search queries include `externalstl` in the STL run.
   - Agent outputs reference the substituted filename.
   - Generated XML uses the uploaded filename in all `<drawfilestl>` nodes.
   - Stored artefacts include the uploaded STL.
3. Record results in `docs/ui_integration/mvp_reference_runner.py` or a new QA log section, noting any anomalies and how to reproduce them.
4. If issues are found, create tickets or document blockers before sign-off.
```

---
All agents should cross-reference the shared implementation plan and keep non-STL scenarios untouched. When the user supplies an external STL, every stage must rename `External.stl` (or similar placeholder) to the uploaded filename and otherwise apply the minimal necessary edits.
