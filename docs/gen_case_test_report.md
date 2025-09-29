# GenCase Test Report

## Environment
- GenCase v5.4.354.01 (07-04-2025) on Windows; all logs report `OmpThreads: 16`.
- Default DualSPHysics binaries loaded from `bin/windows` (`LoadDsphConfig> .../bin/windows/DsphConfig.xml`).
- Source XML cases live under `AutoXml_script/`; regenerated XML is expected under `AutoXml_script/generated_cases_direct/`.
- JSON library snapshots captured in `AutoXml_script/config_library/`.

## Reported Test Matrix (`report_runs_*`)
| Case | Input Source | Run Directory | Status | Warnings / Errors | Notes |
|------|--------------|---------------|--------|-------------------|-------|
| CaseDambreak_Def | Official XML (`AutoXml_script/CaseDambreak_Def.xml`) | `report_runs_CaseDambreak_Def_official/Case.out` | success | `*** WARNING: No fluid particles?`, `Automatic maximum depth is zero?`, `Constant B is zero.` | Baseline tank-only setup produces boundary particles only.
| CaseDambreak_Def | JSON?XML regeneration (expected `CaseDambreak_Def_from_official.xml`) | `report_runs_CaseDambreak_Def_regen/Case.out` | fail | `XML file was not found.` | Converter never wrote to `AutoXml_script/generated_cases_direct/`; path mismatch blocks run.
| CaseDambreakVal2D_Def | Official XML (`AutoXml_script/CaseDambreakVal2D_Def.xml`) | `report_runs_CaseDambreakVal2D_Def_official/Case.out` | success | none | Reference 2D dam-break passes without warnings.
| CaseDambreakVal2D_Def | JSON?XML regeneration | `report_runs_CaseDambreakVal2D_Def_regen/Case.out` | fail | `XML file was not found.` | Same missing-output issue as above.
| CaseDamBreak3D_Def | Official XML (`AutoXml_script/CaseDamBreak3D_Def.xml`) | `report_runs_CaseDamBreak3D_Def_official/Case.out` | success | none | Full 3D case with normals helper completes and writes normals summary.
| CaseDamBreak3D_Def | JSON?XML regeneration | `report_runs_CaseDamBreak3D_Def_regen/Case.out` | fail | `XML file was not found.` | Regenerated XML absent at lookup path.
| CaseSloshingHR_Def | JSON prompt output (`CaseSloshingHR_Def_from_xml.xml`) | `report_runs_CaseSloshingHR_Def_from_xml/Case.out` | fail | `XML file was not found.` | Script expected file in `AutoXml_script/generated_cases/`; generation step missing.

## Manual Official XML Runs
| Output Directory | Case | Status | Warnings / Errors | Notes |
|------------------|------|--------|-------------------|-------|
| `official_dambreak_out/CaseDambreak_Def.out` | CaseDambreak_Def | success | Same 3 warnings about missing fluid / depth / constant B | Direct run of author-supplied XML.
| `CaseDambreak_Def_official_out/CaseDambreak_Def.out` | CaseDambreak_Def | success | Same 3 warnings | Duplicate validation of official XML with copied outputs.
| `CaseDambreak_Def_test_out/CaseDambreak_Def.out` | CaseDambreak_Def | success | Same 3 warnings | Additional manual run for comparison.
| `official_dam2d_out/CaseDambreakVal2D.out` | CaseDambreakVal2D | success | none | Baseline 2D dam-break; produces 20k fluid pts.
| `official_dam2d_out2/CaseDambreakVal2D.out` | CaseDambreakVal2D | success | none | Second capture (likely same command) used for diffing.
| `official_sloshing_out/CaseSloshingHR_Def.out` | CaseSloshingHR_Def | success | `*** WARNING: File 'SloshingMotionData.dat' not found to copy.` (twice) | Motion file lives at `AutoXml_script/SloshingMotionData.dat`; copy step failed.
| `official_out/Case.out` & `official_out/CaseDambreakVal2D.out` | CaseDambreakVal2D | fail | `Attribute 'x' is missing.` | Raw XML in `AutoXml_script/CaseDambreakVal2D_Def.xml` lacked `x` attribute before normalization.

