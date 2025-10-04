# Planning Agent Module

## Overview

The Planning Agent module implements Phase 1 of the S2 RAG Planning Agent architecture. It provides:

- **Two-stage RAG + Schema pipeline**: Separates planning (Agent 1) from schema generation (Agent 2)
- **Auditable Plan JSON**: Structured output that documents retrieval, curation, and guidance
- **Configuration management**: Environment-based settings with sensible defaults
- **Validation**: Schema-based and custom validation with structured error reporting
- **Logging & Metrics**: Persistent logs and metrics for monitoring and debugging

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_RAG_PLANNING_AGENT` | `"0"` | Enable the planning agent pipeline (`"1"` to enable) |
| `PLANNING_AGENT_MODE` | `"two-requests"` | Mode: `"two-requests"` or `"single-request"` |
| `PLANNING_MAX_CURATED_EXAMPLES` | `"12"` | Maximum number of curated examples |
| `PLANNING_MAX_QUOTE_LENGTH` | `"400"` | Maximum length of quote text in characters |
| `PLANNING_SCHEMA_VERSION` | `"1.0"` | Plan JSON schema version |

### Setting Environment Variables

**Windows PowerShell:**
```powershell
$env:USE_RAG_PLANNING_AGENT="1"
$env:PLANNING_AGENT_MODE="two-requests"
$env:PLANNING_MAX_CURATED_EXAMPLES="10"
```

**Unix/Linux/Mac:**
```bash
export USE_RAG_PLANNING_AGENT=1
export PLANNING_AGENT_MODE=two-requests
export PLANNING_MAX_CURATED_EXAMPLES=10
```

## Plan JSON Schema

The Plan JSON serves as the contract between Agent 1 (Planning) and Agent 2 (Schema Generation).

### Required Fields

- `query`: Original user query or search query
- `curated_examples`: Array of selected examples with citations
- `schema_guidance`: Guidance for Schema Agent with TODO placeholders

### Optional Fields

- `metadata_filter`: Metadata filter applied during retrieval
- `coverage`: Coverage analysis (case_type, dim, features)
- `extracted_params`: Parameters extracted from examples
- `missing_params`: List of required but missing parameters
- `conflicts`: Detected conflicts or inconsistencies
- `citations`: Detailed citations
- `tool_calls`: Tool calls made during planning
- `status`: Planning status (`completed`, `no_results`, `retrying`)
- `attempt`: Retry attempt number
- `plan_completion_rate`: Fraction of required fields covered (0.0-1.0)
- `stage2_feedback`: Feedback from Stage 2 if failed

### Example Plan JSON

```json
{
  "schema_version": "1.0",
  "query": "Create a 2D dambreak simulation",
  "metadata_filter": {
    "case_type": "dambreak",
    "dim": "2D"
  },
  "curated_examples": [
    {
      "filename": "CaseDambreak_Def.json",
      "rank": 1,
      "score": 0.95,
      "rationale": "Perfect match for 2D dambreak",
      "spans": [
        {
          "quote": "{ \"StepAlgorithm\": 1, \"Kernel\": 2 }"
        }
      ]
    }
  ],
  "schema_guidance": "<<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>\n[required_fields]\n- TimeMax needs specification"
}
```

## Validation

### Using the Validator

```python
from agents import validate_plan_json

plan = {...}  # Your plan dictionary
result = validate_plan_json(plan)

if result.valid:
    print("Plan is valid!")
else:
    for issue in result.issues:
        print(f"{issue.severity.upper()}: {issue.message}")
        if issue.hint:
            print(f"  Hint: {issue.hint}")
```

### Validation Issues

Validation issues have the following structure:

- **path**: JSON path to the problematic field (e.g., `["curated_examples", 0, "spans", 1, "quote"]`)
- **message**: Human-readable error description
- **code**: Machine-friendly error code (e.g., `quote-too-long`, `missing-required`)
- **severity**: `error`, `warning`, or `info`
- **hint**: Optional actionable guidance

### Common Validation Errors

| Code | Description | Solution |
|------|-------------|----------|
| `missing-required` | Required field is missing | Add the required field to the plan |
| `quote-too-long` | Quote exceeds max length | Truncate quote or adjust `PLANNING_MAX_QUOTE_LENGTH` |
| `too-many-examples` | Too many curated examples | Reduce examples or adjust `PLANNING_MAX_CURATED_EXAMPLES` |
| `too-many-spans` | Too many spans per example | Reduce spans to max 6 per example |
| `schema-*` | JSON Schema violation | Check schema requirements |
| `low-diversity` | Multiple examples from same file | Use examples from different files |
| `incomplete-guidance` | schema_guidance appears incomplete | Include TODO placeholder and structured sections |

## Logging & Metrics

### Log Files

All logs are stored in `logs/last_run/`:

- `planning_plan.json`: Most recent Plan JSON with metadata
- `planning_plan.1.json` - `planning_plan.5.json`: Rotated previous plans
- `two_stage_search.json`: Search results and metadata
- `metadata.json`: Applied filters and query information

### Metrics CSV

Metrics are appended to `metrics/plan_runs.csv` with columns:

- `timestamp`: ISO format UTC timestamp
- `query_sha256`: Hash of the query (first 16 chars)
- `status`: `completed`, `no_results`, or `retrying`
- `completion_rate`: Fraction of fields covered (0.00-1.00)
- `stage2_passed`: `true` or `false`
- `retry_count`: Number of retries
- `mode`: `two-requests` or `single-request`
- `notes`: Brief notes or error summary (max 200 chars)

### Using Logging Utils

```python
from agents.logging_utils import persist_plan_json, append_metrics

