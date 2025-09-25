# DualSPHysicsGPT ?V To?Do Roadmap

Purpose: keep generator the only XML producer, use fixer for clear guidance, and make runs observable, recoverable, and easy to review.

## 0) Current State (quick snapshot)
- Generator (`chains/generator.py`) produces XML; temporary debug prints are enabled to show messages/raw_out/extracted XML.
- Exec runner (`tools/exec.py`): headless mode runs under `<BASE>/<CASE_NAME>` where `BASE = DSPH_WORKDIR or cwd`; creates `<CASE_NAME>_out` and returns absolute `workdir`.
- Fixer (`chains/fixer.py`) outputs a textual fix plan (root cause + actionable edits), not XML.
- Controller (`controller/loop.py`):
  - On failure, captures `stderr` with fallback to `stdout` (first 4000 chars), stores diagnostics + fixer suggestion, and regenerates via generator using a composed prompt.
  - Review reject path mirrors the same: fixer ?? generator ?? rerun.

## 1) Short?Term Stabilization (1?V2 days)
- Diagnostics
  - [x] Always persist full `stdout` and `stderr` into artifacts (see ??4) in addition to the 4k excerpt used for prompts.
  - [x] Normalize stage detection across all run modes (`headless`, `existing_bat`, `direct_exec`) and expose `stage` consistently.
  - [ ] Improve GenCase failure parsing (e.g., capture lines following ??Execution aborted.?? into diagnostics).
- Exec runner
  - [x] Ensure `_run_direct_exec()` uses the same `BASE/CASE_NAME` working dir policy as headless to avoid Temp output.
  - [ ] Re?verify path quoting on Windows; ensure spaces in paths are quoted for all binaries.
- Generator/Fixer prompts
  - [x] Existing `prompts/fixer_system_prompt.md` and `prompts/generator_system_prompt.md` provide the structured guidance (reviewed \& linked).
  - [x] Gate generator??s noisy debug prints behind `DSPH_DEBUG=1` (or a logger) to keep normal runs clean.

## 2) CLI (first pass)
- Commands
  - [ ] `dsph run "<request>"` ?? starts a session, streams progress, prints `workdir` and artifacts path.
  - [ ] `dsph review <session_id> accept|reject [--feedback "..."]` ?? accepts or loops with feedback.
  - [ ] `dsph show <session_id>` ?? prints last XML, diagnostics excerpt, fix plan, and artifacts dir.
  - [ ] `dsph check` ?? validates `DSPH_BIN_DIR`, binaries presence, GPU availability.
- Flags
  - [ ] `--max-iters`, `--gpu`, `--bin <DSPH_BIN_DIR>`, `--workdir <path>`, `--use-existing-batch <bat>`, `--validate-only`.

## 3) API (optional)
- [ ] POST `/sessions` ?? `{ session_id, status }`.
- [ ] GET `/sessions/:id` ?? `{ last_xml, diagnostics, fix_suggestion, history, workdir }`.
- [ ] POST `/sessions/:id/review` ?? `{ status }`.
- [ ] SSE/WS for streaming generator + solver logs (optional).

## 4) Session Artifacts (on disk)
Create `sessions/<session_id>/` with:
- [x] `request.txt` ?V original user request.
- [x] `last_xml.xml` ?V latest XML.
- [x] `fix_plan.md` ?V latest fixer output.
- [x] `diagnostics.txt` ?V full stdout + stderr of last run.
- [x] `history.json` ?V append?only records of XMLs, results, diagnostics excerpts, and fix plans.
- [x] `workdir.txt` ?V absolute path to solver workdir.
Wire these writes into `controller/loop.py` after each iteration.

## 5) Run Modes & Safety
- [ ] `validate-only` mode: execute GenCase only to catch XML issues faster.
- [ ] Auto?cleanup option for `<CASE_NAME>_out` controlled by `DSPH_AUTODELETE_OUT` (already respected by bat). Document behavior.

## 6) Fix Plan Format (produced by fixer)
Recommend a structured, model?friendly layout (pure text or light YAML; no XML):
- [ ] [Root Cause]
- [ ] [Required Changes] (bullets)
- [ ] [Concrete Edits] (by XML path or tag names; include sample attribute updates)
- [ ] [Validation Criteria] (what should succeed on next run)
Have generator explicitly ingest a ??[Fix Suggestions]?? section.

## 7) Prompt Refinements
- [ ] Generator: accept sections ?V [Original Request], [Previous XML], [Fix Suggestions], [References]. Enforce ??output only a single <case>...</case>??.
- [ ] Fixer: emphasize ??no XML output?? and require actionable, minimal edits.
- [ ] Add small examples in both prompts for common errors (e.g., missing `case.casedef.constantsdef`).

