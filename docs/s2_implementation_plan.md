# S2 Implementation Plan: RAG Planning Agent (Phase 2)

## Overview
This document outlines the implementation plan for Phase 2 of the RAG Planning Agent system, based on `docs/s2_rag_planning_agent.md`.

## Current State Analysis

### Existing Infrastructure
1. ✅ **Schema Defined**: `schemas/planning_agent_schema.json` - Complete Plan JSON schema
2. ✅ **OpenAI File Search**: `rag/openai_file_search.py` - Retrieval with metadata filtering
3. ✅ **Generator Pipeline**: `chains/generator.py` - Can output JSON with schema
4. ✅ **Validation**: `agents/plan_validator.py` - Schema validation infrastructure
5. ✅ **Logging**: `agents/logging_utils.py` - Logging utilities

### What's Missing (Phase 2)
1. ❌ **Planning Agent Core Logic** - RAG retrieval + curation + scoring
2. ❌ **XML/JSON Parsing & Scoring** - 4-dimension evaluation (Algorithm, Geometry, Boundary, Execution)
3. ❌ **Schema Guidance Generator** - TODO placeholder generation
4. ❌ **Two-Stage Integration** - Connect Planning Agent → Schema Agent
5. ❌ **Retry Mechanism** - Feedback loops from Stage 2 failures
6. ❌ **Metrics Tracking** - `metrics/plan_runs.csv` and monitoring
7. ❌ **Comprehensive Tests** - End-to-end testing

## Implementation Checklist

### Phase 2.1: Core Planning Agent (Priority 1)
- [ ] Create `agents/planning_agent.py`
  - [ ] Implement `run_planning_agent()` main entry point
  - [ ] Add `_parse_retrieved_files()` - Load JSON/XML from config_library
  - [ ] Add `_score_example()` - 4-dimension scoring (1-5 scale)
  - [ ] Add `_select_curated_examples()` - Top-k selection with diversity
  - [ ] Add `_extract_parameters()` - Parameter extraction from examples
  - [ ] Add `_detect_coverage()` - case_type/dim/features analysis
  - [ ] Add `_generate_schema_guidance()` - TODO placeholder generation
  - [ ] Add `_build_plan_json()` - Assemble final Plan JSON

- [ ] Create `prompts/planning_agent_system_prompt.md`
  - [ ] Define Planning Agent responsibilities
  - [ ] Add scoring criteria (Algorithm, Geometry, Boundary, Execution)
  - [ ] Add quote extraction rules
  - [ ] Add conflict detection guidelines

### Phase 2.2: Schema Agent Integration (Priority 1)
- [ ] Create `agents/schema_agent.py`
  - [ ] Implement `run_schema_agent()` - Generate JSON from Plan
  - [ ] Add Plan JSON parsing and evidence assembly
  - [ ] Add schema_guidance interpretation
  - [ ] Add missing_params handling strategies

- [ ] Create `prompts/schema_agent_system_prompt.md`
  - [ ] Define Schema Agent responsibilities
  - [ ] Add strict JSON schema adherence rules
  - [ ] Add fallback strategies for missing params
  - [ ] Add unit/dimension consistency checks

- [ ] Update `chains/generator.py`
  - [ ] Add `USE_TWO_STAGE_RAG_SCHEMA` environment variable check
  - [ ] Add `USE_RAG_PLANNING_AGENT` environment variable check
  - [ ] Implement two-stage workflow:
    ```python
    if USE_TWO_STAGE_RAG_SCHEMA and USE_RAG_PLANNING_AGENT:
        # Stage 1: Planning Agent
        plan_json = run_planning_agent(user_query, vs_ids, metadata_filter)
        persist_plan_json(plan_json)
        
        # Stage 2: Schema Agent
        config_json = run_schema_agent(plan_json, user_query, schema)
        xml = generate_case_xml(config_json)
    else:
        # Existing single-stage logic
    ```

