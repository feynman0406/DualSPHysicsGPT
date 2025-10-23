# DualSPHysicsGPT MVP Working Record

## MVP Snapshot
- Branch: experiment-s0-vectors-to-schema
- MVP run artifacts: `logs/mvp/agent1_output.json`, `logs/mvp/agent2_config.json`, `logs/mvp/generated_case.xml`
- Core entry points: `scripts/mvp_direct_file_search.py`, `rag/openai_file_search.py`, `chains/json_normalizer.py`, `AutoXml_script/generate_xml.py`

## Architecture Overview
- **Stage 0 - Query prep**: `rag/openai_file_search.py:360` tokenizes the raw request into MUST/SHOULD lists, appends the untouched query, and injects a retrieval hint so file-search always sees the original wording alongside structured cues (dimensionality, mDBC, etc.).
- **Stage 1 - Reference finder**: `scripts/mvp_direct_file_search.py:369` prompts Agent 1 with OpenAI file_search. The tool fetches up to 15 candidates per vector store, Agent 1 inspects each snippet, keeps only semantically correct templates, and emits adaptation notes in `logs/mvp/agent1_output.json`. `_reorder_sources_by_analysis_text` then re-ranks by the agent's reasoning so downstream prompts stay grounded.
- **Stage 2 - Config generator**: `scripts/mvp_direct_file_search.py:510` packages Agent 1's survivors into a compact prompt for Agent 2. The response format uses the DualSPHysics schema with `strict:false`, letting the LLM flex optional blocks while diff guardrails protect constants, mkconfig, and geometry. Conflicts between user intent and Agent 1 guidance are reconciled silently before edits are applied.
- **Stage 3 - Normalization**: `chains/json_normalizer.py:41` harmonizes aliases, vector shapes, gauge fingerprints, and execution defaults so every config matches the canonical layout the XML generator expects.
- **Stage 4 - XML generation and optional GenCase**: `scripts/mvp_direct_file_search.py:703` calls `AutoXml_script/generate_xml.py:1177` to materialize XML. When `--execute` is used, `tools/exec.py` runs GenCase and saves outputs under `logs/mvp/case_out/` for inspection.

## Key Design Decisions
- Two-agent handshake keeps retrieval vetting (Agent 1) separate from schema-constrained synthesis (Agent 2), reducing prompt bloat and forcing an explicit instruction pass (`scripts/mvp_direct_file_search.py:458`).
- Query rewriting stays additive: the raw user text is preserved, preventing tool hallucinations and helping niche terms like mDBC survive preprocessing.
- Schema enforcement shifted from strict JSON validation to loose mode plus targeted diff checks after real cases revealed high structural variance (`scripts/mvp_direct_file_search.py:638`, `schemas/dualsphysics_config_schema.json`).
- Normalizer favors repair over rejection, emitting warnings when it fills missing vectors or renames legacy keys so the pipeline remains resilient during exploration.
- Geometry normals now mandate `norgeometry.svshapes`; the generator backfills `{ "v": true }` and a standard debug comment when legacy templates omit it so schema validation and GenCase exports stay aligned.

## Retrieval Debugging Log (mDBC dam-break)
- Raw file-search with "generate a 3D dambreak mdbc xml file" surfaces `CaseDamBreak3D_mDBC_Def.json` immediately, but the MVP hint "MUST: dambreak, mdbc, 3D" still allows non-mDBC files to outrank it because the vector score dominates once results are truncated at `_DEFAULT_SEARCH_LIMIT = 15` (`rag/openai_file_search.py:29`).
- The metadata filter today is purely textual; `CaseDamBreak3D_mDBC_Def.json` lacks a dedicated metadata key, so the filter cannot force inclusion. MUST tokens live only in the query string, not a hard filter.
- Recommended mitigations:
  1. Increase `max_num_results` to 25 when MUST contains niche terms (`rag/openai_file_search.py:406`).
  2. Post-process search results to bubble filenames whose `source_path` contains "mdbc" ahead of equal-score items before handing them to Agent 1.
  3. Extend ingestion metadata so mDBC templates carry an explicit tag, unlocking true metadata filtering.
- Interim verification lives in `logs/last_run/sources.json`, and `search_query_test.py` reproduces raw vs. MVP queries side-by-side for regression tracking.

## Tooling and Validation
- `tests/test_agent2_reference_loading.py` guards against missing reference payloads and truncated snippets.
- `tests/test_json_normalizer.py` and `tests/test_generator_json_pipeline.py` cover the normalization flow and XML conversion.
- `scripts/regenerate_config_library.py` refreshes local exemplars and re-syncs checksums consumed by the vector store ingestion helpers.
- `roundtrip_report.md` documents XML->JSON->XML checks, while `TEST_MVP.md` captures the manual smoke-playbook followed during the successful run.

## Lessons Learned and Next Steps
- Retrieval must treat specialist keywords (mDBC, HR/NS variants) as scarcity signals; relaxing schema is not enough without higher-recall search.
- Add automated rerank metrics so we can compare raw vs. hint-driven searches and detect when important templates fall below the cutoff.
- Wire MVP runs into lightweight telemetry (for example append outcomes to `metrics/plan_runs.csv`) and gate new prompt changes with the regression tests above.
- Future work: implement metadata tagging during ingestion, broaden normalization to cover commands.list children, and automate GenCase smoke runs for high-value scenarios.
