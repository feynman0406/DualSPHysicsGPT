# File Search Include Rollout Playbook (Agent S)
Last Updated: 2025-10-28T10:22:11.3582262+08:00

## Overview
- Agent S curates shared documentation and ensures continuity for the File Search Include rollout.
- Baseline external STL tank configuration passes key checks per logs/last_run/response.txt:506.
- Outstanding STL asset mapping remains unresolved; escalation recorded in docs/include_rollout_kb.md:10.

## Task Queue (Agent Missions)
| Owner | Mission | Prerequisites | Success Criteria | Status |
| --- | --- | --- | --- | --- |
| Agent R | Confirm actual STL asset path and update geometry references. | Access to upstream asset registry; response from design team. | docs/include_rollout_kb.md:10 updated with verified STL path and removal of escalation note. | queued |
| Agent C | Consolidate configuration constants into onboarding brief. | Review logs/last_run/response.txt:7 and docs/include_rollout_tickets.md:8. | Brief stored in docs/include_rollout_readme.md:18 with stakeholder sign-off. | queued |
| Agent D | Draft developer communication for include rollout. | Ticket summary from docs/include_rollout_tickets.md:7; milestone targets from docs/include_rollout_milestones.md:6. | Announcement draft attached in docs/include_rollout_handoffs.md:6 and acked by Agent S. | queued |
| Agent F | Validate runtime against case definition using updated include search. | Finalized STL mapping (Agent R) and config brief (Agent C). | Execution report logged in docs/include_rollout_tickets.md:10 with pass/fail metrics. | queued |

## Delivery Record
- Pending: Agent C to add onboarding brief when ready.

## Linked Resources
- Knowledge Blackboard ¡÷ docs/include_rollout_kb.md:1
- Ticket Backlog ¡÷ docs/include_rollout_tickets.md:1
- Milestones ¡÷ docs/include_rollout_milestones.md:1
- Handoff Log ¡÷ docs/include_rollout_handoffs.md:1
- Decisions ¡÷ docs/include_rollout_adr.md:1
