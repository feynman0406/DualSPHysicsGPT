DualSPHysics Pipeline Stabilization Plan

Objectives
- Ensure regenerated XML lands in the expected workspace so automated GenCase runs succeed.
- Preserve fluid geometry in regenerated and round-trip cases to eliminate "no fluid particles" warnings.
- Package auxiliary data files alongside generated cases to keep solver runs warning-free.
- Harden the JSON-to-XML toolchain with schema guardrails and validation checkpoints.
- Provide simple commands to regenerate cases, compare against official XML, and capture results.

Workstream 1 ? Output Paths
- Update scripts/smoke_test_configs.py default --output-dir to AutoXml_script/generated_cases_direct.
- When the default output dir is used, always emit a summary JSON via --results.
- Acceptance: invoking the smoke script with no overrides creates AutoXml_script/generated_cases_direct/<ConfigStem>.xml and writes results.json in the same folder.

Workstream 2 ? Preserve Fluid Geometry
- Extend generate_xml.validate_case_tree to require a fill/draw command immediately after each setmkfluid, except for known boundary-only templates captured in an explicit allowlist.
- Add regression tests that exercise geometry.commands conversions (objects -> commands) and confirm fluid fill preservation across normalization.
- Acceptance: dam-break JSON fixtures (2D/3D) pass validation and GenCase without fluid-missing warnings; boundary-only templates remain allowed.

Workstream 3 ? Motion/Data File Handling
- In tools/exec.run_dualsphysics gather required data assets before execution by parsing the XML for <copy> nodes and *.dat file attributes via ElementTree (no regex).
- Copy known resources from AutoXml_script/ (starting with SloshingMotionData.dat) into the solver workspace; log a warning and continue when a source file is missing unless DSPH_COPY_DATA=strict.
- Introduce DSPH_COPY_DATA env flag with values: off (skip copies), warn (default), strict (treat missing files as errors).
- Acceptance: sloshing cases run without "File 'SloshingMotionData.dat' not found" warnings under default settings.

Workstream 4 ? JSON Schema Guardrails
- Teach chains/json_normalizer vector helpers to ensure x/y/z attributes exist; fill missing axes with 0.0 only when an explicit allow_zero_axes flag is set, otherwise raise a validation error.
- Record guardrail decisions in warnings returned to the controller and cover them with tests/test_json_normalizer.py.
- Acceptance: normalization emits deterministic vectors, surfaces missing-axis errors in tests, and continues to support current fixtures.

Workstream 5 ? Template and Predefinition Hygiene
- Maintain sanitize_newvarcte in chains/generator; expose an optional sanitizer config at configs/sanitizer.yaml consumed by chains/generator.build_sanitizer_from_config.
- Ensure template-driven generation (GenCase_CaseTemplate.xml) injects required constants such as Dp using geometry.definition.dp defaults before writing XML.
- Acceptance: template workflows no longer produce "The variable 'Dp' does not exist" and sanitizer rules can be toggled via config file changes alone.

Workstream 6 ? CLI and Docs
- README.md: add a "Regenerate and Run" section demonstrating scripts/smoke_test_configs.py and the new DSPH_COPY_DATA behavior.
- docs/gen_case_test_report.md: add a rerun checklist referencing the smoke script and results.json output.
- Acceptance: documentation references match actual command syntax and highlight the new environment flags.

Workstream 7 ? Tests and Matrix
- Keep tests/test_official_xml_cases.py guarding official XML execution.
- Add targeted unit tests that build minimal fluid + boundary geometry via JSON and assert validate_case_tree success.
- Optionally gate full solver integration tests behind DSPH_BIN_DIR to avoid CI failures.
- Acceptance: CI runs unit tests successfully and optional slow tests are skipped when binaries are absent.

Milestones
- M0 (today): implement Workstream 1 and Workstream 3, update README quick commands, and rerun a smoke subset.
- M1: deliver Workstream 2 and Workstream 4 guardrails with corresponding tests.
- M2: complete Workstream 5 sanitizer config, documentation updates, and broaden the test matrix.

Immediate Next Actions
- Implement Workstream 1 (default paths + results output) and guard Workstream 3 (data copy flag + SloshingMotionData support).
- Re-run scripts/smoke_test_configs.py --skip-solver and confirm artifacts under AutoXml_script/generated_cases_direct with results.json.
- Execute a representative sloshing case through tools/exec.run_dualsphysics to verify data copy behavior.

Rollback Plan
- All changes remain behind environment flags or command overrides (output-dir override, DSPH_COPY_DATA modes), making reversion low-risk.