## 8) Observability & Logging
- [ ] Replace ad?hoc prints with a logger; respect `DSPH_DEBUG` to toggle verbose dumps (lc_messages/raw_out/extracted XML).
- [ ] Print a one?line progress summary per iteration: stage, status, workdir, artifacts dir.

## 9) Windows / Batch Robustness
- [ ] Ensure codepage UTF?8 in headless bat (`chcp 65001 > nul`) if non?ASCII file names are expected.
- [ ] Normalize path separators in bat inputs; keep quotes around paths.

## 10) Testing Plan
- [ ] Unit: prompt assembly (generator/fixer), diagnostics merging, session persistence utilities.
- [ ] System: point to a real `DSPH_BIN_DIR` and run a small case (validate?only ?? full run; CPU/GPU variants).

## 11) Documentation
- [ ] README quickstart: env setup, `DSPH_BIN_DIR`, `DSPH_WORKDIR`, `USE_BATCH` vs `USE_EXISTING_BATCH`.
- [ ] CLI usage examples and screenshots.
- [ ] Troubleshooting: ??Execution aborted.?? with GenCase error lines; how to read `diagnostics.txt`.

## 12) Nice?to?haves
- [ ] Diff view between iterations for XML.
- [ ] Zip/download artifacts per session.
- [ ] Template library of common cases (e.g., dambreak).
- [ ] i18n toggle for prompts/UI (zh/EN).
---
Tracking tips:
- Use issue labels: `exec`, `diag`, `cli`, `api`, `prompts`, `docs`, `testing`.
- Start with ??1, ??4, ??6, ??7; then add ??2 CLI skeleton. This yields an end-to-end useful loop quickly.

## Implementation Plan (next steps)

### Milestone 1 ?V Stabilize Core Loop
- [x] Normalize stage detection across _run_headless_bat, _run_existing_bat, and _run_direct_exec() so controller logging sees consistent stage values.

### Milestone 2 ?V Prompts & Guidance
- [x] Use the existing system prompts (prompts/generator_system_prompt.md, prompts/fixer_system_prompt.md) for structured guidance.
- [x] Point generator/fixer chains at those prompts via .env so [Fix Suggestions] flow through regeneration.

### Milestone 3 ?V Developer Ergonomics
- [ ] Implement the CLI surface (dsph run/review/show/check) with shared flag parsing and controller wiring.

### Milestone 4 ?V Future Project Readiness
- [ ] Define staged run contracts (gencase|solver|post|all) and extend exec returns with artifact listings for the controller.
- [ ] Prototype the geometry-first flow (GenCase-only pass, user confirmation) through controller + CLI.
- [ ] Draft README quickstart/troubleshooting that highlights new session artifacts and stage options.
## Future Goals (Next Project)
- Communicator/orchestrator agent that interacts with the user and calls tools:
  - XML generator (only source of XML)
  - XML fixer (outputs structured fix plans, no XML)
  - DualSPHysics exec with stage control: gencase-only, solver-only, post-only, or full batch
- Geometry?first flow:
  - Generate Case_Def.xml ?? run GenCase only ?? report success and artifact path for geometry inspection
  - Ask whether to proceed to solver/post or revise geometry/algorithms
- Stage flags and contracts:
  - Introduce run_stage = gencase|solver|post|all (defaults to all)
  - Uniform exec return: status, stage, workdir, stdout/stderr, and detected artifacts
- UI/UX ideas:
  - Later integrate ParaView or a lightweight preview (optional; non?blocking for core pipeline)
- Testing:













## 13) RAG Enablement
- [x] Env loading refactor: ensure `.env` (or CLI-provided env files) are read before `chains.generator` / `chains.fixer` import their flags; consider lazy reads or `reload_use_rag()` helper shared by CLI + API.
- [x] Index build workflow: validate corpora under `data/`; add guard rails in `rag/build_indices.py` for missing keys, plus document a `python rag/build_indices.py ...` command (Make/CLI alias) that writes to `rag/indexes/`.
- [x] Retrieval hardening: enrich `rag/retrievers.py` with logging when indexes missing, allow configurable `k` + alternative embedding provider, and expose a CLI flag/env to switch providers.
- [ ] Prompt integration: confirm generator/fixer chains truncate/contextualize retrieved docs deterministically; surface toggles via `.env` + CLI flags.
- [x] Docs & ops: update `.env` comments, README/to_do checklist with RAG prerequisites, and provide runbook for refreshing indexes & troubleshooting missing artifacts.




