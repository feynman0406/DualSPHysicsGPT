# Codex Agent Prompt Pack

Repository root: `C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT`.

## How to Use
- Pick the block that matches the step you want the agent to own, replace placeholders (for example `<BRANCH_NAME>`), and send it as the only prompt.
- Do not mix prompts; each block repeats the global constraints and is self-contained.
- Keep `docs/ui_integration/progress_log.md` up to date and ensure agents attach test results with every handoff while maintaining `docs/ui_integration/agent_coordination_log.md` (read before starting, log ISO-8601 start/finish entries).

## Shared Agent Reminders
- Read `docs/ui_integration/agent_coordination_log.md` before touching the repo, and append ISO-8601 start/finish entries (with dependency notes) to the Progress Timeline for every assignment.
- In 2D scenarios the geometry is activated by keeping `geometry.definition.pointmin.y` and `pointmax.y` at `0`, but every `fillbox`/`void` command must still provide a finite thickness in `size.y` (for example `#Dp*2`). Collapsing the box to zero thickness removes all initial particles, so even purely 2D requests should emit 3D-sized boxes.

- Force fluid fillboxes to stay valid: inside any `<setmkfluid>` block, always emit `<modefill>void</modefill>`, keep the fillbox origin inside its fluid definition bounds (`point.axis <= fillbox.axis <= point.axis + size.axis`), and when `pointmin.y == pointmax.y` (2D) snap `fillbox.y` to that plane.

## Kickoff Prompt
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. Treat the following locations as read-only unless a later manifest explicitly allows changes: scripts/, chains/, logs/mvp/ (current contents), AutoXml_script/, api/, schemas/, CaseSloshingHR_Def_from_xml_out_direct/, Case_out/, metrics/, prompts/, rag/, tests/, tools/, and anything listed in docs/ui_integration/baseline_manifest.md. Never edit, move, or delete these assets. All new artifacts must live inside docs/ui_integration/, ui_backend/, ui/app/, tests/ui_backend/, ui/tests/, or other writable locations explicitly assigned in the phase prompts. Always run relevant tests before handoff, capture commands with summarized results, update docs/ui_integration/progress_log.md when a phase ends, and log ISO-8601 start/finish entries (with dependency notes) in docs/ui_integration/agent_coordination_log.md. Do not check secrets into the repository.

Acknowledge the constraints, list any clarifying questions, then wait for the phase-specific prompt before making changes.
```

## Phase 0 �V Baseline Audit
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. All locations listed in the Kickoff prompt are read-only. For Phase 0 you may create or modify files only under docs/ui_integration/ and logs/mvp/reference_run/.

Phase objective: capture the exact behavior of the existing MVP CLI pipeline without modifying it.

Before you begin:
- Read `docs/ui_integration/agent_coordination_log.md` before taking action, note prior decisions, and add an ISO-8601 kickoff entry covering goals/dependencies.
- Review README.md, TEST_MVP.md, and docs/MVP_USAGE.md to understand the official workflow.
- Confirm the required environment variables from .env or user input.

Tasks:
1. Enumerate all MVP CLI entry points and required environment variables.
2. Execute one clean MVP run using the documented command; do not edit inputs. Save stdout/stderr to logs/mvp/reference_run/mvp_run.log and copy resulting artifacts into logs/mvp/reference_run/.
3. Produce integrity metadata (hashes, sizes, timestamps) for the captured artifacts.
4. Document environment requirements in docs/ui_integration/env_matrix.md (variables, defaults, effects).
5. Author docs/ui_integration/baseline_manifest.md listing every file/folder treated as immutable.
6. Update docs/ui_integration/progress_log.md (and append matching completion entry in docs/ui_integration/agent_coordination_log.md) with a Phase 0 summary, verification steps, and open issues.

Deliverables:
- docs/ui_integration/baseline_manifest.md
- docs/ui_integration/env_matrix.md
- logs/mvp/reference_run/ (artifacts + mvp_run.log + checksum listing)
- Updated docs/ui_integration/progress_log.md (completion logged in docs/ui_integration/agent_coordination_log.md)

Validation:
- Provide the exact commands executed and a concise digest of hash outputs.
- Explicitly confirm that no read-only assets were modified.

Reporting:
- Finish with a recap of tasks completed, deliverable paths, validation commands, and remaining questions.
```

