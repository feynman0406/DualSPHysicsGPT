# DualSPHysicsGPT MVP Work Record

## MVP Status
- Branch: experiment-s0-vectors-to-schema
- Local modifications when the MVP succeeded: chains/json_normalizer.py, docs/auto_xml_schema.md, schemas/dualsphysics_config_schema.json, scripts/mvp_direct_file_search.py
- MVP run artifacts saved in logs/mvp/ (agent1_output.json, agent2_config.json, generated_case.xml)

## End-to-End Workflow
**Stage 0 - Retrieval framing**
- scripts/mvp_direct_file_search.py:386 creates the Agent 1 prompt and enables OpenAI file_search, seeding the conversation with the user query and guardrails about evaluating every candidate reference.

**Stage 1 - Agent 1 (Reference Finder)**
- Agent 1 analyzes file search hits, reranks them by how they appear in the analysis, and captures lightweight metadata plus guidance in logs/mvp/agent1_output.json (scripts/mvp_direct_file_search.py:386).
- _reorder_sources_by_analysis_text gives LLM reasoning priority over raw retrieval scores so the instructions stay semantically grounded (scripts/mvp_direct_file_search.py:325).

**Stage 2 - Agent 2 (Config Generator)**
- scripts/mvp_direct_file_search.py:510 loads the local JSON references returned by Agent 1, persists the full payload to logs/mvp/agent2_input.json, and builds the structured prompt.
- The OpenAI call uses the project schema with strict mode disabled to allow legitimate variability while still validating shape (scripts/mvp_direct_file_search.py:626).
- A fixed-section diff check guards constants, mkconfig, and geometry.definition, retrying the call up to three times if the LLM drifts from the reference template (scripts/mvp_direct_file_search.py:638).

**Stage 3 - JSON normalization and XML generation**
- Agent 2's JSON is normalized into the canonical format via normalize_case_config before any XML is produced (chains/json_normalizer.py:41).
- The normalizer accepts loose inputs (aliases like constantsdef, mixed vector shapes) and issues warnings rather than failing whenever possible (chains/json_normalizer.py:66).
- generate_xml_and_execute then calls generate_case_xml, which validates the structure before serializing XML (scripts/mvp_direct_file_search.py:703, AutoXml_script/generate_xml.py:1177).

**Stage 4 - Optional GenCase execution**
- When --execute is supplied, generate_xml_and_execute invokes tools.exec.run_gencase to test the XML end-to-end, capturing outputs in logs/mvp/case_out/ (scripts/mvp_direct_file_search.py:727).

## Key Design Choices
- **Two-agent handshake**: Agent 1 performs semantic vetting over the raw retrieval scores so Agent 2 starts from a vetted, instruction-rich template. This separation keeps the second prompt compact and focused.
- **Reference resolution**: The MVP resolves file paths locally to avoid large context windows and make debugging reproducible (scripts/mvp_direct_file_search.py:135).
- **Instruction alignment**: The Agent 2 prompt insists on silently reconciling user intent and Agent 1 guidance before editing, reducing contradictory edits.
- **Semi-strict schema**: We set strict:false in the response format after discovering that real DualSPHysics cases contain optional blocks and naming variations that the strict schema rejected. The diff guardrails keep high-value sections locked even with relaxed validation.
- **Synonym heuristics**: Token maps for constants and geometry terms help spot when the user explicitly requests changes, allowing Agent 2 to permit only those edits in fixed sections (scripts/mvp_direct_file_search.py:179).
- **Progressive hardening**: The JSON normalizer backfills missing canonical keys, normalizes vectors, and synthesizes execution parameter plans so the downstream XML generator stays deterministic (chains/json_normalizer.py:41).

## Validation & Tooling
- docs/MVP_USAGE.md documents CLI-driven verification, including pausing after Agent 1 for manual review.
- tests/test_agent2_reference_loading.py exercises reference resolution edge cases to ensure truncated excerpts still resolve for Agent 2.
- tests/test_generate_xml.py keeps the generator honest by round-tripping known-good configs through the XML serializer.
- logs/mvp/agent2_fixed_section_diff.json captures any diff violations for rapid debugging when Agent 2 retries.

## Lessons & Next Steps
- Strict JSON schema enforcement proved too brittle for the diversity of DualSPHysics templates, so we now lean on semantic guardrails plus normalization.
- The current workflow lacks an automated retry path for poor Agent 1 retrievals; a light feedback loop (for example, alternative rerank strategies) would improve recall.
- Metrics and telemetry are still manual, so wiring the MVP into metrics/plan_runs.csv would surface coverage and failure modes over time.
- Future work: integrate the MVP guardrails into the production planner chain, add automated GenCase smoke tests, and broaden schema allowances for motion and floating blocks.
