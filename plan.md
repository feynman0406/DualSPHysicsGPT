# DualSPHysics Pipeline Stabilization & Expansion Plan (Updated)

## Goals (status)
1. [DONE] **Restore automated regeneration + execution**: Smoke tests now default to `AutoXml_script/generated_cases_direct/` and always emit `results.json`.
2. [WIP] **Guarantee fluid completeness**: Pending validator enhancements and regression tests.
3. [DONE] **Package auxiliary data**: Solver pipeline copies required `.dat`/`.txt`/`.csv` assets with configurable `DSPH_COPY_DATA` modes.
4. [WIP] **Harden JSON-to-XML guardrails**: Vector/attribute guardrails still outstanding.
5. [DONE] **Document and script workflows**: README and `gen_case_test_report.md` document the regeneration workflow, asset handling, and env flags.
6. [WIP] **Expand regression coverage**: Additional unit/integration tests remain to be added.
7. [WIP] **XML Roundtrip Fidelity**: Ensure XML -> JSON -> XML conversion is lossless.

## Workstreams & Deliverables

### [DONE] WS1 – Output Path & Artifact Discipline (Complete)
- `scripts/smoke_test_configs.py` now writes regenerated XML to `AutoXml_script/generated_cases_direct/` by default and persists `results.json`.
- Results capture solver metadata including warnings, asset usage, and workspace paths.

### [WIP] WS2 – Fluid Geometry Preservation (In Progress)
- TODO:
  - Extend `generate_xml.validate_case_tree` with `setmkfluid` → fill/draw enforcement and allowlisted boundary-only cases.
  - Add regression tests covering `geometry.objects` to `geometry.commands` conversion and fluid preservation.
- Acceptance: Dam-break fixtures validate/run without fluid warnings while boundary-only templates remain valid.

### [DONE] WS3 – Auxiliary Data Copy Pipeline (Complete)
- `tools/exec.run_dualsphysics` parses XML for data assets, copies them into the workspace, and surfaces warnings in result payloads.
- `DSPH_COPY_DATA` modes: `off`, `warn` (default), `strict`. Assets resolved from `AutoXml_script/`, project root, or `DSPH_ASSET_PATHS`.

### [WIP] WS4 – JSON Schema Guardrails (In Progress)
- TODO:
  - Update `chains/json_normalizer` to enforce x/y/z vectors with optional `allow_zero_axes`.
  - Emit guardrail warnings back to the controller and cover via `tests/test_json_normalizer.py`.
- Acceptance: Normalization emits deterministic vectors and fails fast on missing axes.

### [WIP] WS5 – Template & Sanitizer Hygiene (Not Started)
- TODO:
  - Maintain `sanitize_newvarcte` and load rules from `configs/sanitizer.yaml`.
  - Ensure template workflows inject required constants (e.g., `Dp`) before XML is emitted.
- Acceptance: Template runs avoid “The variable 'Dp' does not exist” and sanitizer toggles become config-driven.

### [DONE] WS6 – CLI & Documentation Updates (Complete)
- README “Regenerate and Run” section documents the smoke test workflow and `DSPH_COPY_DATA`.
- `docs/gen_case_test_report.md` now includes a rerun checklist referencing the smoke script and asset handling behavior.

### [WIP] WS7 – Test Matrix & Automation (In Progress)
- TODO:
  - Keep `tests/test_official_xml_cases.py` current and add new unit tests covering fluid + boundary cases and the asset pipeline.
  - Add optional gating for heavy solver tests via `DSPH_BIN_DIR`.
- Acceptance: CI runs fast tests, skips heavy ones without binaries, and catches validator regressions.