### Phase 2.3: XML/JSON Analysis & Scoring (Priority 2)
- [ ] Create `agents/example_scorer.py`
  - [ ] Implement `score_algorithm()` - Algorithm relevance (1-5)
  - [ ] Implement `score_geometry()` - Geometry fit (1-5)
  - [ ] Implement `score_boundary()` - Boundary/materials match (1-5)
  - [ ] Implement `score_execution()` - Execution params match (1-5)
  - [ ] Implement `compute_aggregate_score()` - Average + rationale
  - [ ] Add XML/JSON parsing utilities

- [ ] Create `agents/quote_extractor.py`
  - [ ] Implement `extract_quotes()` - Smart quote extraction
  - [ ] Add length limiting (<600 chars)
  - [ ] Add span tracking (start/end indices)
  - [ ] Add diversity enforcement (max 3 per file)

### Phase 2.4: Retry Mechanism (Priority 2)
- [ ] Create `agents/retry_manager.py`
  - [ ] Implement `handle_stage2_failure()` - Parse Stage 2 errors
  - [ ] Add `update_plan_for_retry()` - Enhance Plan JSON
  - [ ] Add `append_retry_feedback()` - Track retry history
  - [ ] Add retry limit enforcement (max 3 retries)

- [ ] Update `agents/planning_agent.py`
  - [ ] Add `retry` parameter support
  - [ ] Add `stage2_feedback` processing
  - [ ] Update `schema_guidance` with retry info

### Phase 2.5: Monitoring & Metrics (Priority 2)
- [ ] Create `metrics/plan_runs.csv` structure
  - [ ] Define columns: timestamp, query_hash, status, completion_rate, stage2_passed, attempt, notes
  - [ ] Add CSV headers

- [ ] Create `agents/metrics_tracker.py`
  - [ ] Implement `log_plan_run()` - Record each planning attempt
  - [ ] Implement `compute_completion_rate()` - Required fields coverage
  - [ ] Implement `compute_stage2_success_rate()` - Daily success rate
  - [ ] Add high-risk flagging (completion_rate < 0.7)

- [ ] Update logging
  - [ ] Persist `logs/last_run/planning_plan.json`
  - [ ] Add `status`, `attempt`, `plan_completion_rate` fields
  - [ ] Add `stage2_feedback` for failures

### Phase 2.6: Testing (Priority 3)
- [ ] Create `tests/test_planning_agent.py`
  - [ ] Test `run_planning_agent()` with mock retrieval
  - [ ] Test scoring logic with sample XML/JSON
  - [ ] Test quote extraction
  - [ ] Test Plan JSON validation

- [ ] Create `tests/test_schema_agent.py`
  - [ ] Test `run_schema_agent()` with sample Plan JSON
  - [ ] Test schema_guidance interpretation
  - [ ] Test missing_params handling
  - [ ] Test strict JSON schema compliance

- [ ] Create `tests/test_two_stage_pipeline.py`
  - [ ] End-to-end test: query → Plan JSON → config JSON → XML
  - [ ] Test retry mechanism
  - [ ] Test metadata filtering
  - [ ] Test metrics tracking

- [ ] Update `tests/test_planning_phase1.py`
  - [ ] Add Phase 2 integration tests
  - [ ] Test two-stage workflow

### Phase 2.7: Documentation (Priority 3)
- [ ] Update `README.md`
  - [ ] Add two-stage RAG setup instructions
  - [ ] Add environment variables documentation
  - [ ] Add troubleshooting guide

- [ ] Create `docs/two_stage_usage_guide.md`
  - [ ] Usage examples
  - [ ] Configuration options
  - [ ] Monitoring and debugging

- [ ] Update `agents/README.md`
  - [ ] Document Planning Agent
  - [ ] Document Schema Agent
  - [ ] Document retry mechanism

## File Structure

