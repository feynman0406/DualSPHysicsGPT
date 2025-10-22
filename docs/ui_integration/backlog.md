# UI Integration Backlog

The backlog captures near-term improvements for the DualSPHysics UI stack. Items are prioritised by
user value while respecting the immutable MVP baseline.

| Priority | Initiative | Rationale | Dependencies | Expected Impact |
| --- | --- | --- | --- | --- |
| P0 | Structured log streaming channel | Phase 3 and 4 logs still load via bulk fetch, blocking live troubleshooting; real-time streaming unlocks the log tab "Running" state described in `ui_state_matrix.md`. | UI backend needs incremental tailer + SSE/WebSocket endpoint; review with compliance before exposing live logs. | Faster triage during long MVP runs, reduces need to poll log files, improves perceived responsiveness. |
| P1 | Telemetry enrichment (token usage, retrieval quality, stage timings) | Phase 3 placeholders and Phase 4 notes cite missing metrics; surfacing OpenAI cost + retrieval health aligns with MVP governance goals. | Requires MVP wrapper parsing Agent 1/2 outputs without modifying MVP scripts; depends on history store schema update. | Enables cost dashboards, anomaly detection, and justifies continued MVP usage under budget constraints. |
| P1 | Parameter diff + artifact comparison workflow | Wireframes call for baseline diffs but current artifacts are static downloads; engineers need quick regress detection. | Needs artifact hash manifest from backend and UI diff viewer component; reuse baseline data from `logs/mvp/reference_run`. | Speeds regression analysis, supports governance requirements for change detection before execution. |
| P2 | Failure remediation playbooks in UI | Progress log notes open questions about failure translations; embedding guided actions reduces escalation load. | Extend error taxonomy in `ui_backend.errors` and add content hooks in frontend. Coordination with docs team for curated guidance. | Shortens MTTR for common OpenAI/network failures and enforces consistent operator responses. |
| P2 | Scheduled regression automation + telemetry hooks | Phase 5 CI assumes manual triggers; adding scheduled runs with telemetry export ensures drift detection. | Leverage new `scripts/run_full_regression` as orchestrator; integrate with GitHub Actions cron and metrics sink (eg JSON log). | Guarantees MVP + UI stack stay healthy, surfaces trends in run durations and resource usage for governance reviews. |
| P3 | Accessibility and localisation audit | UI foundation built quickly; need WCAG + internationalisation review before broader rollout. | Requires design review, storybook snapshots, and translation pipeline; coordinate with UX team. | Expands user reach, reduces risk of late-stage compliance blockers. |

## Recent Updates
- 2025-10-22: Shipped the artifact viewer copy preview control so operators can copy visible artifact text; navigator.clipboard requires HTTPS or localhost and falls back to execCommand-based copying.

Backlog items map directly to open questions recorded in prior phase documentation (progress log, wireframes, state matrix) ensuring future work aligns with protected MVP constraints.
