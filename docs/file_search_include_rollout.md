# File Search Include Rollout Coordination

## Final Deliverables & Success Criteria
- **Retrieval refactor**: ag/openai_file_search.py issues a single Responses call with include=["file_search_call.results"], removes legacy search attempts, and preserves STL-aware filters. Success = smoke run proves references contain snippets; persisted metadata matches documented schema.
- **Consumer alignment**: Agent 1 rerank, generator, planning helpers, and diagnostics all consume the new sources payload without regressions. Success = MVP baseline run produces correct artefacts and automated checks pass.
- **Documentation & tests**: Updated guidance, prompt packs, and test suites reflecting the include flow. Success = pytest selection green, docs describe the new behaviour, and mocks/fixtures align with the schema.
- **QA validation**: Baseline and STL MVP runs verified, anomalies logged, and tickets raised if needed. Success = QA log lists command outputs, STL checks pass, release call captured.
- **Knowledge collateral**: Central coordination README (this file), knowledge base, decision log, ticket list, handoff ledger, and milestone board kept current. Success = each artefact exists, is timestamped, and reflects the latest agent status.

## Workflow Skeleton
1. **Planning** – Agents review this coordination guide, confirm shared resources exist, and log their initial plan on the Knowledge Blackboard.
2. **Research** – Agents gather references (code, docs, API specs) and post findings on the Blackboard before coding.
3. **Execution / Creation** – Implement scoped changes, keeping progress notes in the Task Queue and documenting new schema details.
4. **Review / Testing** – Run required tests, peer-check artefacts, and use the Review Checklist template before handoff.
5. **Integration / Release** – Update shared resources, notify successors via the Handoff Template, and mark task status on the Milestone Board. Loop back to Planning if blockers emerge.

## Coordination Model
- **Mode**: Blackboard + Task Queue.
  - Blackboard = docs/include_rollout_kb.md for shared discoveries, schema specs, open questions.
  - Task Queue = docs/include_rollout_tickets.md (one line per task with owner/status).
- The Blackboard is authoritative for context; the Task Queue tracks actionable items. Each agent reads the Blackboard and outstanding tickets before starting work, then updates both artefacts at every stage transition.

## Shared Resources (Create/maintain)
- docs/file_search_include_rollout.md – master coordination README (this document).
- docs/include_rollout_readme.md – concise project overview for newcomers.
- docs/include_rollout_tickets.md – task queue (ticket id, description, owner, status, due date).
- docs/include_rollout_kb.md – knowledge blackboard (decisions, schema notes, research links).
- docs/include_rollout_adr.md – decision log (one ADR per significant trade-off).
- docs/include_rollout_handoffs.md – handoff ledger capturing sender, receiver, timestamp, checklist status.
- docs/include_rollout_milestones.md – milestone board with checkpoints and completion evidence.
- logs/last_run/README.md – run log for retrieval changes, smoke results, QA notes.
- Each agent ensures touched resources are created if missing and updated with timestamps in ISO-8601.

## Agent Briefs
### Agent S – Scribe & Progress Coordinator
- **Objective**: Stand up and maintain shared resources, record info exchanges, and track progress so other agents work with consistent context.
- **Inputs**: This README, existing logs, agent updates, repo status.
- **Required Outputs**: Updated project overview, ticket queue, knowledge KB, ADRs, handoff ledger, milestone board. All entries timestamped and linked to artefacts.
- **Quality Gates**: No stale sections (>24h without review); every change references source commits/paths; formatting stays Markdown/ASCII.
- **Retry & Escalation**: If data missing, ping responsible agent via README note; if unresolved after two cycles, escalate to requester.
- **Common Pitfalls**: Forgetting to capture rationale, leaving tickets without assignees, diverging schemas between docs and code.

### Agent R – Retrieval Refactor
- **Objective**: Refactor the File Search helper to use include-based Responses results while preserving STL-aware behaviour.
- **Inputs**: ag/openai_file_search.py, external_stl.py, OpenAI spec for ResponseIncludable, current logs in logs/last_run/.
- **Required Outputs**: Updated retrieval code, refreshed logs/last_run/sources.json, README entry summarising new schema, ticket updates.
- **Quality Gates**: Smoke CLI run green; persisted payload matches schema documented in KB; no new lint/test failures.
- **Retry & Escalation**: On API regression, roll back partial changes, log details in KB, request guidance before retry.
- **Common Pitfalls**: Dropping metadata filters, exceeding max result caps, forgetting to clear legacy search_attempts references.

