# MVP Runner API Contract

The UI backend exposes the MVP DualSPHysics pipeline through the `ui_backend.runner` module. The
contract focuses on a single entry point that wraps `scripts/mvp_direct_file_search.py` without
touching the original MVP source code.

## Entry Point

```python
from pathlib import Path
from ui_backend.runner import run_mvp
from ui_backend.models import RunRequest

request = RunRequest(
    query="Create a 2D dambreak simulation with water height 2 meters",
    pause_after_agent1=False,
    execute=False,
    model_name="gpt-5-mini",
    output_dir=Path("logs/ui_backend/example_run"),
)
response = run_mvp(request)
```

The wrapper launches the MVP CLI in a subprocess (`python -m ui_backend._mvp_entry`). Output paths
under `logs/mvp/` are transparently re-routed into the caller-provided `output_dir`. Existing
artifacts in `logs/mvp/` remain untouched.

## Request Schema (`RunRequest`)

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | `str` | Yes | User request forwarded to the MVP CLI `--query` flag. |
| `output_dir` | `Path` | Yes | Destination directory for log capture and redirected MVP artifacts. Created automatically. |
| `pause_after_agent1` | `bool` | No | Mirrors `--pause-after-agent1`; pauses after Agent 1 when `True`. Defaults to `False`. |
| `execute` | `bool` | No | Mirrors `--execute`; runs GenCase when `True`. Defaults to `False`. |
| `model_name` | `str | None` | No | Optional model override propagated via `OPENAI_MODEL`. UI posts `model` when set. |
| `timeout` | `float | None` | No | Optional wall-clock timeout passed to `subprocess.run`. |
| `env` | `dict[str, str] | None` | No | Additional environment variables merged into the subprocess environment. |
| `external_stl` | `Path \| None` | No | Optional resolved path to the uploaded STL copied into the run workspace. |

All requests must ensure `OPENAI_API_KEY` and `OPENAI_RAG_VS_DESIGN_ID` are available via the current
process environment or the optional `env` override.
When the UI uploads an external STL, `/api/runs` expects a `multipart/form-data` payload with the `externalStl` file field alongside the JSON fields (`query`, `pauseAfterAgent1`, `execute`, optional `model`).

## Response Schema (`RunResponse`)

| Field | Type | Description |
| --- | --- | --- |
| `status` | `RunStatus` enum (`success`, `failed`, `interrupted`) | Overall execution outcome derived from the subprocess exit code. |
| `exit_code` | `int` | Raw exit code returned by the MVP CLI. Negative values indicate termination by signal. |
| `started_at` / `finished_at` | `datetime` | UTC timestamps captured immediately before and after the subprocess execution. |
| `command` | `Sequence[str]` | Exact command that was executed (`python -m ui_backend._mvp_entry ?`). |
| `modelName` | `str | None` | Model recorded with the run (UI selection or backend default). |
| `log_path` | `Path` | Location of the combined stdout/stderr log (`mvp_run.log`). |
| `output_dir` | `Path` | Folder containing the redirected MVP artifacts and log. |
| `produced_files` | `list[ProducedFile]` | Discovered output files (recursively) excluding the log file. Each record includes the absolute `Path` and an optional friendly description. |
| `dependency_manifest` | `dict[str, object] | None` | Normalized dependency manifest for the run; see *Dependency Manifest* below. |
| `error` | `ErrorInfo | None` | Present when `status != success`; contains human-readable message, raw details, and remediation hint. |
| `duration_seconds` (property) | `float` | Convenience accessor returning the elapsed duration in seconds. |

- Summaries returned by `/api/runs` include:
  - `summary.externalStl` (filename + size metadata) and `summary.externalStlAttached` so the UI can highlight runs that included user geometry.
  - `summary.dependencyCount` and `summary.dependencyWarnings` derived from the dependency manifest.

### Produced File Descriptions

When present, the following artifacts receive canned descriptions:

- `agent1_output.json` ??"Agent 1 references & analysis"
- `agent2_config.json` ??"Agent 2 generated config"
- `generated_case.xml` ??"Generated XML case"
- `agent2_input.json` ??"Agent 2 normalized prompt"

Any additional files are surfaced without a predefined description. Directory entries are ignored.

### Dependency Manifest

Every run writes `dependency_manifest.json` next to the redirected MVP artifacts and mirrors referenced files under `external_files/`. The manifest captures:

- `run_id` and `generated_at` metadata for traceability.
- `files[]` entries describing each dependency. Entries are sorted by `path` and expose:
  - `path`: repo-relative or run-relative location reported by the agents or inferred from XML.
  - `purpose`: optional description supplied by Agent 2.
  - `source`: `declared`, `xml`, or `external_stl`.
  - `status`: `copied`, `available`, or `missing`.
  - `copied_path`: run-relative path when the file was copied into `external_files/`.
  - `notes`: optional list capturing copy warnings.
