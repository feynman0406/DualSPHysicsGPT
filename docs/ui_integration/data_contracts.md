# Data Contracts

Contracts extend the Phase 1 `RunResponse` and related artifacts. Each structure is serialised as JSON for the UI. Fields marked as optional may be omitted when unavailable.

## Run Summary

Source: `ui_backend.runner.run_mvp` response plus derived telemetry.

```json
{
  "run_id": "CASE-20251021-01",
  "query": "Create a 2D dambreak simulation with water height 2 meters",
  "status": "success",
  "exit_code": 0,
  "started_at": "2025-10-21T14:05:12Z",
  "finished_at": "2025-10-21T14:12:44Z",
  "duration_seconds": 452.8,
  "step_status": [
    {"step": "reference_search", "state": "completed", "started_at": "2025-10-21T14:05:12Z", "finished_at": "2025-10-21T14:07:55Z"},
    {"step": "config_generation", "state": "completed", "started_at": "2025-10-21T14:07:55Z", "finished_at": "2025-10-21T14:11:07Z"},
    {"step": "execution", "state": "skipped", "reason": "execute flag false"}
  ],
  "stage_checkpoints": [
    {"stage": "init", "state": "completed", "started_at": "2025-10-21T14:05:12Z", "finished_at": "2025-10-21T14:05:20Z"},
    {"stage": "sim", "state": "completed", "started_at": "2025-10-21T14:05:20Z", "finished_at": "2025-10-21T14:12:00Z"},
    {"stage": "post", "state": "completed", "started_at": "2025-10-21T14:12:00Z", "finished_at": "2025-10-21T14:12:44Z"}
  ],
  "summary": {
    "primary_output": "generated_case.xml",
    "artifact_count": 4,
    "has_failures": false
  }
}
```

Required extensions beyond Phase 1: persistent `run_id` naming, per-step timing (derive from log timestamps), summary helpers, and stage checkpoints capturing the wrapper lifecycle (`init`, `sim`, `post`). Base fields already available from `RunResponse`.

## Log Entry

Logs originate from `mvp_run.log` but should be streamed as structured entries.

```json
{
  "run_id": "CASE-20251021-01",
  "sequence": 42,
  "timestamp_relative": 12.4,
  "timestamp_utc": "2025-10-21T14:05:24.500Z",
  "stream": "stdout",
  "message": "[Step 1/3] Searching vector store..."
}
```

Extensions needed: backend must parse combined stdout and stderr, add relative timestamps, and tag lines by logical stream (stdout, stderr, agent1, agent2) if available.

## Metrics Snapshot

Calculated after run completion or periodically for long runs.

```json
{
  "run_id": "CASE-20251021-01",
  "captured_at": "2025-10-21T14:12:50Z",
  "duration_seconds": 452.8,
  "token_usage": {"input": 45000, "output": 12000, "cost_usd": 3.42},
  "retrieval": {"recall_at_5": 0.8, "total_sources": 15},
  "step_durations": {
    "reference_search": 163,
    "config_generation": 192,
    "execution": 97
  },
  "baseline_delta": {"duration_percent": 0.05, "cost_percent": 0.12},
  "resource_usage": {
    "cpu_percent": 55,
    "memory_percent": 72,
    "gpu": [{"name": "RTX 4090", "utilization_percent": 68}]
  }
}
```

Token usage and cost require OpenAI usage data; retrieval metrics depend on additional instrumentation from Agent 1. Baseline comparisons rely on stored reference metrics (eg from `logs/mvp/reference_run`). Resource usage snapshots encode CPU %, memory %, optional MB counters, detected GPUs, and notes describing the capture trigger. Fallback notes clarify when system tooling is unavailable.

## Artifact Metadata

Derived from Phase 1 `produced_files` plus extra attributes for preview and diff.

```json
{
  "run_id": "CASE-20251021-01",
  "path": "logs/ui_backend/example_run/generated_case.xml",
  "label": "Generated XML case",
  "size_bytes": 7725,
  "sha256": "f36f7fd7...",
  "mime_type": "application/xml",
  "preview_available": true,
  "download_url": "/api/runs/CASE-20251021-01/artifacts/generated_case.xml",
  "baseline_comparable": true
}
```

Phase 1 already exposes `path` and `description`; size, hash, mime type, and serving URL must be added by later backend work. Preview flag enables UI fallbacks for large files.

## Step Detail (per tab)

For the Run Detail view each tab consumes a targeted payload.

```json
{
  "run_id": "CASE-20251021-01",
  "step": "config_generation",
  "overview": {
    "input_prompt": "...",
    "retrieved_references": [
      {"filename": "CaseDambreak2D_Def.json", "score": 0.60},
      {"filename": "CaseDambreak3D_Def.json", "score": 0.58}
    ],
    "parameter_changes": [
      {"path": "geometry.blocks[0].max_z", "from": 1.5, "to": 2.0}
    ]
  },
  "logs": {"first_sequence": 30, "last_sequence": 65},
  "artifacts": ["agent2_config.json"],
  "status": "completed"
}
```

Overview content can be synthesised from `agent1_output.json` and `agent2_config.json`. Parameter diffs will require a comparator service in a later phase.

## Backend Data Gaps

- Structured log streaming with timestamps and stream labels.
- Token usage, cost, and retrieval quality metrics surfaced through the runner or an auxiliary telemetry store.
- Artifact hashing and mime typing so the UI can gate previews and diffing.
- Parameter diff summaries derived from comparing generated config against reference templates.
