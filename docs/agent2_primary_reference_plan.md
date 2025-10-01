# Agent 2 Primary Reference Alignment Plan

## Overview
Objective: ensure Schema Agent (Stage 2) reuses the primary reference configuration's geometry and algorithm structure with minimal numerical tweaks, while still handling low-similarity cases safely.

## Stage Checklist
| Stage | Goals | Planned Tests | Status |
|-------|-------|---------------|--------|
| Stage 1 | Capture current behaviour, draft implementation plan, create tracking doc | pytest tests/test_planning_phase1.py | Done (20 passed) |
| Stage 2 | Update Planning Agent to flag primary reference and emit stronger guidance & overrides | pytest tests/test_planning_phase1.py | Done (20 passed) |
| Stage 3 | Update Schema Agent to preload reference template, apply minimal overrides, tighten prompt | pytest tests/test_generate_xml.py & pytest tests/test_json_normalizer.py | Done (generate_xml + json_normalizer passing) |
| Stage 4 | Regression pass, finalize documentation, ensure logs reflect new metadata | pytest tests/test_generator_json_pipeline.py | Done (5 passed; warning about datetime.utcnow in sessions/store.py) |

## Notes
- Maintain compatibility with existing Plan JSON schema (no new top-level keys).
- Ensure fallback instructions cover low-score cases to avoid brittle behaviour.
- Avoid adding heavy dependencies; stick to standard library helpers.
- Resolved previous pytest tests/test_generate_xml.py failures by fixing geometry fallback, label precedence, and tag sanitization.