## Phase 1 �V Wrapper/API Layer
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. All locations listed in the Kickoff prompt and docs/ui_integration/baseline_manifest.md are read-only. For this phase you may modify/create files only under ui_backend/, tests/ui_backend/, docs/ui_integration/, logs/ui_backend/, and supporting configuration files (for example .gitignore) when necessary.

Phase objective: expose the MVP CLI via a reusable wrapper/API layer without altering MVP source.

Before you begin:
- Read `docs/ui_integration/agent_coordination_log.md` before taking action, note prior decisions, and add an ISO-8601 kickoff entry covering goals/dependencies.
- Read docs/ui_integration/baseline_manifest.md, env_matrix.md, progress_log.md, and docs/ui_integration/agent_coordination_log.md.
- Re-run the MVP reference flow using Phase 0 instructions to ensure the environment works (do not edit outputs).

Tasks:
1. Implement ui_backend/runner.py wrapping scripts/mvp_direct_file_search.py via subprocess with parameters (query, pause_after_agent1, execute, output_dir).
2. Create ui_backend/models.py defining request/response dataclasses (status, timestamps, log path, produced files, error info).
3. Create ui_backend/errors.py translating exit codes and stderr signatures into human-readable messages.
4. Write tests/ui_backend/test_runner.py covering success paths (using the reference query) and failure paths (for example missing environment variable). Use temporary directories so MVP outputs stay untouched.
5. Document the contract in docs/ui_integration/api_contract.md (interfaces, parameters, sample payloads, error behaviors).
6. Update docs/ui_integration/progress_log.md (and append matching completion entry in docs/ui_integration/agent_coordination_log.md) with a Phase 1 summary, test commands, and outstanding questions.

Deliverables:
- ui_backend/runner.py, ui_backend/models.py, ui_backend/errors.py (and __init__.py if needed)
- tests/ui_backend/test_runner.py
- docs/ui_integration/api_contract.md
- Updated docs/ui_integration/progress_log.md (completion logged in docs/ui_integration/agent_coordination_log.md)
- Supporting configuration updates if introduced (list them)

Validation:
- Run `pytest tests/ui_backend -q` and capture results.
- Demonstrate the wrapper executing the MVP flow without changing baseline outputs (command + brief outcome).
- Confirm no read-only files were modified (a `git status` summary is acceptable).

Reporting:
- Provide a feature summary, deliverable paths, validation commands/results, and risks or TODOs for Phase 2.
```

## Phase 2 �V UX Specification
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. All read-only restrictions remain in force. For Phase 2 you may only create or edit documentation within docs/ui_integration/ (and optional docs/ui_integration/assets/). Do not modify code.

Phase objective: produce the UX specification for the future UI.

Before you begin:
- Read `docs/ui_integration/agent_coordination_log.md` before taking action, note prior decisions, and add an ISO-8601 kickoff entry covering goals/dependencies.
- Review docs/ui_integration/api_contract.md, baseline_manifest.md, env_matrix.md, progress_log.md, and docs/ui_integration/agent_coordination_log.md.
- Examine logs/mvp/reference_run/ outputs to understand available data.

Tasks:
1. Draft low-fidelity wireframes covering Run List, Run Detail (stepper), log viewer, metrics widgets, and artifact viewer. Save references in docs/ui_integration/wireframes.md (link to Figma or embed ASCII diagrams). Store assets under docs/ui_integration/assets/ if needed.
2. Document component states in docs/ui_integration/ui_state_matrix.md (idle/running/success/failure per view).
3. Define data contracts in docs/ui_integration/data_contracts.md with JSON examples or schema snippets for run summaries, log entries, metrics snapshots, and artifact metadata.
4. Note any missing backend data that later phases must provide.
5. Update docs/ui_integration/progress_log.md (and append matching completion entry in docs/ui_integration/agent_coordination_log.md) with a Phase 2 summary, decisions, and open issues.

Deliverables:
- docs/ui_integration/wireframes.md (+ assets if relevant)
- docs/ui_integration/ui_state_matrix.md
- docs/ui_integration/data_contracts.md
- Updated docs/ui_integration/progress_log.md (completion logged in docs/ui_integration/agent_coordination_log.md)

Validation:
- Cross-check data contracts against Phase 1 API outputs; record expected extensions.
- Confirm no read-only files were modified.

Reporting:
- Summarize produced artifacts, highlight dependency or gap notes, and list next steps feeding into Phase 3.
```