## Manual Regenerated XML Runs
| Output Directory | Case | Status | Warnings / Errors | Notes |
|------------------|------|--------|-------------------|-------|
| `regen_dambreak_out/CaseDambreak_Def.out` | CaseDambreak_Def_from_json | success | Same 3 fluid-related warnings | Regenerated XML matches official warning profile.
| `regen_official_dam2d_out2/CaseDambreakVal2D.out` | CaseDambreakVal2D_from_json | success | none | Shows bijection success for 2D dam-break.
| `regen_sloshing_out/CaseSloshingHR_Def.out` | CaseSloshingHR_Def_from_json | success | `SloshingMotionData.dat` copy warnings again | Need to package motion data into workspace before running.

## Round-trip / Miscellaneous Checks
| Output Directory | Case | Status | Warnings / Errors | Notes |
|------------------|------|--------|-------------------|-------|
| `roundtrip_out/Case.out` | Case (generic tank) | success | Same trio of ?no fluid? warnings | XML?JSON?XML round-trip retained boundary-only geometry.
| `roundtrip_out/CaseDambreakVal2D.out` | CaseDambreakVal2D | success | Same trio of ?no fluid? warnings | Indicates regenerated config omitted fluid block.
| `roundtrip_dam2d_out/CaseDambreakVal2D.out` | CaseDambreakVal2D | success | Same trio of ?no fluid? warnings | Confirms issue repeatable.
| `^.out` | (invalid case) | fail | `File: ^.xml` missing | Accidental invocation with malformed case name.
| `Case_out/Case.out` | Case_Def.xml | fail | `The variable 'Dp' does not exist.` | Template lacked mandatory constant definitions when evaluated.

## Supporting JSON Artifacts
- `dam2d_compare.json`, `dam2d_compare_new.json`, `sloshing_compare.json`, and `genCase_key_tests.json` capture full stdout for official vs regenerated runs to aid diffing.
- `AutoXml_script/config_library/CaseDamBreak3D_Def_official.json` and `AutoXml_script/config_library/CaseSloshingHR_Def_official.json` are XML?JSON snapshots feeding the regeneration pipeline.

## Gaps & Follow-up Items
- Regenerated XML files must be written into `AutoXml_script/generated_cases_direct/` (or `generated_cases/`) before invoking `report_runs_*`; otherwise GenCase exits with `XML file was not found`.
- Several regenerated / round-trip cases drop fluid geometry, leading to `No fluid particles were created?` warnings. Ensure `setmkfluid` + `fill*` commands survive normalization.
- Sloshing runs require `SloshingMotionData.dat` be copied alongside generated XML to silence copy warnings; consider embedding a file-copy helper in the pipeline.
- The failing `official_out` runs highlight missing positional attributes in historical XML; verify the JSON schema guardrails prevent omitting required coordinates.
- `Case_out/Case.out` shows the template parser still lacks `Dp`; template cases should inject constants before evaluation.

## Re-run Guidance
1. Re-generate XML from JSON configs: `python scripts/smoke_test_configs.py --config-dir AutoXml_script/config_library --output-dir AutoXml_script/generated_cases_direct --results AutoXml_script/generated_cases_direct/results.json`.
2. Run GenCase manually: `bin/windows/GenCase_win64.exe CaseDambreakVal2D_Def AutoXml_script/generated_cases_direct/CaseDambreakVal2D -save:all` (adjust case name & output folder per test).
3. Compare logs against the references above to confirm warning-free execution (or capture deviations).

## Automated Coverage
- Added pytest `tests/test_official_xml_cases.py` to execute every official XML in `AutoXml_script/` via `GenCase_win64`. It skips template files and fails on non-zero exit codes or logged `*** ERROR` messages, providing quick regression detection when official definitions stop compiling.
