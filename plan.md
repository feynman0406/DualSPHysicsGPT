DualSPHysics Pipeline Stabilization Plan

Objectives
- Unblock report_runs_* by ensuring regenerated XML is written to the expected directory.
- Preserve fluid geometry in regenerated/round‑trip cases to avoid “no fluid particles” warnings.
- Package required auxiliary files (e.g., SloshingMotionData.dat) alongside generated cases.
- Add guardrails in the JSON→XML path to catch/normalize common schema pitfalls.
- Provide simple commands to re‑generate, run, and validate parity vs. official XML.

Workstream 1 — Output Paths
- Update scripts/smoke_test_configs.py default --output-dir to AutoXml_script/generated_cases_direct.
- Keep CLI override; write a summary JSON via --results by default when output-dir is generated_cases_direct.
- Acceptance: running the smoke script produces XML files under AutoXml_script/generated_cases_direct with names <ConfigStem>.xml.

Workstream 2 — Preserve Fluid Geometry
- Ensure geometry.mainlist retains setmkfluid + fill/draw commands through normalization.
- Add validation (already present in generate_xml.validate_case_tree) to fail early when setmkfluid exists without a subsequent fill*/draw*.
- Extend json_normalizer to promote simple “objects: [{type: fluid|bound, ...}]” into commands when mainlist is absent (already supported); add tests for fluid presence.
- Acceptance: JSON fixtures for dam‑break (2D/3D) normalize to XML that passes validate_case_tree and GenCase without missing‑fluid warnings (except known baseline tank case).

Workstream 3 — Motion/Data File Handling
- In tools/exec.run_dualsphysics: copy known auxiliary files referenced by cases into the working directory before invoking GenCase.
  - Start with AutoXml_script/SloshingMotionData.dat and any *.dat detected in the XML text.
  - Optional env flag DSPH_COPY_DATA=0 to disable.
- Acceptance: Sloshing cases run without “File 'SloshingMotionData.dat' not found to copy.” warnings.

Workstream 4 — JSON Schema Guardrails
- Normalize vectors: when a node expects a vector (e.g., point/size), coerce scalars to attributes and warn on missing axes; fill missing axes with 0.0 when safe.
- Parameters: allow dict/list; merge extra attributes into parameter nodes (already supported); add round‑trip tests.
- Constants: allow attribute‑style and node‑spec styles; preserve _units/_comment; add tests for vector constants.
- Acceptance: tests/test_json_normalizer.py extended to cover vector coercion and required‑axis warnings.

Workstream 5 — Template/Predefinition Hygiene
- Keep sanitize_newvarcte (name/value→attribute) in chains/generator; add optional config‑driven sanitizer if future rules are needed.
- For template‑based generation (GenCase_CaseTemplate.xml flows), ensure required constants (e.g., Dp) are injected from geometry.definition.dp if missing.
- Acceptance: template workflows don’t error on “The variable 'Dp' does not exist.”

Workstream 6 — CLI and Docs
- README and docs/gen_case_test_report.md: add a Re‑run section using scripts/smoke_test_configs.py with generated_cases_direct.
- Document new env flags: DSPH_COPY_DATA, DSPH_WORKDIR, DSPH_BIN_DIR.
- Acceptance: a new “Regenerate & Run” snippet reproducibly rebuilds and runs the matrix.

Workstream 7 — Tests & Matrix
- tests/test_official_xml_cases.py: keep as‑is to guard official XML execution.
- Add tests that build a minimal fluid + bound geometry via JSON and assert no validator errors.
- Optional slow tests to run executive path via tools/exec (skipped unless DSPH_BIN_DIR is set).
- Acceptance: CI passes unit tests; slow tests are opt‑in.

Milestones
- M0 (today):
  - Switch smoke_test default output dir to generated_cases_direct.
  - Add DSPH_COPY_DATA handling and copy SloshingMotionData.dat.
  - Update README quick commands; re‑run a subset locally.
- M1: Extend json_normalizer vector/axis guardrails; add tests for fluid preservation and parameters.
- M2: Add optional sanitizer config and template constant injection; broaden test matrix.

Immediate Next Actions
- Implement Workstream 1 (output dir) and Workstream 3 (data copy) since they unblock runs and are low risk.
- Re‑generate XML via scripts/smoke_test_configs.py with --skip-solver and verify files land in AutoXml_script/generated_cases_direct.
- Run a sloshing case through tools/exec.run_dualsphysics to confirm copy logic removes the dat‑file warnings.

Roll‑Back Plan
- All changes are localized; retain CLI flags to revert behaviors (output dir override, DSPH_COPY_DATA=0).