## Phase 3 �V UI Foundation
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. All locations noted in previous prompts and baseline_manifest are read-only. For this phase you may modify/create files under ui/app/, ui/tests/, docs/ui_integration/, and supporting configuration files. Do not edit MVP directories.

Phase objective: build the front-end foundation that can trigger the MVP wrapper and display core results.

Before you begin:
- Read `docs/ui_integration/agent_coordination_log.md` before taking action, note prior decisions, and add an ISO-8601 kickoff entry covering goals/dependencies.
- Review docs/ui_integration/wireframes.md, ui_state_matrix.md, data_contracts.md, api_contract.md, progress_log.md, and docs/ui_integration/agent_coordination_log.md.
- Ensure backend wrapper tests still pass (`pytest tests/ui_backend -q`).

Tasks:
1. Scaffold a front-end app under ui/app/ (React, Next, Vite, or similar). Include package.json scripts for dev, build, test, and lint, along with configuration (e.g., ESLint, Prettier). Document setup in ui/app/README.md.
2. Implement an API client (e.g., ui/app/src/services/api.ts) communicating with the backend wrapper; if mocking is required, document the approach clearly.
3. Create screens:
   - Run List page to display runs and trigger new executions.
   - Run Detail view with pipeline stepper invoking the backend runner and showing stage status.
   - Log viewer with polling of backend log files.
   - Artifact viewer for JSON/XML outputs from logs/mvp.
4. Handle UI states per the specification, providing reasonable placeholders where backend data is not yet available.
5. Write a smoke/E2E test under ui/tests/ (e.g., smoke.spec.ts) covering the baseline flow (stubbing API responses is acceptable).
6. Update docs/ui_integration/progress_log.md (and append matching completion entry in docs/ui_integration/agent_coordination_log.md) with Phase 3 summary, integration notes, and gaps.

Deliverables:
- ui/app/ source tree (with README and configuration files)
- ui/tests/smoke.spec.ts (or equivalent)
- Updated docs/ui_integration/progress_log.md (completion logged in docs/ui_integration/agent_coordination_log.md)
- Any new configuration (eslint, prettier, etc.)

Validation:
- Run `npm install`, `npm run build`, and `npm run test` (list the exact commands used) and capture results.
- Provide a manual or scripted walkthrough of the baseline user flow and highlight the observed outputs.
- Confirm read-only assets remain untouched.

Reporting:
- Summaries of implemented features, deliverable paths, test outputs, and outstanding issues feeding Phase 4.
```

## Phase 4 �V Execution Monitoring Enhancements
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. Respect all read-only constraints. For this phase you may modify/create files under ui_backend/, ui_backend/data/, tests/ui_backend/, ui/app/, ui/tests/, and docs/ui_integration/.

Phase objective: add execution monitoring, resource metrics, and run history while keeping the MVP untouched.

Before you begin:
- Read `docs/ui_integration/agent_coordination_log.md` before taking action, note prior decisions, and add an ISO-8601 kickoff entry covering goals/dependencies.
- Review the latest backend/frontend code, api_contract.md, data_contracts.md, ui_state_matrix.md, progress_log.md, and docs/ui_integration/agent_coordination_log.md.
- Run existing tests (pytest and frontend smoke) to ensure a clean baseline.

Tasks:
1. Backend:
   - Implement ui_backend/history_store.py (SQLite or JSON) persisting run metadata (id, query, timestamps, status, artifacts) under ui_backend/data/.
   - Implement ui_backend/metrics.py to collect CPU/GPU stats (psutil, nvidia-smi) with graceful fallback when unavailable.
   - Update runner endpoints to emit stage checkpoints (init/sim/post) and metrics snapshots suitable for polling/streaming.
   - Revise docs/ui_integration/api_contract.md to document new endpoints/fields.
2. Frontend:
   - Connect Run List to the history store and display persisted runs.
   - Enhance Run Detail with segmented progress bars, timestamps, and status indicators per stage.
   - Add resource usage widgets showing CPU/GPU utilization with fallback messaging.
3. Testing:
   - Extend backend pytest coverage for history persistence and metrics fallback behavior (simulate missing nvidia-smi).
   - Update frontend tests to cover new UI states.
4. Documentation:
   - Update docs/ui_integration/data_contracts.md, ui_state_matrix.md, progress_log.md, docs/ui_integration/agent_coordination_log.md for new fields or behaviors.

Deliverables:
- Updated ui_backend modules (runner changes, history_store.py, metrics.py, data configuration)
- Updated ui/app/ components and associated tests
- Updated docs/ui_integration/api_contract.md, data_contracts.md, ui_state_matrix.md, progress_log.md, and docs/ui_integration/agent_coordination_log.md

Validation:
- Provide `pytest` output and frontend test results.
- Demonstrate history persistence across process restarts (describe steps executed).
- Show metrics fallback behavior when system tools are unavailable (command + observed outcome).
- Confirm no read-only assets were modified.

Reporting:
- Summaries, deliverable paths, validation commands, and remaining risks or TODOs for Phase 5.
```