```
agents/
├── planning_agent.py        # NEW: Main Planning Agent
├── schema_agent.py          # NEW: Schema Agent
├── example_scorer.py        # NEW: Scoring logic
├── quote_extractor.py       # NEW: Quote extraction
├── retry_manager.py         # NEW: Retry handling
├── metrics_tracker.py       # NEW: Metrics tracking
├── config.py                # Existing
├── plan_validator.py        # Existing
└── logging_utils.py         # Existing

prompts/
├── planning_agent_system_prompt.md    # NEW
├── schema_agent_system_prompt.md      # NEW
├── generator_system_prompt.md         # Existing
└── fixer_system_prompt.md             # Existing

logs/last_run/
├── planning_plan.json       # NEW: Plan JSON output
├── metadata.json            # Existing
├── sources.json             # Existing
└── response.txt             # Existing

metrics/
├── plan_runs.csv            # NEW: Planning metrics
└── .gitkeep                 # Existing
```

## Environment Variables

```bash
# Two-stage RAG control
USE_TWO_STAGE_RAG_SCHEMA=1       # Enable two-stage mode
USE_RAG_PLANNING_AGENT=1         # Use Planning Agent in Stage 1

# Existing variables (still needed)
USE_RAG=1
OPENAI_RAG_VS_DESIGN_ID=vs_xxx
DSPH_USE_JSON_SCHEMA=1
DSPH_STRICT_JSON_SCHEMA=1        # Strict schema in Stage 2
```

## Implementation Order

### Sprint 1 (Days 1-3): Core Planning Agent
1. Create `agents/planning_agent.py` skeleton
2. Implement basic retrieval integration
3. Add simple scoring (stub implementation)
4. Generate basic Plan JSON
5. Add unit tests

### Sprint 2 (Days 4-6): Schema Agent & Integration
1. Create `agents/schema_agent.py`
2. Integrate with generator.py (two-stage workflow)
3. Add Plan JSON → Schema Agent flow
4. Test end-to-end with simple cases

### Sprint 3 (Days 7-9): Scoring & Analysis
1. Implement full 4-dimension scoring
2. Add XML/JSON parsing
3. Add quote extraction with length limits
4. Add parameter extraction
5. Test with real config_library files

### Sprint 4 (Days 10-12): Retry & Monitoring
1. Implement retry mechanism
2. Add metrics tracking
3. Add CSV logging
4. Test retry scenarios
5. Add monitoring dashboard

### Sprint 5 (Days 13-14): Testing & Documentation
1. Comprehensive integration tests
2. Update all documentation
3. Create usage guide
4. Performance tuning

## Success Criteria

### Functional
- [ ] Planning Agent successfully retrieves and scores examples
- [ ] Plan JSON validates against schema
- [ ] Schema Agent generates valid config JSON
- [ ] Retry mechanism handles Stage 2 failures
- [ ] Metrics tracking works correctly

### Quality
- [ ] Stage 2 success rate > 80%
- [ ] Plan completion rate > 70%
- [ ] Retry success rate > 60% (after 1 retry)
- [ ] No regressions in existing tests

### Performance
- [ ] Planning Agent latency < 5s (excluding LLM calls)
- [ ] Total two-stage latency < 2x single-stage
- [ ] Memory footprint acceptable

## Risk Mitigation

### Risk 1: Scoring complexity
- **Mitigation**: Start with simple scoring, iterate based on results
- **Fallback**: Use retrieval scores only

### Risk 2: Plan JSON too large
- **Mitigation**: Strict length limits on quotes and arrays
- **Fallback**: Reduce maxItems in schema

### Risk 3: Stage 2 failures
- **Mitigation**: Comprehensive retry with feedback
- **Fallback**: Graceful degradation to single-stage

### Risk 4: Performance degradation
- **Mitigation**: Caching, parallel processing where possible
- **Fallback**: Make two-stage optional

## Notes

- Keep Phase 1 infrastructure intact (validation, logging)
- Ensure backward compatibility with single-stage mode
- Add feature flags for gradual rollout
- Monitor metrics closely during initial deployment
- Prepare rollback plan if success rate drops

## Next Steps After Phase 2

- Phase 3: Schema Guidance Agent (separate agent for guidance generation)
- Phase 4: Advanced caching and optimization
- Phase 5: Multi-model support and A/B testing
