# Baseline Manifest

Phase 0 establishes the MVP CLI as an immutable baseline. Unless a later phase explicitly relaxes restrictions, treat every location outside the two writable roots below as read-only:

- `docs/ui_integration/`
- `logs/mvp/reference_run/`

For quick reference, the following repository areas remain immutable in Phase 0 (non-exhaustive but covers all active code/assets):
- Repository root files (`*.py`, `*.md`, `.env`, plans, etc.)
- `agents/`, `api/`, `AutoXml_script/`, `chains/`, `cli/`, `controller/`, `llm/`, `metrics/`, `prompts/`, `rag/`, `schemas/`, `scripts/`, `sessions/`, `tests/`, `tools/`, `ui_backend/`
- `logs/mvp/` contents other than `logs/mvp/reference_run/`
- Generated case directories such as `Case_out/` and `CaseSloshingHR_Def_from_xml_out_direct/`

Always capture modifications¡Xand any newly discovered immutable paths¡Xin future manifests so the UI stack stays aligned with the frozen MVP behavior.