## Phase 5 �V Stabilization & Deployment
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. Read-only restrictions remain. For this phase you may modify/create files under .github/workflows/, scripts/ci/, ui_backend/, ui/app/, docs/ui_integration/, ui/tests/, tests/ui_backend/, and related configuration files, but never alter MVP directories.

Phase objective: harden testing, CI, and deployment so the UI layers coexist safely with the MVP pipeline.

Before you begin:
- Read `docs/ui_integration/agent_coordination_log.md` before taking action, note prior decisions, and add an ISO-8601 kickoff entry covering goals/dependencies.
- Review the latest documentation and code produced through Phase 4.
- Ensure existing tests pass (pytest, frontend suite).

Tasks:
1. Implement a unified CI pipeline (e.g., .github/workflows/ui_pipeline.yml or scripts/ci/run_all.sh) that executes: (a) MVP smoke command documented in Phase 0, (b) `pytest tests/ui_backend`, and (c) frontend lint/build/test (e.g., `npm run lint && npm run build && npm run test`).
2. Add or finalize lint/format configurations (Ruff, ESLint, Prettier) and wire them into package scripts and CI.
3. Write docs/ui_integration/deployment.md covering local development, staging/production deployment, environment variables, reverse proxy or service supervision, and optional Docker instructions if supplied.
4. Create docs/ui_integration/rollback_plan.md referencing the baseline manifest, regression commands, and data backup steps.
5. Perform a dry run following the deployment guide; capture logs or screenshots and store them under docs/ui_integration/assets/ (referenced from the guide).
6. Update docs/ui_integration/progress_log.md (and append matching completion entry in docs/ui_integration/agent_coordination_log.md) with Phase 5 summary, test commands, and outstanding issues.

Deliverables:
- CI workflow or scripts executing the combined pipeline
- Lint/format configuration files (if added or updated)
- docs/ui_integration/deployment.md and docs/ui_integration/rollback_plan.md (with assets if applicable)
- Updated docs/ui_integration/progress_log.md (completion logged in docs/ui_integration/agent_coordination_log.md)

Validation:
- Provide local output from the CI script/workflow run.
- Show lint/build/test command results.
- Confirm read-only assets remain unchanged.

Reporting:
- Summaries, deliverable paths, validation commands, and follow-up items for Phase 6.
```

## Phase 6 �V Continuous Improvement Framework
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. Respect all read-only constraints. For this phase you may modify/create files under docs/ui_integration/, .github/, scripts/, and other governance-related areas, but never touch MVP directories.

Phase objective: establish a repeatable improvement framework while protecting the MVP baseline.

Before you begin:
- Read `docs/ui_integration/agent_coordination_log.md` before taking action, note prior decisions, and add an ISO-8601 kickoff entry covering goals/dependencies.
- Review all documentation produced in prior phases (api_contract.md, wireframes, state matrix, deployment guide, progress_log.md, docs/ui_integration/agent_coordination_log.md, etc.).
- Ensure regression scripts and tests from earlier phases run cleanly.

Tasks:
1. Create docs/ui_integration/backlog.md listing prioritized feature ideas with rationale, dependencies, and impact.
2. Create docs/ui_integration/contribution_checklist.md detailing required steps before opening PRs (manifest check, tests, lint, regression script, documentation updates).
3. Add templates:
   - .github/ISSUE_TEMPLATE/ui_task.md for new work requests.
   - .github/PULL_REQUEST_TEMPLATE/ui_changes.md referencing the contribution checklist and baseline manifest confirmation.
4. Implement scripts/run_full_regression.sh (and scripts/run_full_regression.bat if Windows support is needed) that execute the MVP smoke command, backend pytest suite, and frontend tests; ensure the script exits on failure and logs outputs.
5. Update docs/ui_integration/progress_log.md (and append matching completion entry in docs/ui_integration/agent_coordination_log.md) with governance notes, maintenance cadence, and escalation paths.
6. Document any optional automation or telemetry hooks if relevant.

Deliverables:
- docs/ui_integration/backlog.md
- docs/ui_integration/contribution_checklist.md
- .github/ISSUE_TEMPLATE/ui_task.md
- .github/PULL_REQUEST_TEMPLATE/ui_changes.md
- scripts/run_full_regression.sh (and .bat variant if provided)
- Updated docs/ui_integration/progress_log.md (completion logged in docs/ui_integration/agent_coordination_log.md)
- Additional governance docs if added

Validation:
- Run the regression script(s) and provide condensed output.
- Ensure backlog items tie back to prior findings or user goals.
- Confirm read-only assets remain untouched.

Reporting:
- Summaries, deliverable paths, validation commands, and any recommended future actions.
```

