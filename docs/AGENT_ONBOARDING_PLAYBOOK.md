# DualSPHysicsGPT - Future Agent Onboarding Playbook

This playbook captures the working knowledge a future agent needs to extend the project safely. Update it whenever workflows, dependencies, or conventions change.

---

## 1. Project Snapshot
- Goal: Produce and iterate DualSPHysics `Case_Def.xml` files from natural-language requests using LLM reasoning, retrieval, schema enforcement, and solver feedback loops.
- Architecture highlights:
  - Controller (`controller/loop.py`) runs generator -> execution -> fixer cycles until success, user review, or `MAX_ITERS`.
  - AutoXml subsystem (`AutoXml_script/`) translates normalized JSON configs into DualSPHysics-compliant XML and supports round-trip validation.
  - Retrieval stack (FAISS/BM25 or OpenAI File Search) feeds design and error corpora into prompts.
  - Planning + Schema agents (`agents/`) curate examples, build plan JSON, and request strict schema outputs before XML generation.
  - Execution harness (`tools/exec.py`) prepares workspaces, copies assets, and invokes the DualSPHysics toolchain.

---

## 2. Prerequisites and Environment
1. Python: 3.10+ recommended; work inside a dedicated virtual environment.
2. Dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Environment variables (prefer a `.env` in the repo root):
   - Core LLM access: `LLM_PROVIDER`, `OPENAI_MODEL`, `OPENAI_API_KEY`.
   - Retrieval toggles: `USE_RAG`, `USE_OPENAI_FILE_SEARCH`, `IDX_DIR`, `TOP_K`, `EMBEDDING_PROVIDER`.
   - Vector store IDs when using File Search: `OPENAI_RAG_VS_DESIGN_ID`, `OPENAI_RAG_VS_ERROR_ID`.
   - Execution options: `DSPH_BIN_DIR`, `DSPH_WORKDIR`, `DSPH_USE_GPU`, `DSPH_COPY_DATA` (`off|warn|strict`).
   - Two-stage pipeline: `USE_TWO_STAGE_RAG_SCHEMA`, `USE_RAG_PLANNING_AGENT`.
4. DualSPHysics binaries: keep the official executables in `bin/windows/` or point `DSPH_BIN_DIR` at your installation. Validate with `python -m cli.dsph check --bin path/to/bin`.
5. Corpora (recommended):
   - Populate `data/design_corpus` and `data/error_corpus` with reference XML, logs, and fixes.
   - Refresh local indexes (`python rag/build_indices.py ...`) or run ingestion scripts (`scripts/ingest_design_corpus.py`, `scripts/ingest_error.py`) for OpenAI vector stores.

---

## 3. Repository Map
- `cli/`
  - `dsph.py`: CLI entry-point with `run`, `review`, `show`, `rag`, `check` commands.
- `controller/`
  - `loop.py`: session lifecycle, iteration loop, retrieval freeze logic, user review handling.
- `chains/`
  - `generator.py`: orchestrates planning/schema agents, normalization, AutoXml conversion, and RAG integration.
  - `fixer.py`: builds textual remediation plans from diagnostics and references.
  - Helpers: `json_normalizer.py`, `mdbc_normals.py`, `rag_utils.py`.
- `agents/`: planning, schema, scoring, validation, logging utilities, configuration (`agents/config.py`).
- `AutoXml_script/`: XML generator, config library, DualSPHysics reference snippets, round-trip tools.
- `rag/`: local index builder, OpenAI File Search glue, retriever factories, `vector_stores.json` state.
- `tools/`
  - `exec.py`: solver harness, asset discovery, copy policies, GPU checks.
- `sessions/`
  - `store.py`: persistent artifacts (`request.txt`, `last_xml.xml`, `fix_plan.md`, `history.json`, etc.).
