# Agent Quick Reference - DualSPHysicsGPT

**Purpose**: This document provides essential context for AI agents working on this project, eliminating the need to re-read multiple files.

## Project Overview

**DualSPHysicsGPT** generates DualSPHysics simulation configuration XML files from natural language queries using LLMs and RAG.

**Current Implementation**: Two-stage RAG + Planning Agent system (Phase 2 complete)

## Critical File Locations

### Core Workflow Files
```
chains/generator.py          # Main entry point: generator_chain()
chains/json_normalizer.py    # Normalizes JSON config before XML conversion
chains/rag_utils.py          # RAG utilities: build_metadata_filter(), persist_sources()
```

### LLM & RAG
```
llm/client.py                # llm_call(), get_model_name(), get_openai_client()
rag/openai_file_search.py   # response_with_file_search(), get_last_run_info()
rag/vector_stores.json       # Vector store IDs (vs_68cc41440b9c8191bb5ef0fce9c4417f)
```

### Planning Agent System (Phase 2)
```
agents/planning_agent.py     # Stage 1: run_planning_agent()
agents/schema_agent.py       # Stage 2: run_schema_agent()
agents/example_scorer.py     # 4D scoring: Algorithm, Geometry, Boundary, Execution
agents/quote_extractor.py    # Smart quote extraction with length limits
agents/config.py             # PlanningAgentSettings, load_planning_settings()
agents/plan_validator.py     # validate_plan_json()
```

### Schemas
```
schemas/dualsphysics_config_schema.json  # Main config schema
schemas/planning_agent_schema.json       # Plan JSON schema (from Phase 1)
```

### Configuration Files
```
AutoXml_script/config_library/*.json     # Example configurations (source for RAG)
AutoXml_script/generate_xml.py          # generate_case_xml() - JSON to XML converter
```

### Logs & Metrics
```
logs/last_run/planning_plan.json    # Plan JSON output from Stage 1
logs/last_run/metadata.json         # File search metadata
logs/last_run/sources.json          # Retrieved source documents
logs/mvp/agent1_output.json         # Agent 1 metadata-only reference list
logs/mvp/agent2_input.json          # Agent 2 payload with resolved local snippets
metrics/plan_runs.csv               # Planning metrics tracking
```

## Key Environment Variables

### Two-Stage Workflow Control
```bash
USE_TWO_STAGE_RAG_SCHEMA=1        # Enable two-stage mode
USE_RAG_PLANNING_AGENT=1          # Enable Planning Agent in Stage 1
USE_RAG=1                         # Enable RAG system
```

### OpenAI Configuration
```bash
OPENAI_API_KEY=xxx
OPENAI_MODEL=gpt-4o              # Default model
OPENAI_MODEL_RESPONSES=gpt-4o    # For Responses API
OPENAI_RAG_VS_DESIGN_ID=vs_xxx   # Vector store ID (fixed: vs_68cc41440b9c8191bb5ef0fce9c4417f)
```

### JSON Schema Control
```bash
DSPH_USE_JSON_SCHEMA=1           # Enable JSON schema mode
DSPH_STRICT_JSON_SCHEMA=1        # Enable strict schema enforcement
DSPH_FORBID_XML_FALLBACK=1       # Forbid XML fallback (fail if JSON fails)
```

### Planning Agent Settings (Optional)
```bash
PLANNING_AGENT_MODE=two-requests           # or "single-request"
PLANNING_MAX_CURATED_EXAMPLES=12          # Max examples in Plan JSON
PLANNING_MAX_QUOTE_LENGTH=400             # Max characters per quote
PLANNING_SCHEMA_VERSION=1.0
```

### Debug
```bash
DSPH_DEBUG=1                     # Enable detailed logging
```

## Main Execution Flows

### 1. Standard Single-Stage (Legacy)
```
User Query ??generator_chain() ??LLM (with RAG context) ??JSON/XML ??Output
```