### [WIP] WS8 – XML Roundtrip Fidelity (Not Started)
- **Goal:** Ensure that converting an XML to JSON and back to XML preserves all structural and semantic information. The round-tripped XML should be functionally identical to the original, preventing data loss.
- **Tasks:**
  - **1. Create a Roundtrip Test Suite:**
    - Implement a new test script, `tests/test_xml_roundtrip.py`.
    - This script will iterate through all official `Case*.xml` files.
    - For each file, it will perform a full XML -> JSON -> XML conversion cycle in memory.
    - It will then structurally compare the original XML tree with the round-tripped one, logging any differences in tags, attributes, text, and comments. This test will initially fail and serve as our guide.

  - **2. Preserve XML Comments:**
    - **Analysis:** The standard `xml.etree.ElementTree` library does not preserve comments, which is a major source of information loss.
    - **Proposal:** Upgrade the XML parsing engine to `lxml`, which is the industry standard for robust XML handling in Python and fully supports comments.
    - **Action:**
      - Add `lxml` to `requirements.txt`.
      - Update `AutoXml_script/xml_to_json.py` to use `lxml.etree` for parsing, capturing comments.
      - Update `AutoXml_script/generate_xml.py` to use `lxml.etree` for serialization, writing comments back to the XML.

  - **3. Address Attribute Ordering:**
    - **Analysis:** Attribute order is not guaranteed, causing cosmetic differences that make comparison difficult.
    - **Action:** Modify `generate_xml.py` to sort attributes alphabetically before writing them to ensure deterministic, comparable output.

  - **4. Normalize Data and Formatting:**
    - **Analysis:** Minor differences in floating-point precision and tag formatting (e.g., `<tag/>` vs. `<tag></tag>`) can occur.
    - **Action:**
      - Standardize floating-point serialization to a fixed, high precision (e.g., 8 decimal places).
      - Configure the XML serializer to use a consistent style for tags and indentation.

- **Acceptance:** The `test_xml_roundtrip.py` suite passes for all official case files, proving that the conversion process is lossless and reliable.

## Milestones

- **M0 (Completed)**  
  - Delivered WS1, WS3, WS6.  
  - Updated documentation and rerun guidance.  
  - Regenerated smoke tests capture solver + asset metadata.

- **M1 (Next)**  
  - Deliver WS2 and WS4 guardrails with supporting unit tests.  
  - Verify fluid completeness and vector validation end-to-end.
  - Begin implementation of WS8.

- **M2 (Future)**  
  - Implement WS5 sanitizer config + template hygiene.  
  - Expand regression matrix per WS7 and tighten CI gating.
  - Complete and verify WS8.

## Immediate Next Actions
1. Implement `generate_xml.validate_case_tree` enhancements and add dam-break regression fixtures (WS2).
2. Upgrade `chains/json_normalizer` guardrails, return structured warnings, and cover with tests (WS4).
3. Add unit tests verifying asset copy metadata and fast failure paths; gate heavy solver tests with `DSPH_BIN_DIR` (WS7).
4. **Begin WS8 by creating the `tests/test_xml_roundtrip.py` test suite.**

## Rollback & Safety
- Behavioral changes remain behind CLI options or env flags (`--output-dir`, `DSPH_COPY_DATA`, `DSPH_ASSET_PATHS`), enabling quick rollback.
- Upcoming validator/test work (WS2/WS4/WS7/WS8) will introduce guardrails before merging risky changes.


--------------------------------------------------------------------------------
Auto XML Roundtrip Integration Plan (Detailed)

Objective
- Integrate the lossless XML ↔ JSON ↔ XML roundtrip into the DualSPHysicsGPT pipeline so agents can safely edit a JSON config without losing structure, order, or comments from official GenCase templates. Ensure roundtrip tests pass and generated XMLs are accepted by GenCase.

