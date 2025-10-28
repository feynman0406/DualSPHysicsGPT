# File Search Include Rollout - Ticket Backlog
Last Updated: 2025-10-28T09:50:00Z

## Backlog
| Ticket | Summary | Source | Status | Notes |
| --- | --- | --- | --- | --- |
| C | Consumer alignment with include payload | logs/mvp/agent1_output.json:1 | in-review | Agent C verified snippet-rich references and handed off to Agent D (see docs/include_rollout_handoffs.md). |
| R | Retrieval include refactor complete; snippet payload available. | logs/last_run/sources.json:1 | done | Handoff sent to Agent C for consumer alignment. |
| D | Docs/tests updated for include payload; pytest suite recorded. | docs/external_stl_agent_prompts.md:1 | in-review | Agent D refreshed include prompts and added tests/test_openai_file_search.py; pytest log at logs/last_run/README.md (2025-10-28T08:35Z). |
| FSI-001 | Domain and boundary conformity validated for external STL tank setup. | logs/last_run/response.txt:506 | done | Checks list confirms Domain-2x gate, wall schema, and normals readiness. |
| FSI-002 | Execution parameters captured for rollout reference (StepAlgorithm=2, Kernel=2, TimeMax=3.0s). | logs/last_run/response.txt:399 | in-progress | Agent C to package into onboarding brief per docs/include_rollout_readme.md:18. |
| FSI-003 | Confirm actual External.stl asset path and update documentation. | logs/last_run/response.txt:518 | blocked | Pending Agent R response; escalation tracked in docs/include_rollout_kb.md. |
| FSI-004 | Prepare validation report once include search wires to runtime. | docs/include_rollout_readme.md:15 | queued | Dependent on Agent R and Agent C deliverables before execution. |
| F | QA regression: Duck.stl not injected into generated config/XML. | logs/mvp/generated_case.xml:1 | blocked | STL run still emits drawbox geometry; Duck.stl absent and cp950 encoding workaround required for CLI logs. |

## Queue Notes
- Tickets remain aligned with milestones in docs/include_rollout_milestones.md.