### 2. Two-Stage with Planning Agent (Phase 2)
```
User Query 
  ??
Stage 0: OpenAI file_search retrieval (max_num_results=3)
  ??
Stage 1: Planning Agent (run_planning_agent)
  - Score examples (4 dimensions, 1-5 scale)
  - Extract quotes (<400 chars each, max 3 per file)
  - Extract parameters
  - Detect coverage & gaps
  - Generate Plan JSON ??logs/last_run/planning_plan.json
  ??
Stage 2: Schema Agent (run_schema_agent)
  - Load Plan JSON
  - Build prompt with evidence + schema_guidance
  - Call OpenAI with strict JSON schema
  - Generate config JSON
  ??
Post-processing
  - Normalize JSON (json_normalizer)
  - Generate XML (generate_case_xml)
  - Sanitize XML (sanitize_newvarcte)
  ??
Output: XML + config + sources + metadata
```

### 3. Fallback Behavior
- If two-stage fails ??automatically falls back to single-stage
- Logs error when DSPH_DEBUG=1

## Critical Data Structures

### Plan JSON Schema (Stage 1 Output)
```json
{
  "query": "string (max 4000)",
  "metadata_filter": {"case_type": "dambreak", "dim": "2D"},
  "curated_examples": [
    {
      "filename": "CaseDambreak_Def.json",
      "rank": 1,
      "score": 0.85,
      "rationale": "Algorithm=5, Geometry=4, Boundary=4, Execution=5 ??...",
      "spans": [
        {"quote": "...", "start": 0, "end": 100}
      ]
    }
  ],
  "coverage": {
    "case_type": "dambreak",
    "dim": "2D",
    "features": ["mDBC", "floating"]
  },
  "extracted_params": [
    {"name": "execution.parameters.TimeMax", "value": 2.0, "unit": "s", "source": "file.json"}
  ],
  "missing_params": ["execution.parameters.Kernel"],
  "conflicts": ["Dimension mismatch: query says 3D but examples are 2D"],
  "schema_guidance": "<<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>\n[required_fields]...",
  "citations": [...]
}
```

### Config JSON Schema (Stage 2 Output)
See `schemas/dualsphysics_config_schema.json` - Full DualSPHysics configuration

## Key Functions & Their Signatures

### Generator Chain
```python
def generator_chain(
    user_query: str,
    *,
    freeze_retrieval: bool = False,
    frozen_docs: Optional[List[Document]] = None
) -> Dict[str, Any]:
    """
    Returns: {
        "xml": str,
        "config": Dict (optional),
        "sources": List[Document],
        "structured_meta": Dict (optional),
        "warnings": List[str] (optional)
    }
    """
```

### Two-Stage Workflow (Internal)
```python
def _two_stage_workflow(user_query: str) -> Dict[str, Any]:
    """
    Executes:
    1. File search retrieval
    2. Planning Agent
    3. Schema Agent
    4. XML generation
    
    Raises RuntimeError on failure (fallback handles it)
    """
```

### Planning Agent
```python
def run_planning_agent(
    user_query: str,
    vector_store_ids: List[str],
    metadata_filter: Optional[Dict[str, Any]] = None,
    retry_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Returns Plan JSON (see schema above)"""
```

### Schema Agent
```python
def run_schema_agent(
    plan_json: Dict[str, Any],
    user_query: str,
    schema: Dict[str, Any],
    llm_client: Any,  # OpenAI client
    model: str,
    temperature: float = 0.0
) -> Dict[str, Any]:
    """Returns config JSON matching dualsphysics_config_schema.json"""
```

### LLM Call
```python
def llm_call(
    messages: List[Dict[str, str]],  # [{"role": "system/user/assistant", "content": "..."}]
    model: str,
    reasoning: Optional[Dict[str, str]] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 20480,
    stop: Optional[List[str]] = None,
    file_search_vs_ids: Optional[List[str]] = None,
    metadata_filter: Optional[Dict[str, Any]] = None,
    json_schema: Optional[Dict[str, Any]] = None,
    strict: bool = False
) -> str:
    """Universal LLM call supporting OpenAI and OpenRouter"""
```