- `warnings`: aggregate issues (e.g., missing assets).

The UI now renders dependency badges using `summary.dependencyCount`/`summary.dependencyWarnings` and builds download links from `files[].copied_path` via `/api/runs/{run_id}/artifacts/content`. Repo-managed assets should live under AutoXml_script/external_assets/ (or other repo-relative paths) so the collector can resolve and copy them into each run's workspace.


The backend persists the manifest in run history and surfaces it via `RunResponse.dependency_manifest` and the `/runs/{run_id}/dependencies` endpoint.

## Error Translation

`ui_backend.errors.interpret_process_failure` interprets the subprocess exit code and textual output.
It currently recognises the following situations:

| Trigger | User-Facing Message | Hint |
| --- | --- | --- |
| Output contains "missing required environment variables" | "Required MVP environment variables are missing" | "Ensure OPENAI_API_KEY and OPENAI_RAG_VS_DESIGN_ID are set before running." |
| Output contains "httpx" | "HTTP client reported an error during OpenAI request" | "Check network connectivity and OpenAI service availability." |
| Output contains "openai" | "OpenAI API returned an error" | "Review the logs for specific API response details." |
| Exit code < 0 | "Process terminated by signal" | "Inspect system logs for the signal source." |
| Fallback | "MVP pipeline failed with an unknown error" | "Review the log output for clues or rerun with DEBUG logging." |

The full combined stdout/stderr transcript is preserved in `RunResponse.log_path` for debugging.

## Example Outcomes

### Successful Run

```json
{
  "status": "success",
  "exit_code": 0,
  "log_path": "logs/ui_backend/example_run/mvp_run.log",
  "produced_files": [
    {"path": "logs/ui_backend/example_run/agent1_output.json", "description": "Agent 1 references & analysis"},
    {"path": "logs/ui_backend/example_run/generated_case.xml", "description": "Generated XML case"}
  ]
}
```

### Missing Environment Variable

```json
{
  "status": "failed",
  "exit_code": 1,
  "error": {
    "message": "Required MVP environment variables are missing",
    "hint": "Ensure OPENAI_API_KEY and OPENAI_RAG_VS_DESIGN_ID are set before running."
  },
  "log_path": "logs/ui_backend/example_run/mvp_run.log"
}
```

Clients must always inspect `status` before consuming produced artifacts. On failure the redirected
output directory may contain partial files.
## Stage Checkpoints & Metrics Snapshots

The wrapper now enriches `RunResponse` with structured execution telemetry:

- `run_id`: stable identifier persisted in the history store.
- `stage_checkpoints`: ordered list covering `init`, `sim`, and `post` stages. Each checkpoint tracks the stage name, lifecycle state (`pending`, `running`, `completed`, `failed`), UTC start/finish timestamps, and optional message for failures.
- `metrics`: collection of resource usage snapshots captured throughout the run. Every snapshot records capture time, CPU percent, memory utilisation (percent and absolute MB), detected GPU devices (name, utilisation, memory), plus free-form notes describing the trigger (eg `init: starting run`).

Client integrations should prefer `stage_checkpoints` for rendering segmented progress indicators and use the most recent `metrics` entry for resource widgets. Snapshots are appended at key transitions (post-initialisation, post-simulation, post-processing) and fall back gracefully when system tools are unavailable (eg `psutil` or `nvidia-smi`).
## Run History Endpoints

The UI backend surfaces read-only endpoints backed by `HistoryStore`.

- `GET /runs`: List recent runs (sorted by `startedAt` descending). Each entry includes run metadata, optional summary (artifact count, primary output, dependency counts/warnings), and `stageCheckpoints` for the init/sim/post lifecycle.
- `GET /runs/{run_id}`: Retrieve a single run summary using the same shape as the list endpoint. Returns 404 when the identifier is unknown.
- `GET /runs/{run_id}/dependencies`: Return the persisted dependency manifest as JSON or HTTP 204 when no manifest is available.
- `GET /runs/{run_id}/metrics`: Returns `{runId, capturedAt, durationSeconds, resourceUsage[]}` and responds with HTTP 204 when telemetry snapshots are unavailable.
- `GET /runs/{run_id}/artifacts`: Enumerates persisted artifacts with `path`, optional label/description, and echoes the `runId`.

Future phases may expose log streaming and artifact content helpers, but the MVP UI can poll the above resources without modifying the DualSPHysics CLI.