# Persist plan
plan = {...}
path = persist_plan_json(plan, attempt=1)

# Log metrics
append_metrics(
    query="Create dambreak case",
    status="completed",
    completion_rate=0.85,
    stage2_passed=True,
    retry_count=0,
    mode="two-requests",
    notes="Successfully generated"
)
```

## Development Workflow

### Manual Validation

You can validate Plan JSON files manually:

```bash
python -c "
from agents import validate_plan_json
import json

with open('tests/fixtures/plan_jsons/valid_plan_v1.json') as f:
    plan = json.load(f)

result = validate_plan_json(plan)
print(f'Valid: {result.valid}')
for issue in result.issues:
    print(issue)
"
```

### Running Tests

```bash
# Run all Phase 1 tests
pytest tests/test_planning_phase1.py -v

# Run specific test class
pytest tests/test_planning_phase1.py::TestPlanValidator -v

# Run with coverage
pytest tests/test_planning_phase1.py --cov=agents
```

### Updating Schema Version

When updating the schema:

1. Modify `schemas/planning_agent_schema.json`
2. Update `schema_version` enum to include new version
3. Update `PLANNING_SCHEMA_VERSION` default in `agents/config.py`
4. Add migration logic if needed
5. Update this README

## Troubleshooting

### Validation Failures

**Problem**: `completion_rate < 0.7`

**Solutions**:
- Check if all required fields are in `extracted_params` or acknowledged in `missing_params`
- Review search results to ensure relevant examples were retrieved
- Verify metadata filter is not too restrictive

**Problem**: `quote-too-long` errors

**Solutions**:
- Truncate quotes to fit within `PLANNING_MAX_QUOTE_LENGTH`
- Extract more focused, relevant segments
- Increase `PLANNING_MAX_QUOTE_LENGTH` if quotes are necessarily long

**Problem**: `schema_guidance` incomplete warnings

**Solutions**:
- Include `<<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>` placeholder
- Add structured sections: `[required_fields]`, `[assumptions]`, `[open_questions]`
- Provide specific guidance for Schema Agent

### Stage 2 Failures

If Stage 2 (Schema Agent) repeatedly fails:

1. Check `logs/last_run/planning_plan.json` for `stage2_feedback`
2. Review `schema_guidance` for clarity and completeness
3. Verify `extracted_params` cover essential fields
4. Check `conflicts` for unresolved issues
5. Consider adjusting metadata filters or search parameters

### High Retry Rates

If retry count is consistently high:

1. Review `metrics/plan_runs.csv` for patterns
2. Check if specific queries or case types are problematic
3. Verify vector store contains relevant examples
4. Consider improving metadata filters or search query construction

## Architecture Notes

### Phase 1 Scope

Phase 1 provides the foundation but does NOT implement:
- Actual planning agent logic (Phase 2)
- RAG retrieval integration (Phase 2)
- Schema agent integration (Phase 4)
- Retry mechanisms (Phase 4)

Phase 1 ensures the infrastructure is in place for these future components.

### Future-Proofing

The schema includes optional fields for future enhancements:
- `tool_calls`: For single-request mode with function calling
- `stage2_feedback`: For retry loop integration
- `attempt`: For multi-attempt tracking

These fields are optional now but will be populated in later phases.

## Related Documentation

- `docs/s2_rag_planning_agent.md`: Complete S2 architecture specification
- `schemas/planning_agent_schema.json`: Full JSON Schema definition
- Root `README.md`: Project overview and setup

## Support

For issues or questions:
1. Check this README for common solutions
2. Review test cases in `tests/test_planning_phase1.py` for usage examples
3. Consult the S2 specification in `docs/s2_rag_planning_agent.md`