### File Search
```python
def response_with_file_search(
    messages: List[Dict[str, Any]],
    model: str,
    vector_store_ids: List[str],
    metadata_filter: Optional[Dict[str, Any]] = None,
    max_output_tokens: int = 8000,
    query_rewrite: bool = True,
    temperature: Optional[float] = None,
    reasoning: Optional[Dict[str, Any]] = None
) -> str:
    """
    OpenAI Responses API with file_search.
    Auto-logs to logs/last_run/metadata.json
    """
```

## Scoring System (Planning Agent)

### 4 Dimensions (1-5 scale each)
1. **Algorithm**: Workflow and main commands reusability (1=can't reuse, 5=direct reuse)
2. **Geometry**: Dimension and fill requirements match (1=major redesign, 5=perfect fit)
3. **Boundary/Materials**: mk, boundary conditions, floating body compatibility
4. **Execution**: Parameters, gauges, timeout settings

### Aggregate Score
- Simple arithmetic mean of 4 dimensions
- Used to rank curated examples
- Stored in `curated_examples[*].rationale`

### Quote Extraction Rules
- Max length: 400-600 chars per quote
- Max quotes per file: 3
- Diversity: prefer different filenames
- Priority: based on adjustments needed (from scoring)

## Common Patterns

### Checking Two-Stage Mode
```python
def _use_two_stage_rag() -> bool:
    return (
        os.environ.get("USE_TWO_STAGE_RAG_SCHEMA", "0") == "1" and
        os.environ.get("USE_RAG_PLANNING_AGENT", "0") == "1"
    )
```

### Loading Schema
```python
from chains.generator import _load_json_schema
schema = _load_json_schema()  # Cached, loads from schemas/dualsphysics_config_schema.json
```

### Getting OpenAI Client
```python
from llm.client import get_openai_client
client = get_openai_client()  # Returns OpenAI client instance
```

### Validating Plan JSON
```python
from agents.plan_validator import validate_plan_json
is_valid, errors = validate_plan_json(plan_json)
if not is_valid:
    print(f"Validation errors: {errors}")
```

### Building Metadata Filter
```python
from chains.rag_utils import build_metadata_filter
metadata_filter = build_metadata_filter(user_query)
# Returns: {"case_type": "dambreak", "dim": "2D"} or similar
```

## Testing Conventions

### Test File Locations
```
tests/test_planning_agent.py          # Planning Agent unit tests (NOT YET CREATED)
tests/test_schema_agent.py            # Schema Agent unit tests (NOT YET CREATED)
tests/test_two_stage_pipeline.py      # End-to-end tests (NOT YET CREATED)
tests/test_planning_phase1.py         # Phase 1 tests (EXISTS)
tests/test_generator_json_pipeline.py # Generator pipeline tests (EXISTS)
```

### Running Tests
```bash
# All tests
pytest

# Specific test file
pytest tests/test_planning_phase1.py

# With verbose output
pytest -v

# Quick mode (quiet)
pytest -q
```

## Vector Store Details

### Fixed Configuration
- **Vector Store ID**: `vs_68cc41440b9c8191bb5ef0fce9c4417f`
- **Source Files**: `AutoXml_script/config_library/*.json`
- **File Count**: ~18 example configurations
- **Chunk Strategy**: No chunking (full files)
- **Top-k**: 3 (fixed, cannot retry)

### Metadata Filter Structure
```json
{
  "case_type": "dambreak|sloshing|floating|wavemaker|damping",
  "dim": "2D|3D",
  "features": "mDBC|floating|waves|damping"  // Optional
}
```

## Known Limitations (Phase 2)

### Not Yet Implemented
- ??Retry mechanism (`agents/retry_manager.py`)
- ??Automated metrics tracking (`agents/metrics_tracker.py`)
- ??Comprehensive unit tests for new components
- ??Complete user documentation in main README

### Potential Issues
1. **File path resolution**: Assumes files in `AutoXml_script/config_library/`
2. **Quote extraction**: Simple XML parsing may not handle deep nesting
3. **No retry logic**: Falls back to single-stage on Schema Agent failure
4. **Limited error recovery**: Many exceptions cause workflow failure

### Performance Characteristics
- **Planning Agent**: ~2-5s (no LLM calls, just processing)
- **Schema Agent**: ~3-8s (one LLM call with strict schema)
- **Total overhead**: ~2-3x single-stage latency
- **Token usage**: +1000-3000 tokens for Schema Agent prompt

## Quick Debugging Checklist

### If Two-Stage Not Working
1. Check environment variables: `USE_TWO_STAGE_RAG_SCHEMA=1` and `USE_RAG_PLANNING_AGENT=1`
2. Check vector store ID: `OPENAI_RAG_VS_DESIGN_ID` set correctly
3. Enable debug: `DSPH_DEBUG=1`
4. Check logs: `logs/last_run/planning_plan.json` exists and valid
5. Check fallback: Look for "Two-stage workflow failed" in output

### If Plan JSON Invalid
1. Check schema: `schemas/planning_agent_schema.json`
2. Validate: Use `validate_plan_json()` function
3. Check lengths: quotes < 600 chars, query < 4000 chars
4. Check arrays: curated_examples < 12, extracted_params < 64

### If Schema Agent Fails
1. Check Plan JSON structure
2. Verify schema compatibility: `schemas/dualsphysics_config_schema.json`
3. Check model supports structured outputs: gpt-4o, gpt-4o-mini
4. Review schema_guidance content
5. Check for missing required fields

## Code Style & Conventions

### Imports
```python
from __future__ import annotations  # At top of file
from typing import Any, Dict, List, Optional, Tuple  # Type hints
```

### Logging
```python
import logging
LOGGER = logging.getLogger(__name__)

# Usage
LOGGER.info(f"Stage 1 complete: {len(examples)} examples")
LOGGER.warning(f"File not found: {path}")
LOGGER.error(f"Planning failed: {exc}", exc_info=True)
```

### Error Handling
```python
try:
    result = risky_operation()
except Exception as exc:
    LOGGER.error(f"Operation failed: {exc}", exc_info=True)
    raise RuntimeError(f"Detailed error message: {exc}") from exc
```

### Type Hints
- Always use type hints for function parameters and return values
- Use `Optional[Type]` for nullable values
- Use `Dict[str, Any]` for flexible dictionaries
- Use `List[Type]` for homogeneous lists

## Quick Start for New Agents

### Reading This Project
1. **Start here**: This document (AGENT_QUICK_REFERENCE.md)
2. **Understand goals**: `docs/s2_rag_planning_agent.md` (Chinese, detailed spec)
3. **See implementation**: `docs/s2_phase2_implementation_summary.md`
4. **Check schemas**: `schemas/planning_agent_schema.json` and `schemas/dualsphysics_config_schema.json`

### Making Changes
1. **Always check**: Does two-stage mode need to be enabled?
2. **Test locally**: Enable `DSPH_DEBUG=1` and check logs
3. **Validate schemas**: Use existing validators before LLM calls
4. **Preserve fallback**: Don't break single-stage workflow
5. **Update docs**: If adding features, update this file

### Common Tasks
- **Add new scoring dimension**: Modify `agents/example_scorer.py`
- **Change quote extraction**: Modify `agents/quote_extractor.py`
- **Adjust metadata filter**: Modify `chains/rag_utils.py`
- **Add metrics**: Modify `metrics/plan_runs.csv` structure
- **Change schema**: Update both JSON schema files and validators

## Version History

- **Phase 1** (Completed): Planning Agent schema and validation infrastructure
- **Phase 2** (Completed): Planning Agent core logic, Schema Agent, two-stage integration
- **Phase 2.4** (TODO): Retry mechanism
- **Phase 2.5** (Partial): Metrics tracking structure created
- **Phase 2.6** (TODO): Comprehensive automated testing
- **Phase 2.7** (TODO): Complete user documentation

---

**Last Updated**: January 10, 2025  
**Status**: Phase 2 Complete, Ready for Testing  
**Next Priority**: Retry mechanism (Phase 2.4) and automated tests (Phase 2.6)
