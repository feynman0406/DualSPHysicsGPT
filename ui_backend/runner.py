from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from uuid import uuid4

from .errors import interpret_process_failure
from .history_store import HistoryStore, RunRecord
from .metrics import collect_resource_snapshot
from .models import (
    ErrorInfo,
    ProducedFile,
    ResourceUsageSnapshot,
    RunRequest,
    RunResponse,
    RunStageStatus,
    RunStatus,
    StageState,
)

logger = logging.getLogger(__name__)

_DEFAULT_DESCRIPTIONS = {
    "agent1_output.json": "Agent 1 references & analysis",
    "agent2_config.json": "Agent 2 generated config",
    "generated_case.xml": "Generated XML case",
    "agent2_input.json": "Agent 2 normalized prompt",
    "mvp_run.log": "Console log captured by wrapper",
}

_STAGE_ORDER = ("init", "sim", "post")

_default_history_store: HistoryStore | None = None


def _generate_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:6].upper()
    return f"RUN-{timestamp}-{suffix}"


def _collect_produced_files(output_dir: Path, log_path: Path) -> List[ProducedFile]:
    produced: List[ProducedFile] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path == log_path:
            continue
        description = _DEFAULT_DESCRIPTIONS.get(path.name)
        produced.append(ProducedFile(path=path, description=description))
    return produced


def _build_command(request: RunRequest) -> List[str]:
    return [
        sys.executable,
        "-m",
        "ui_backend._mvp_entry",
        *request.as_argv(),
    ]