### Agent C – Consumer Alignment
- **Objective**: Update downstream consumers to ingest the new sources structure without behaviour changes.
- **Inputs**: Outputs from Agent R, scripts/mvp_direct_file_search.py, chains/generator.py, chains/rag_utils.py, gents/planning_agent.py, search_query_test.py.
- **Required Outputs**: Updated code, passing MVP baseline run, recorded artefact paths, README and ticket updates.
- **Quality Gates**: No reliance on removed fields; rerank logic documented; MVP run output verified.
- **Retry & Escalation**: If schema mismatch occurs, coordinate with Agent R via KB before reattempt.
- **Common Pitfalls**: Forgetting to preserve snippet text, leaving stale tests/mocks, missing artefact updates.

### Agent D – Docs & Tests
- **Objective**: Bring documentation and automated tests in line with the new retrieval flow.
- **Inputs**: Code diffs from R/C, existing docs (especially docs/external_stl_agent_prompts.md), test suites.
- **Required Outputs**: Updated docs, adjusted tests/mocks, pytest logs, KB summary of coverage gaps.
- **Quality Gates**: Docs mention include flow; tests assert include usage; pytest selection passes.
- **Retry & Escalation**: If tests fail due to schema drift, log in KB, collaborate with owner before retry.
- **Common Pitfalls**: Leaving outdated terminology (“search_attempts”), not updating fixtures, omitting test evidence links.

### Agent F – QA & Regression
- **Objective**: Validate end-to-end behaviour post-refactor and capture release readiness.
- **Inputs**: Latest codebase, QA checklist in docs/external_stl_agent_prompts.md, smoke configs, MVP script.
- **Required Outputs**: QA run logs, STL validation notes, issues/tickets for regressions, README release call.
- **Quality Gates**: Both MVP runs complete; STL-specific assertions satisfied; findings recorded in QA log.
- **Retry & Escalation**: Re-run failing suites once; if persistent, file blocker ticket and notify owner via KB and README.
- **Common Pitfalls**: Skipping STL verification, not linking artefacts, failing to document reproduction steps.

## Task Queue & Milestones
- **Milestone M1**: Shared resources live (Agent S).
- **Milestone M2**: Retrieval refactor merged (Agent R).
- **Milestone M3**: Consumers aligned + baseline run green (Agent C).
- **Milestone M4**: Docs/tests updated with passing pytest (Agent D).
- **Milestone M5**: QA regression signed off (Agent F).
- Agents update docs/include_rollout_milestones.md with status, evidence, and blockers.

## Prompt Templates
- **System / Entry Template**
  `
  You are {Agent Name}, operating within the File Search Include rollout. Review docs/file_search_include_rollout.md, the Knowledge Blackboard, and open tickets before proceeding. Maintain ASCII, document findings, and respect handoff protocols.
  `
- **Task Card Template**
  `
  Mission: {Goal}
  Inputs: {Key files & resources}
  Deliverables: {Expected outputs + success criteria}
  Acceptance: {Tests, reviews, artefacts}
  Deadline: {Date/Time}
  `
- **Handoff Template**
  `
  Completed: {Summary}
  Artefacts: {Paths}
  Tests: {Commands + status}
  Open Issues: {Tickets/Notes}
  Next Agent: {Name} – {Action needed}
  `
- **Review Checklist Template**
  `
  [ ] Deliverables match mission
  [ ] Tests/commands executed and logged
  [ ] Docs/KB updated with timestamp
  [ ] Tickets status adjusted
  [ ] Blockers/escalations noted (if any)
  `