- `docs/`: specifications and prior work (schema guides, planning plans, quick references).
- `scripts/`: operational helpers for ingestion, smoke tests, evaluations, config regeneration.
- `tests/`: pytest coverage spanning AutoXml, chains, planning agent, controller, and regression fixtures.

---

## 4. Core Runtime Flow
1. Entry: `python -m cli.dsph run "<request>"` loads `.env`, applies CLI overrides, and calls `controller.loop.run_pipeline`.
2. Generator phase:
   - When two-stage flags are on, Stage 1 (planning agent) emits plan JSON and Stage 2 (schema agent) requests strict config output using `schemas/dualsphysics_config_schema.json`.
   - JSON is normalized (`chains/json_normalizer.py`), normals enforced, and `AutoXml_script.generate_xml` produces XML.
   - Retrieved documents are persisted to `logs/last_run/` and `sessions/<id>/rag_sources.md`.
3. Execution phase: `tools.exec.run_dualsphysics` creates a workspace, stages assets, runs GenCase / solver / post tools, and captures stdout/stderr plus workspace metadata.
4. Fixer phase (on failures): `chains/fixer.py` digests diagnostics and prior XML to produce actionable guidance, optionally backed by error corpus retrieval.
5. Loop control: sources freeze after iteration one unless fixer signals unlock; session state persisted via `sessions.store` helpers.
6. Review: success pushes the session to `pending_review`; use `python -m cli.dsph review <session> accept|reject` to close or iterate with user feedback prompts.

---

## 5. Retrieval and Knowledge Management
- Local indexes: `python rag/build_indices.py --design_dir data/design_corpus --error_dir data/error_corpus --out_dir rag/indexes` builds FAISS and BM25 artifacts for offline mode.
- OpenAI File Search:
  - `scripts/ingest_design_corpus.py` sanitizes XML to JSON, uploads deltas, and updates `.env` plus `rag/vector_stores.json`.
  - `scripts/ingest_error.py` handles error corpus uploads with checksum-based delta detection.
  - Retrieval metadata lives in `logs/last_run/metadata.json` and `<agent>_sources.json`.
- Metadata filters: `chains/rag_utils.build_metadata_filter()` scopes retrieval using keywords inferred from the request and diagnostics.
- Source freezing: generator keeps first-iteration sources to stay deterministic; fixer regex rules decide when to unlock retrieval for later iterations.

---

## 6. Planning and Schema Agents
- Planning agent (`agents/planning_agent.py`) scores examples, extracts quotes, and emits plan JSON validated by `agents/plan_validator.py`.
- Schema agent (`agents/schema_agent.py`) consumes the plan, prompts the LLM with strict schema requirements, and returns structured configs.
- Settings live in `agents/config.py` with env vars such as `PLANNING_AGENT_MODE`, `PLANNING_MAX_CURATED_EXAMPLES`, `PLANNING_MAX_QUOTE_LENGTH`, and `PLANNING_SCHEMA_VERSION`.
- Observe runs via `logs/last_run/planning_plan.json` and `metrics/plan_runs.csv`.
- Fallback: when planning or schema stages fail, generator drops back to single-stage prompting; see `chains/generator.py` for control flow.

---

## 7. AutoXml Essentials
- `AutoXml_script/generate_xml.py` builds compliant XML from normalized configs; `validate_case_tree` guards structural integrity.
- Config templates in `AutoXml_script/config_library/` double as RAG seeds and regression fixtures.
- Schema documentation: `docs/json_schema.md`, plus the official DualSPHysics PDFs in `AutoXml_script/`.
- Round-trip tests: keep `tests/test_generator_json_pipeline.py` and `tests/test_xml_roundtrip.py` green whenever schema or generator logic changes.

---

## 8. Execution Layer and Assets
- `tools/exec.py` responsibilities:
  - Build per-run workspaces and optional reusable batch scripts (`USE_EXISTING_BATCH`, `DSPH_BATCH_PATH`).
  - Collect referenced assets by scanning XML for `.dat`, `.txt`, `.csv` and copy them according to `DSPH_COPY_DATA`.
  - Honour execution toggles (`RUN_GENCASE`, `RUN_SOLVER`, `RUN_POST`) for validation-only runs.
  - Return stdout, stderr, workdir, and warning metadata to the controller.