def _merge_env(request: RunRequest, repo_root: Path, output_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    if request.env:
        env.update(request.env)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["MVP_REPO_ROOT"] = str(repo_root)
    env["MVP_REDIRECT_ROOT"] = str(output_dir)
    return env


def _resolve_status(exit_code: int) -> RunStatus:
    if exit_code == 0:
        return RunStatus.SUCCESS
    if exit_code < 0:
        return RunStatus.INTERRUPTED
    return RunStatus.FAILED


def _get_history_store(store: HistoryStore | None) -> HistoryStore | None:
    global _default_history_store
    if store is not None:
        return store
    if _default_history_store is None:
        try:
            _default_history_store = HistoryStore()
        except Exception as exc:  # pragma: no cover - defensive guard for filesystem errors
            logger.warning("Unable to initialise default history store: %s", exc)
            _default_history_store = None
    return _default_history_store


def _prepare_stage_checks(
    started_at: datetime,
) -> tuple[dict[str, RunStageStatus], list[RunStageStatus]]:
    stage_map: dict[str, RunStageStatus] = {}
    stage_list: list[RunStageStatus] = []
    for name in _STAGE_ORDER:
        if name == "init":
            status = RunStageStatus(
                stage=name,
                state=StageState.RUNNING.value,
                started_at=started_at,
            )
        else:
            status = RunStageStatus(stage=name, state=StageState.PENDING.value)
        stage_map[name] = status
        stage_list.append(status)
    return stage_map, stage_list


def _stage_sequence(stage_map: dict[str, RunStageStatus]) -> list[RunStageStatus]:
    ordered: list[RunStageStatus] = []
    for name in _STAGE_ORDER:
        if name in stage_map:
            ordered.append(stage_map[name])
    return ordered


def _as_error_dict(error: ErrorInfo | None) -> dict[str, str | None] | None:
    if error is None:
        return None
    return {
        "message": error.message,
        "details": error.details,
        "hint": error.hint,
    }


def _capture_metrics(
    snapshots: list[ResourceUsageSnapshot],
    store: HistoryStore | None,
    run_id: str,
    note: str,
) -> None:
    snapshot = collect_resource_snapshot()
    if note:
        snapshot.notes.append(note)
    snapshots.append(snapshot)
    if store:
        store.append_metrics(run_id, snapshot)


def run_mvp(request: RunRequest, *, store: HistoryStore | None = None) -> RunResponse:
    """Execute the MVP CLI via subprocess and collect structured metadata."""

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = request.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "mvp_run.log"

    command = _build_command(request)
    env = _merge_env(request, repo_root, output_dir)

    started_at = datetime.now(timezone.utc)
    history_store = _get_history_store(store)

    run_id = request.run_id or _generate_run_id()
    stage_map, initial_stage_list = _prepare_stage_checks(started_at)

    initial_snapshot = collect_resource_snapshot()
    initial_snapshot.notes.append("init: starting run")
    metrics_snapshots: list[ResourceUsageSnapshot] = [initial_snapshot]

    if history_store:
        record = RunRecord(
            run_id=run_id,
            query=request.query,
            status="running",
            started_at=started_at,
            output_dir=str(output_dir),
            command=command,
            stage_checkpoints=initial_stage_list,
            metrics=[initial_snapshot],
        )
        history_store.start_run(record)

    # Finish init stage before launching the subprocess.
    init_finished = datetime.now(timezone.utc)
    stage_map["init"] = RunStageStatus(
        stage="init",
        state=StageState.COMPLETED.value,
        started_at=stage_map["init"].started_at,
        finished_at=init_finished,
    )
    if history_store:
        history_store.update_stage(run_id, stage_map["init"])

    _capture_metrics(metrics_snapshots, history_store, run_id, "init: stage complete")

    sim_started = datetime.now(timezone.utc)
    stage_map["sim"] = RunStageStatus(
        stage="sim",
        state=StageState.RUNNING.value,
        started_at=sim_started,
    )
    if history_store:
        history_store.update_stage(run_id, stage_map["sim"])

    completed: subprocess.CompletedProcess[str] | None = None
    run_exception: Exception | None = None
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=request.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(
            command,
            -1,
            stdout=exc.stdout or "",
            stderr=exc.stderr or str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive but unlikely path
        run_exception = exc

    if run_exception is not None:
        sim_finished = datetime.now(timezone.utc)
        stage_map["sim"] = RunStageStatus(
            stage="sim",
            state=StageState.FAILED.value,
            started_at=sim_started,
            finished_at=sim_finished,
            message=str(run_exception),
        )
        if history_store:
            history_store.update_stage(run_id, stage_map["sim"])
        raise run_exception

    assert completed is not None

    combined_output = (completed.stdout or "") + (completed.stderr or "")
    log_path.write_text(combined_output, encoding="utf-8")

    finished_at = datetime.now(timezone.utc)
    run_status = _resolve_status(completed.returncode)
    sim_state = (
        StageState.COMPLETED.value
        if run_status is RunStatus.SUCCESS
        else StageState.FAILED.value
    )
    stage_map["sim"] = RunStageStatus(
        stage="sim",
        state=sim_state,
        started_at=sim_started,
        finished_at=finished_at,
    )
    if history_store:
        history_store.update_stage(run_id, stage_map["sim"])

    _capture_metrics(metrics_snapshots, history_store, run_id, "sim: stage complete")

    post_started = datetime.now(timezone.utc)
    stage_map["post"] = RunStageStatus(
        stage="post",
        state=StageState.RUNNING.value,
        started_at=post_started,
    )
    if history_store:
        history_store.update_stage(run_id, stage_map["post"])

    produced_files = _collect_produced_files(output_dir, log_path)

    post_finished = datetime.now(timezone.utc)
    post_state = StageState.COMPLETED.value
    stage_map["post"] = RunStageStatus(
        stage="post",
        state=post_state,
        started_at=post_started,
        finished_at=post_finished,
    )
    if history_store:
        history_store.update_stage(run_id, stage_map["post"])

    _capture_metrics(metrics_snapshots, history_store, run_id, "post: stage complete")

    error: ErrorInfo | None = None
    if run_status is not RunStatus.SUCCESS:
        error = interpret_process_failure(completed.returncode, combined_output)

    if history_store:
        history_store.append_artifacts(run_id, produced_files)
        history_store.complete_run(
            run_id,
            status=run_status.value,
            finished_at=post_finished,
            exit_code=completed.returncode,
            artifacts=produced_files,
            error=_as_error_dict(error),
        )

    return RunResponse(
        status=run_status,
        exit_code=completed.returncode,
        started_at=started_at,
        finished_at=post_finished,
        command=command,
        log_path=log_path,
        output_dir=output_dir,
        run_id=run_id,
        produced_files=produced_files,
        error=error,
        stage_checkpoints=_stage_sequence(stage_map),
        metrics=metrics_snapshots,
    )