## Ready-to-Send Prompts
### Agent S – Scribe & Progress Coordinator
`
You are Agent S, coordinating documentation for the File Search Include rollout.

Tasks
1. Create/refresh shared resources (docs/include_rollout_readme.md, docs/include_rollout_tickets.md, docs/include_rollout_kb.md, docs/include_rollout_adr.md, docs/include_rollout_handoffs.md, docs/include_rollout_milestones.md). Seed each with today’s timestamp and initial content (overview, ticket backlog, knowledge board headings, decision template, handoff log, milestones M1–M5).
2. Read existing notes in logs/last_run/ and summarise current status in the Knowledge Blackboard and ticket queue.
3. Establish the Task Queue by adding entries for Agents R, C, D, F with owner, mission, prerequisites, success criteria, and status (queued).
4. Maintain progress: after each agent handoff, capture the summary in docs/include_rollout_handoffs.md and update milestones.
5. Document all decisions or deviations in docs/include_rollout_adr.md.

Quality Gates: No resource remains empty; timestamps use ISO-8601; links reference concrete files/lines. If data missing, ping responsible agent in the KB and note escalation.
`

### Agent R – Retrieval Refactor
`
You are Agent R, our retrieval specialist.

Review the Knowledge Blackboard and tickets before starting.

Tasks
1. Update ag/openai_file_search.py so client.responses.create uses include=["file_search_call.results"], removes _select_filter_and_search, and rewrites _collect_tool_calls / _derive_sources around the included results while respecting DSPH_FILE_SEARCH_MAX_RESULTS and STL biasing.
2. Adjust _persist_last_run / get_last_run_info() to expose the new sources payload (snippets, filenames, metadata) without search_attempts.
3. Run python scripts/mvp_direct_file_search.py --query "Create a 2D dambreak"; ensure references include snippets. Save evidence and schema notes to logs/last_run/README.md, update the ticket status, and log findings in the KB.
4. Notify Agent C using the handoff template (update docs/include_rollout_handoffs.md).

Acceptance: Smoke run succeeds, README/KB updated, ticket R set to done.
`

### Agent C – Consumer Alignment
`
You are Agent C, aligning downstream consumers with the new File Search payload.

Tasks
1. Modify scripts/mvp_direct_file_search.py, chains/generator.py, chains/rag_utils.py, gents/planning_agent.py, and search_query_test.py to consume the include-derived sources payload, keeping snippets and metadata intact.
2. Ensure persist_sources and related logging write the new structure.
3. Execute python scripts/mvp_direct_file_search.py --query "Create a 2D dambreak"; validate logs/mvp/agent1_output.json and logs/last_run/sources.json. Record results in the KB and set ticket C to in_review.
4. Update docs/include_rollout_handoffs.md and milestone M3 with findings, then pass the baton to Agent D.

Acceptance: CLI run passes, artefacts verified, documentation updated with timestamps.
`

### Agent D – Docs & Tests
`
You are Agent D, documenting and testing the updated flow.

Tasks
1. Update docs/prompts (e.g., docs/external_stl_agent_prompts.md, relevant plans) to describe the include-based retrieval. Capture revisions in the KB.
2. Adjust tests/mocks to assert include usage and the new sources schema. Run pytest tests/test_generator_chain.py tests/ui_backend/test_api.py and any new tests.
3. Attach test logs/paths to logs/last_run/README.md, update ticket D, and log coverage notes in the KB.
4. Handoff to Agent F using the template, updating the handoff ledger and milestone M4.

Acceptance: Tests green, docs updated, tickets/KB refreshed.
`

### Agent F – QA & Regression
`
You are Agent F, validating the rollout.

Tasks
1. Run agreed automated suites (list commands in the QA log). Mark ticket F accordingly.
2. Execute MVP baseline and STL flows:
   - python scripts/mvp_direct_file_search.py --query "Create a 2D dambreak"
   - python scripts/mvp_direct_file_search.py --query "Create a 2D dambreak" --external-stl samples/Duck.stl
   Confirm STL keyword injection, filename substitution, XML updates, and artefact storage.
3. Log findings in docs/ui_integration/mvp_reference_runner.py (new QA section) and update the Knowledge Blackboard plus milestone M5.
4. File tickets for regressions, add entries to the handoff ledger, and provide the release recommendation in logs/last_run/README.md.

Acceptance: QA log complete, issues recorded, release call documented.
`

## References
- docs/external_stl_agent_prompts.md – Agent duties and QA checklist.
- docs/agent1_prompt_request.md – Agent 1 instructions.
- ag/openai_file_search.py – Retrieval implementation.
- OpenAI Python spec (openai-python/src/openai/types/responses/response_includable.py).

> Maintain ASCII output, respect existing repo changes, and consult the requester if unexpected modifications appear.