Scope
- Parser: AutoXml_script/xml_to_json.py
- Generator: AutoXml_script/generate_xml.py
- Pipeline: chains/*, controller/loop.py, cli/dsph.py, tools/exec.py
- Tests: tests/test_xml_roundtrip.py (+ related unit tests)
- Docs: README.md, docs/auto_xml_schema.md, docs/gen_case_test_report.md

What must be modified in this project

1) Dependencies and configuration
- requirements.txt: lxml>=5.0.0 is already present; keep pinned to avoid parser drift.
- Add env flag DSPH_ROUNDTRIP_STRICT (default 1) to fail pipelines when roundtrip validation detects differences (propagate to controller/cli).

2) Data model contract for JSON (what producers/LLM must emit)
- Top-level:
  - case_attributes: dict of attributes for <case>.
  - casedef_children: ordered plan of sections and generic nodes in <casedef> so comments/order can be reproduced.
- casedef sections:
  - constants: { name: scalar|string-preserved | vector{x,y,z} | generic-node }
  - mkconfig: attributes + orientations: [{type: 'xy'|'xz'|..., ...}] + extra generic nodes.
  - patterns: list of entries, each may include size/scale/gap/border vectors and children.
  - geometry:
    - predefinition: list of generic nodes or a generic node.
    - definition: preferred shape: {attributes: {...}, children: [generic nodes]}; must include dp and pointmin/pointmax children; numeric strings preserved as strings.
    - commands: preferred shape: {children: [list|mainlist|generic nodes]} in exact order. Legacy fallback: geometry.objects box -> converted into setmk* + fill/draw commands automatically.
- execution:
  - children_order: exact order of blocks under <execution>, e.g., ["parameters","special","extra_nodes"].
  - parameters: dict; optional parameters_order and parameters_children (to preserve comments and mixed entries).
  - special: accept normalized keys: active_absorption, passive_absorption, relaxation_zones, particle_filters; generator emits canonical XML tag names. Preserve order via special_children plan combining known sections and generic nodes.
  - gauges: each gauge supports start→point0, mid→point1 (optional), end→point2, plus arbitrary extras (e.g., pointdp) via children; preserve order with children_plan.
  - timeout: attributes + entries (tout) + children.

3) Wire parser/generator into the agent pipeline
- chains/generator.py:
  - When starting from an official XML template, parse with xml_to_json.parse_case_xml to get the canonical JSON schema for the LLM to edit.
  - Ensure the prompt/normalizer does NOT reorder lists when children_order, casedef_children, parameters_children, special_children, or gauges.children_plan are present.
  - Before running solver, call generate_xml.generate_case_xml; surface validate_case_tree errors as actionable feedback for the fixer chain.
- chains/fixer.py:
  - Accept validation errors from generate_case_xml/validate_case_tree; attempt minimal JSON edits to satisfy validator (e.g., ensure fluid fill after setmkfluid, dp and bounding box completeness).
- controller/loop.py:
  - Add a “roundtrip strict” gate: if DSPH_ROUNDTRIP_STRICT=1, abort run on generator validation failure with a structured error for the fixer to address. If 0, log warnings and continue.

4) JSON normalization changes
- chains/json_normalizer.py:
  - Preserve string forms for numeric-looking values; never coerce to float/int (1.20 must remain "1.20").
  - Enforce vectors only carry x/y/z keys; reject or warn on extras; allow_zero_axes optional.
  - Pass through generic nodes intact: keys like tag/name/type, attributes, children, vector, text, extra.
  - Respect provided order plans: do not sort parameters/special/gauges/commands if children_plan/children_order is present.
  - Backward-compatibility: accept legacy geometry.objects and map to current schema only if commands absent.

5) CLI additions
- cli/dsph.py:
  - New commands:
    - dsph xml-to-json <Case_Def.xml> -> prints/writes JSON using xml_to_json.
    - dsph json-to-xml --config config.json --output case.xml -> generate + validate via generate_xml.
  - run path:
    - If input is XML, transparently convert to JSON for the LLM, then generate XML for execution.
  - review/show:
    - Render and diff pre/post XML (pretty-printed) and show validator messages.

6) Validation/error handling
- Continue to use generate_xml.validate_case_tree. Treat as a blocker when DSPH_ROUNDTRIP_STRICT=1.
- Map errors to human-readable issues for the fixer chain:
  - Missing dp or domain points.
  - No fluid fill after setmkfluid.
  - mkconfig counts not covering used markers.
  - Missing mainlist under commands.

7) Testing
- Keep tests/test_xml_roundtrip.py as the primary acceptance test; ensure it passes locally:
  - pytest -q tests/test_xml_roundtrip.py
- Add/ensure unit tests:
  - tests/test_generate_xml.py: parameters with children; attribute-only parameters; list/dict handling in _build_section_list; special ordering via special_children.
  - tests/test_official_xml_cases.py: generator output accepted by GenCase (structure-only check when binaries unavailable).
  - tests/test_json_normalizer.py: verify order preservation and string formatting.
  - tests/test_predefinition_sanitizer.py: ensure generic nodes flow through unmodified.
- Smoke:
  - scripts/generate_roundtrip_cases.py produces AutoXml_script/generated_cases_roundtrip for manual diff.

8) Documentation
- README.md:
  - Add a “Roundtrip editing” section showing XML→JSON→XML workflow, and CLI examples.
- docs/auto_xml_schema.md:
  - Include examples for: parameters with children; special_children; gauges children_plan; commands children (list/mainlist/generic mixing).
- docs/gen_case_test_report.md:
  - Document how roundtrip outputs are regenerated and compared.

9) CI
- Add job to run pytest -q tests/test_xml_roundtrip.py.
- Optional: run scripts/generate_roundtrip_cases.py and upload artifacts; fail if diffs vs repo-committed exemplars are detected (when we decide to commit exemplars).

10) Migration and backward compatibility
- Legacy JSON still supported:
  - geometry.objects -> still accepted and converted to commands.
  - special legacy keys (activeabsorption etc.) accepted; emitted in canonical XML tag form.
- Provide a one-off conversion path:
  - Use dsph xml-to-json to migrate existing XMLs into the canonical JSON shape for agent editing.

Concrete code touch list (file → changes)

- chains/generator.py
  - Use xml_to_json.parse_case_xml for template ingestion.
  - Ensure produced JSON respects order plans if present; avoid sorting.
  - Call generate_xml.generate_case_xml prior to solver; on ValueError, surface details.

- chains/fixer.py
  - Parse generator errors; adjust JSON minimally (e.g., add mainlist, add fluid fill after setmkfluid, fix dp/pointmin/pointmax).

- chains/json_normalizer.py
  - Preserve string formatting; vectors x/y/z only; pass through generic nodes and order plans.

- controller/loop.py
  - Add DSPH_ROUNDTRIP_STRICT gate; route errors to fixer or abort.

- cli/dsph.py
  - New subcommands xml-to-json and json-to-xml; glue to parser/generator.

- README.md, docs/auto_xml_schema.md, docs/gen_case_test_report.md
  - Add sections/examples for the new workflow and schema shapes.

- tests/*
  - Keep/add the roundtrip and unit tests listed above.

Acceptance criteria
- tests/test_xml_roundtrip.py passes with zero failures on all official cases.
- scripts/generate_roundtrip_cases.py reproduces 21/21 official cases in AutoXml_script/generated_cases_roundtrip.
- No lossy formatting on numbers/booleans/strings (e.g., "1.20" remains "1.20"); comments and order preserved.
- Controller blocks on invalid cases when DSPH_ROUNDTRIP_STRICT=1; “review” flow shows diffs clearly.

Risks and mitigations
- Risk: LLM normalization reorders nodes or coerces numbers.
  - Mitigation: order plans enforced in json_normalizer; string preservation tests.
- Risk: Breaking legacy configs.
  - Mitigation: keep geometry.objects path; accept legacy special keys; add conversion CLI.
- Risk: Over-constraining <special> order.
  - Mitigation: prefer parser-provided special_children; fallback order only if plan is missing.

Timeline (suggested)
- Week 1: Wire parser/generator into chains and cli; add strict gate; docs update.
- Week 2: Finalize json_normalizer adjustments; add tests; enable CI job.
- Week 3: Expand smoke/regression coverage; optional exemplar diffs in CI; stabilize.

Runbook snippets
- Convert XML to JSON:
  python -m cli.dsph xml-to-json AutoXml_script/CaseDambreak_Def.xml > config.json
- Generate XML from JSON (with validation):
  python -m cli.dsph json-to-xml --config config.json --output AutoXml_script/case.xml
- Roundtrip test locally:
  pytest -q tests/test_xml_roundtrip.py
