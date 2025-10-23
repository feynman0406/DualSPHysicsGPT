from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ui_backend import runner
from ui_backend.history_store import HistoryStore
from ui_backend.models import (
    ResourceUsageSnapshot,
    RunRequest,
    RunStatus,
    StageState,
)


def _snapshot_factory():
    counter = {"value": 0}

    def _factory() -> ResourceUsageSnapshot:
        counter["value"] += 1
        timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(
            seconds=counter["value"]
        )
        return ResourceUsageSnapshot(
            captured_at=timestamp,
            cpu_percent=float(counter["value"]),
            memory_percent=42.0,
            memory_used_mb=123.0,
            memory_total_mb=456.0,
            gpu=[],
            notes=[],
        )

    return _factory


def test_run_mvp_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    observed: dict[str, object] = {}
    store_path = tmp_path / "history.json"
    history_store = HistoryStore(store_path)

    def fake_run(
        command,
        *,
        cwd=None,
        env=None,
        capture_output=None,
        text=None,
        encoding=None,
        errors=None,
        timeout=None,
    ):
        assert capture_output is True
        assert text is True
        observed["command"] = command
        observed["cwd"] = cwd
        observed["env"] = env
        output_dir = Path(env["MVP_REDIRECT_ROOT"])
        (output_dir / "agent1_output.json").write_text("{}", encoding="utf-8")
        (output_dir / "generated_case.xml").write_text("<case />", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="all good", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "collect_resource_snapshot", _snapshot_factory())

    request = RunRequest(
        query="Create a 2D dambreak simulation",
        output_dir=tmp_path,
        env={"CUSTOM_ENV": "1"},
    )

    response = runner.run_mvp(request, store=history_store)

    assert response.status is RunStatus.SUCCESS
    assert response.exit_code == 0
    assert response.log_path.exists()
    assert response.log_path.read_text(encoding="utf-8") == "all good"
    assert observed["cwd"] == str(Path(__file__).resolve().parents[2])
    assert "--query" in observed["command"]
    assert observed["env"]["CUSTOM_ENV"] == "1"
    produced_names = {item.path.name for item in response.produced_files}
    assert {"agent1_output.json", "generated_case.xml"} <= produced_names
    assert response.run_id.startswith("RUN-")

    stages = {stage.stage: stage for stage in response.stage_checkpoints}
    assert set(stages.keys()) == {"init", "sim", "post"}
    assert stages["init"].state == StageState.COMPLETED.value
    assert stages["sim"].state == StageState.COMPLETED.value
    assert stages["post"].state == StageState.COMPLETED.value

    assert len(response.metrics) == 4
    assert response.metrics[0].notes[-1] == "init: starting run"

    stored = history_store.get_run(response.run_id)
    assert stored is not None
    assert stored.status == "success"
    assert len(stored.metrics) == len(response.metrics)
    assert stored.stage_checkpoints[1].state == StageState.COMPLETED.value


def test_run_mvp_missing_env_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    message = "Missing required environment variables: OPENAI_API_KEY"
    store_path = tmp_path / "history.json"
    history_store = HistoryStore(store_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout=message, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "collect_resource_snapshot", _snapshot_factory())

    request = RunRequest(query="hello", output_dir=tmp_path)
    response = runner.run_mvp(request, store=history_store)

    assert response.status is RunStatus.FAILED
    assert response.error is not None
    assert "environment variables" in response.error.message.lower()
    assert message in (response.error.details or "")
    assert response.log_path.read_text(encoding="utf-8") == message

    stages = {stage.stage: stage for stage in response.stage_checkpoints}
    assert stages["sim"].state == StageState.FAILED.value

    stored = history_store.get_run(response.run_id)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.error is not None
    assert "Missing required" in (stored.error.get("details") or "")