- GPU detection uses `nvidia-smi`; toggle via CLI `--gpu` or by setting `DSPH_USE_GPU=1`.

---

## 9. Interfaces and Automation
- CLI (`python -m cli.dsph`): supports flags such as `--env`, `--max-iters`, `--bin-dir`, `--workdir`, `--rag-index-dir`, `--rag-top-k`, `--validate-only`.
- FastAPI service (`api/main.py`): endpoints `/run`, `/review`, `/session/{id}`, `/status/{id}` for automation workflows.
- Windows batch helper: `run_headless.bat` demonstrates scripted CLI execution.

---

## 10. Testing and Validation Checklist
- Pytest focus areas:
  - AutoXml and normalization: `tests/test_generate_xml.py`, `tests/test_json_normalizer.py`, `tests/test_mdbc_normals.py`.
  - Retrieval and planning flags: `tests/test_rag_flags.py`, `tests/test_planning_phase1.py`.
  - Controller behaviour: `tests/test_generator_chain.py`, `tests/test_freeze_unlock.py`.
  - Regression fixtures: `tests/test_official_xml_cases.py`, `tests/test_xml_roundtrip.py`.
- Smoke scripts:
  - `python scripts/smoke_test_configs.py --skip-solver` (generate XML for the config library).
  - `python scripts/eval_rag.py --threshold 0.8` (recall audit for File Search).
- Manual review: check `sessions/<uuid>/` artifacts and `logs/last_run/` retrieval outputs after key changes.

---

## 11. Debugging and Observability
- Set `DSPH_DEBUG=1` to enable verbose logging for LLM calls and retriever decisions.
- Use `python -m cli.dsph show <session_id>` or `cli/watch_status.py` for quick inspection.
- Session folders include `status.json`, `history.json`, `diagnostics.txt`, `last_xml.xml`, and `fix_plan.md` for post-run analysis.

---

## 12. Common Implementation Recipes
1. Add corpus files:
   - Place new examples in `data/design_corpus` or `data/error_corpus`.
   - Rebuild indexes or rerun ingestion to keep retrieval aligned with the corpus.
2. Extend JSON schema:
   - Update `schemas/dualsphysics_config_schema.json`, adjust normalization and AutoXml mapping, and refresh docs/tests.
3. Tweak prompts:
   - Edit `prompts/generator_system_prompt.md` or `prompts/fixer_system_prompt.md`; keep placeholders in user rejection templates.
4. Adjust planning behaviour:
   - Modify `agents/example_scorer.py` or env defaults in `agents/config.py`; validate with `pytest tests/test_planning_phase1.py`.
5. Integrate new executables:
   - Extend `DUALSPHYSICS_BINARIES` in `tools/exec.py` and ensure asset handling covers the new tools.

---

## 13. Reference Index
- Quick start and RAG overview: `README.md`.
- Agent cheat sheet: `docs/AGENT_QUICK_REFERENCE.md`.
- Detailed specs: `docs/json_schema.md`, `docs/s2_rag_planning_agent.md`, `docs/two_stage_rag_schema_plan.md`.
- AutoXml deep dive: `AutoXml_script/README.md`.
- Execution harness notes: inline comments in `tools/exec.py`.

---

## 14. Maintenance Notes
- Preserve session artifacts unless intentionally cleaning; they are valuable debugging aids.
- Keep repository text files in UTF-8 and prefer ASCII characters unless upstream assets require otherwise.
- Update this playbook and related docs whenever workflows, dependencies, or contracts change.
- Outstanding areas: retry loops, richer metrics, and broader automated testing remain open for future work.

---

Last updated: 2025-01-17. Update this stamp when you revise the playbook.