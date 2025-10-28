# File Search Include Rollout — Knowledge Blackboard
Last Updated: 2025-10-28T09:50:00Z

## Signals
- Gravity vector confirmed (0,0,-9.81) per logs/last_run/response.txt:7.
- Agent D refreshed docs/external_stl_agent_prompts.md with include-based guidance and landed tests/test_openai_file_search.py to assert snippets + search_call_id in persisted sources (2025-10-28T08:35Z).
- Domain checks and normals readiness all green per logs/last_run/response.txt:506 and logs/last_run/response.txt:509.
- TimeMax configured at 3.0s supporting short validation cycles per logs/last_run/response.txt:456.
- Retrieval refactor captures snippet-rich sources; see logs/last_run/metadata.json:1 and logs/last_run/sources.json:1.
- Agent C run logged snippet-rich references in logs/mvp/agent1_output.json and logs/last_run/sources.json (2025-10-28T07:59Z).
- persist_sources now emits logs/last_run/generator_sources.json and generator_sources.txt summarizing include snippets for downstream debugging.
- 2025-10-28T09:45Z QA sweep (Agent F): pytest 21 passed; baseline MVP run succeeded; STL run confirmed externalstl query injection and stored uploads/manual-1761642532/Duck.stl (logs/mvp/agent1_output.json, logs/last_run/metadata.json).

## Risks / Gaps
- Agent R: please confirm actual External.stl asset path; assumption noted at logs/last_run/response.txt:518.
- No authoritative record of previous handoff owner; entry flagged in docs/include_rollout_handoffs.md:6.
- STL substitution gap: latest STL run generated drawbox-only geometry; Duck.stl never appears in logs/mvp/agent2_config.json or logs/mvp/generated_case.xml.
- Windows console default encoding (cp950) still breaks Agent 1 output without PYTHONIOENCODING override.

## Actions
- Await Agent R confirmation to unblock tickets FSI-003 and Agent F validation.
- Agent F to pick up the snippet-aware logs and validate end-to-end sources payload during QA sweep (use new pytest coverage as reference).
- File regression ticket for missing drawfilestl rename and track encoding mitigation for Windows consoles.
