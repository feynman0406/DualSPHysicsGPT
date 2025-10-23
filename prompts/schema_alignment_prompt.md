# Schema Alignment Implementation Prompt
You are updating DualSPHysicsGPT so Structured Outputs place normals under the <casedef> section instead of execution.special. Follow the fix plan Step 9.

1. Schema updates (schemas/dualsphysics_config_schema.json)
   - Add optional top-level keys: normals (with norgeometry subtree), casedef_children (array of section/generic entries), casedef_extra (array of generic nodes).
   - Introduce a casedefChildPlan definition mirroring the structures used in config_library templates.
   - Restrict execution.special items so entries tagged/type/name == "normals" are rejected by the schema.

2. Guidance alignment
   - Rewrite prompts/auto_xml_contract.md sections that currently say "normals under execution.special"; instruct agents to populate the new normals object and keep execution.special for timeout/wavepaddles/etc.
   - Explicitly call out that drawbox/fillbox commands must use boxfill/modefill child nodes (first) followed by point/size vectors.
   - Update docs/json_schema.md and docs/auto_xml_schema.md to match the new contract (mention casedef_children + normals).

3. Tests + pipeline
   - Adjust tests/test_json_normalizer.py so configurations already compliant with the new schema do not record a "Moved normals" warning.
   - Add a schema-validation test (e.g., in tests/test_generator_json_pipeline.py) that feeds a config_library JSON through the SO validator to ensure the new fields are accepted and normals-in-special is rejected.
   - Re-run the MVP smoke path (scripts/mvp_direct_file_search.py) to confirm Agent2 output validates without migration.

Deliverables:
   * Updated schema/doc/prompt files in sync.
   * Passing pytest suite noted above.
   * Release notes in fix_plan.md Step 9 with status + date.
