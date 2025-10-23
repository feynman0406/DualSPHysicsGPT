# UI Preparation Plan for DualSPHysicsGPT MVP

## Purpose
- Establish a concrete roadmap that readies the current MVP workflow (file search ¡÷ config generation ¡÷ XML ¡÷ execution) for a UI layer.
- Reduce rework by stabilizing the orchestration and data contracts before visual design and implementation begin.
- Provide shared artifacts (API specs, user flows, wireframes) that keep backend, UX, and frontend efforts aligned.

## Current Context
- CLI-based MVP script (`scripts/mvp_direct_file_search.py`) handles Agent?1, Agent?2, XML generation, and optional GenCase execution.
- Outputs are persisted under `logs/mvp/`, but consumers must scrape files and console logs manually.
- Planned service/helper layer will expose the same pipeline as reusable functions and future FastAPI endpoints.
- No dedicated UI yet; requirements emphasize transparency of each stage, artifact inspection, and rerun controls.

## Guiding Principles
1. **Single source of truth** ¡V Service layer defines data contracts; UI only consumes documented responses.
2. **Observability first** ¡V Every stage must expose status, summaries, errors, and artifact paths.
3. **Incremental UX** ¡V Start with MVP screens (request entry, run workspace, artifacts) and expand once feedback arrives.
4. **Automation parity** ¡V UI actions should mirror CLI/API capabilities (pause after Agent?1, execute flag, reruns).
5. **Testability** ¡V Maintain backend smoke tests and UI integration tests tied to the same fixtures.

## Workstreams & Tasks

### 1. Backend Stabilization (Service Layer)
- [ ] Extract orchestration into `services/mvp_runner.py` with `run_mvp()` entrypoint.
- [ ] Return structured results (`Agent1Result`, `Agent2Result`, `ExecutionResult`) including artifact paths and warnings.
- [ ] Define custom exceptions for stage failures with machine-readable `code`/`message`.
- [ ] Centralize environment validation (e.g., `validate_mvp_env()`).
- [ ] Add unit tests covering happy path and failure scenarios (missing env var, Agent?2 schema diff, GenCase error).

### 2. API Contract & Infrastructure
- [ ] Add FastAPI routes:
  - `POST /runs`: trigger `run_mvp()`; allow flags (`pause_after_agent1`, `execute`).
  - `GET /runs/{id}`: return run metadata and stage statuses.
  - `GET /runs/{id}/artifacts`: list downloadable files.
  - `GET /runs/{id}/stream`: Server-Sent Events for live updates (optional v1: polling).
- [ ] Document request/response schemas in `docs/api/ui_contract.md` (OpenAPI snippets or tables).
- [ ] Implement persistence for run records (reuse `sessions/` or new lightweight store).
- [ ] Add API smoke test invoking the full pipeline with mocked OpenAI responses when credentials absent.

### 3. UX Research & User Flows
- [ ] Identify primary personas (internal engineer, reviewer, new agent onboarding).
- [ ] Draft core scenarios:
  1. Submit new NL request and monitor run.
  2. Pause after Agent?1, inspect references, resume.
  3. Review generated config/XML, trigger execution, inspect results.
  4. Replay prior session with updated parameters.
- [ ] Create flow diagrams illustrating stage transitions, data surfaced, and decision points.
- [ ] Validate flows with stakeholders; capture feedback in `docs/ui_feedback.md`.

### 4. Information Architecture & Wireframes
- [ ] Define primary navigation: Dashboard ¡÷ Run Workspace ¡÷ Artifacts.
- [ ] Detail Run Workspace layout (timeline, tabbed content, contextual panel).
- [ ] Produce low-fidelity wireframes (Figma or Excalidraw) and export snapshots to `docs/ui_wireframes/`.
- [ ] Annotate wireframes with required data fields sourced from API responses.

### 5. UI Component Strategy
- [ ] Choose frontend stack (recommended: React + TypeScript + Mantine + Monaco editor).
- [ ] Create component inventory: RequestForm, StatusTimeline, ReferenceList, JsonDiffViewer, XmlViewer, ExecutionConsole, ArtifactBrowser.
- [ ] Document component contracts (props, events, data shape) mapping to API responses.
- [ ] Establish styling guidelines (spacing, colors, typography) consistent with project branding.

### 6. Prototype & Integration Plan
- [ ] Implement mock data layer mirroring API contract for rapid prototyping.
- [ ] Build clickable prototype covering end-to-end flow with mock data.
- [ ] Integrate with live API once service layer stabilizes; guard with feature flag (`ENABLE_UI=1`).
- [ ] Set up CI job running frontend lint/tests and contract tests against OpenAPI schema.

### 7. Validation, Docs, and Rollout
- [ ] Define acceptance criteria checklist (stage visibility, artifact access, error reporting, rerun controls).
- [ ] Conduct usability review sessions; log findings in `docs/ui_usability_notes.md`.
- [ ] Update onboarding docs (`docs/AGENT_ONBOARDING_PLAYBOOK.md`) with UI usage instructions.
- [ ] Plan staged rollout (internal alpha ¡÷ engineering beta ¡÷ full team).
- [ ] Monitor post-launch metrics (run success rate via UI, mean time to diagnose errors).

## Deliverables Checklist
| Deliverable | Owner | Target | Notes |
|-------------|-------|--------|-------|
| `services/mvp_runner.py` + tests | Backend | Week 1 | Exposes orchestration API |
| API contract doc | Backend | Week 1 | Includes example payloads |
| User flow diagrams | UX | Week 1 | Stored in `docs/ui_flows/` |
| Wireframes (lo-fi) | UX | Week 2 | Export PNG + source |
| Component spec doc | Frontend | Week 2 | Props table & data mapping |
| Mock-data prototype | Frontend | Week 3 | Validates layout w/o backend |
| Integrated UI build | Frontend + Backend | Week 4 | Feature-flagged |
| Usability findings doc | UX | Week 4 | Drives iteration |

## Dependencies & Risks
- **OpenAI access** ¡V Need stable creds or mocks; mitigate by adding dependency injection for API clients.
- **GenCase execution** ¡V Ensure sandbox/workdir permissions; provide "preview-only" mode when execution blocked.
- **Data volume** ¡V Large reference files may slow UI; plan pagination or lazy-loading.
- **Resource bandwidth** ¡V Multi-team coordination required; schedule weekly sync to unblock tasks.

## Next Immediate Actions
1. Draft `services/mvp_runner.py` skeleton and align on response dataclasses.
2. Schedule workshop to walk stakeholders through proposed user flows and gather requirements gaps.
3. Create shared document repository (`docs/ui_preparation/`) for artifacts produced by each workstream.