## Bug Investigation Prompt
```
You are GPT-5 Codex working inside repository C:\Users\user\Desktop\Jiejiang SPH\DualSPHysicsGPT on branch <BRANCH_NAME>. Respect all read-only constraints (scripts/, chains/, logs/mvp/, AutoXml_script/, api/, schemas/, metrics/, prompts/, rag/, tests/, tools/, anything in docs/ui_integration/baseline_manifest.md). You may create/modify files only in docs/ui_integration/, ui_backend/, ui/app/, tests/ui_backend/, ui/tests/, or other locations explicitly approved in the linked issue.

Context: Issue <ISSUE_LINK_OR_ID> describes bug "<BUG_SUMMARY>" with reproduction steps:
<REPRO_STEPS>
Relevant logs or artifacts are stored at <LOG_PATHS>. The baseline reference run remains in logs/mvp/reference_run/.

Objectives:
- Reproduce the defect, isolate the root cause, and implement a fix without touching MVP baseline sources.
- Ensure automated coverage exists (new or updated tests) so the regression cannot recur silently.
- Document findings and keep governance records current.

Tasks:
1. Review the issue details, attached logs, and related entries in docs/ui_integration/backlog.md.
2. Reproduce the problem with the provided commands; capture fresh logs under logs/ui_backend/ or docs/ui_integration/ if needed.
3. Implement the fix within writable directories only; adjust UI/backend code and tests as required.
4. Run `scripts/run_full_regression.sh` (or `.ps1`/`.bat`). Use `--skip-mvp` only when OpenAI credentials are unavailable. Add any extra targeted tests or linters as appropriate.
5. Update docs/ui_integration/progress_log.md (and append matching completion entry in docs/ui_integration/agent_coordination_log.md) with the investigation summary, tests executed, and residual risks. Add or revise backlog items if follow-up work is required.

Deliverables:
- Code and test updates inside allowed directories.
- Optional supporting logs or artifacts demonstrating the fix.
- Updated documentation (progress_log.md, docs/ui_integration/agent_coordination_log.md, and backlog.md when applicable).

Validation:
- Provide condensed results of regression and targeted test commands.
- Explicitly confirm that read-only MVP assets remain untouched.

Reporting:
- Conclude with the handoff summary checklist (phase/branch, fixes, deliverables, commands, remaining issues) before requesting review.
```
## Checkpoint Status Prompt
```
Provide a mid-phase status update:
1. Current phase and objectives restated.
2. Files created/modified (paths) with confirmation that no read-only locations were touched.
3. Tests run so far (or planned) and their status.
4. Risks or blockers needing attention.
5. Next planned actions.

Pause further changes until this update is reviewed.
```

## Handoff Summary Prompt
```
Before closing the phase, output a handoff summary:
1. Phase name and branch.
2. Key accomplishments (1�V3 bullet points).
3. Detailed deliverables with relative paths.
4. Commands/tests executed with results.
5. Known issues, TODOs, or follow-up tasks.
6. Explicit confirmation that read-only MVP files remain unchanged.

Wait for approval before merging or starting the next phase.
```


