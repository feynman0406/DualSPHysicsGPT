#!/usr/bin/env python3
"""Reconstruct ui_backend/data/run_history.json from logs/ui_backend/runs."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO_ROOT / "logs" / "ui_backend" / "runs"
HISTORY_PATH = REPO_ROOT / "ui_backend" / "data" / "run_history.json"

_DEFAULT_DESCRIPTIONS = {
    "agent1_output.json": "Agent 1 references & analysis",
    "agent2_config.json": "Agent 2 generated config",
    "generated_case.xml": "Generated XML case",
    "agent2_input.json": "Agent 2 normalized prompt",
    "mvp_run.log": "Console log captured by wrapper",
}

STATUS_KEYWORDS = [
    ("SUCCESS!", "success"),
    ("FAILED!", "failed"),
    ("INTERRUPTED", "interrupted"),
]

TOTAL_DURATION_RE = re.compile(r"Total elapsed\s+([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)
MODEL_RE = re.compile(r"^Model:\s*(.+)$", re.MULTILINE)
QUERY_RE = re.compile(r"^Query:\s*(.+)$", re.MULTILINE)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def _load_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _detect_status(log_text: str) -> str:
    normalized = log_text.upper()
    for marker, status in STATUS_KEYWORDS:
        if marker in normalized:
            return status
    if "SUCCESS" in normalized:
        return "success"
    return "failed"


def _parse_duration(log_text: str) -> float | None:
    match = TOTAL_DURATION_RE.search(log_text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_model(log_text: str) -> str | None:
    match = MODEL_RE.search(log_text)
    if match:
        candidate = match.group(1).strip()
        if candidate:
            return candidate
    return None


def _parse_query(run_dir: Path, log_text: str) -> str:
    agent1_path = run_dir / "agent1_output.json"
    payload = _load_json(agent1_path)
    if isinstance(payload, dict):
        query = payload.get("query")
        if isinstance(query, str) and query.strip():
            return query.strip()
    match = QUERY_RE.search(log_text)
    if match:
        candidate = match.group(1).strip()
        if candidate:
            return candidate
    return "Unknown query"


def _artifact_description(path: Path, run_dir: Path) -> str | None:
    description = _DEFAULT_DESCRIPTIONS.get(path.name)
    if description:
        return description
    if path.suffix.lower() == ".stl":
        try:
            relative = path.relative_to(run_dir)
        except ValueError:
            relative = None
        if relative is None or (relative.parts and relative.parts[0] == "uploads"):
            return "Uploaded STL file"
    return None


def _collect_artifacts(run_dir: Path, log_path: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path == log_path:
            continue
        description = _artifact_description(path, run_dir)
        artifacts.append({"path": str(path.resolve()), "description": description})
    return artifacts


def _load_dependency_manifest(run_dir: Path) -> dict[str, Any] | None:
    manifest_path = run_dir / "dependency_manifest.json"
    data = _load_json(manifest_path)
    if isinstance(data, dict) and data:
        return data
    return None


def _build_stage_checks(started: datetime, finished: datetime, status: str) -> list[dict[str, Any]]:
    init_finish = min(finished, started + timedelta(seconds=1))
    sim_state = "completed" if status == "success" else "failed"
    return [
        {
            "stage": "init",
            "state": "completed",
            "started_at": _iso(started),
            "finished_at": _iso(init_finish),
        },
        {
            "stage": "sim",
            "state": sim_state,
            "started_at": _iso(init_finish),
            "finished_at": _iso(finished),
        },
        {
            "stage": "post",
            "state": "completed",
            "started_at": _iso(finished),
            "finished_at": _iso(finished),
        },
    ]


def _summarize_error(log_text: str) -> dict[str, str | None]:
    tail = "\n".join(log_text.strip().splitlines()[-40:])
    tail = tail[-4000:]
    return {
        "message": "Run completed outside history store; see log tail.",
        "details": tail,
        "hint": "Inspect mvp_run.log for the full error context.",
    }


@dataclass
class RecoveredRun:
    payload: dict[str, Any]
    sort_key: datetime


def _recover_run(run_dir: Path) -> RecoveredRun | None:
    log_path = run_dir / "mvp_run.log"
    log_text = _load_log(log_path)
    if not log_text:
        return None

    status = _detect_status(log_text)
    finish_ts = log_path.stat().st_mtime if log_path.exists() else run_dir.stat().st_mtime
    finished_at = datetime.fromtimestamp(finish_ts, timezone.utc)

    duration = _parse_duration(log_text)
    if duration is None:
        start_ts = run_dir.stat().st_ctime
        started_at = datetime.fromtimestamp(start_ts, timezone.utc)
    else:
        started_at = finished_at - timedelta(seconds=duration)
    if started_at > finished_at:
        started_at = finished_at

    query = _parse_query(run_dir, log_text)
    model_name = _parse_model(log_text)
    artifacts = _collect_artifacts(run_dir, log_path)
    dependency_manifest = _load_dependency_manifest(run_dir)

    command = [
        "python",
        "-m",
        "ui_backend._mvp_entry",
        "--query",
        query,
        "--run-id",
        run_dir.name,
    ]

    record: dict[str, Any] = {
        "run_id": run_dir.name,
        "query": query,
        "status": status,
        "started_at": _iso(started_at),
        "finished_at": _iso(finished_at),
        "exit_code": 0 if status == "success" else None,
        "output_dir": str(run_dir.resolve()),
        "command": command,
        "model_name": model_name,
        "reasoning_config": None,
        "reasoning_level": None,
        "artifacts": artifacts,
        "stage_checkpoints": _build_stage_checks(started_at, finished_at, status),
        "metrics": [],
        "error": None if status == "success" else _summarize_error(log_text),
        "dependency_manifest": dependency_manifest,
        "created_at": _iso(started_at),
        "updated_at": _iso(finished_at),
    }

    return RecoveredRun(payload=record, sort_key=started_at)


def main() -> int:
    if not RUNS_ROOT.exists():
        print(f"Run directory {RUNS_ROOT} does not exist", file=sys.stderr)
        return 1

    recovered: list[RecoveredRun] = []
    missing_logs: list[str] = []

    for run_dir in sorted(RUNS_ROOT.iterdir()):
        if not run_dir.is_dir():
            continue
        run = _recover_run(run_dir)
        if run is None:
            missing_logs.append(run_dir.name)
            continue
        recovered.append(run)

    recovered.sort(key=lambda entry: entry.sort_key)
    runs_payload = [entry.payload for entry in recovered]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps({"runs": runs_payload}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Rebuilt history with {len(runs_payload)} runs -> {HISTORY_PATH}")
    if missing_logs:
        print("Skipped runs without logs:", ", ".join(missing_logs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
