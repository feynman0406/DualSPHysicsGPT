from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import json
import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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

    stored_stl = tmp_path / "uploads" / "duck.stl"
    stored_stl.parent.mkdir(parents=True, exist_ok=True)
    stored_stl.write_text("source", encoding="utf-8")
    run_id = "RUN-UNITTEST"

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
        assert "--run-id" in command
        assert command[command.index("--run-id") + 1] == run_id
        assert "--external-stl" in command
        assert command[command.index("--external-stl") + 1] == str(stored_stl)
        assert env["MVP_RUN_ID"] == run_id
        assert env["MVP_EXTERNAL_STL_SOURCE_PATH"] == str(stored_stl)
        assert env["MVP_EXTERNAL_STL_REL_PATH"] == f"uploads/{run_id}/duck.stl"
        output_dir = Path(env["MVP_REDIRECT_ROOT"])
        copied_target = output_dir / Path(env["MVP_EXTERNAL_STL_REL_PATH"])
        copied_target.parent.mkdir(parents=True, exist_ok=True)
        copied_target.write_text("copied", encoding="utf-8")
        (output_dir / "agent1_output.json").write_text("{}", encoding="utf-8")
        (output_dir / "generated_case.xml").write_text("<case />", encoding="utf-8")
        external_dir = output_dir / "external_files" / "AutoXml_script"
        external_dir.mkdir(parents=True, exist_ok=True)
        (external_dir / "dataset.txt").write_text("fixture", encoding="utf-8")
        manifest = {
            "run_id": run_id,
            "generated_at": "2025-11-03T19:08:02Z",
            "files": [
                {
                    "path": "AutoXml_script/dataset.txt",
                    "purpose": "unit test dataset",
                    "source": "declared",
                    "status": "copied",
                    "copied_path": "external_files/AutoXml_script/dataset.txt",
                }
            ],
            "warnings": [],
        }
        (output_dir / "dependency_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="all good", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    monkeypatch.setattr(runner, "collect_resource_snapshot", _snapshot_factory())

    request = RunRequest(
        query="Create a 2D dambreak simulation",
        output_dir=tmp_path,
        env={"CUSTOM_ENV": "1"},
        run_id=run_id,
        external_stl=stored_stl,
    )

    response = runner.run_mvp(request, store=history_store)

    assert response.status is RunStatus.SUCCESS
    assert response.exit_code == 0
    assert response.log_path.exists()
    assert response.log_path.read_text(encoding="utf-8") == "all good"
    assert observed["cwd"] == str(Path(__file__).resolve().parents[2])
    assert "--query" in observed["command"]
    assert observed["env"]["CUSTOM_ENV"] == "1"
    assert response.run_id == run_id

    produced_names = {item.path.name for item in response.produced_files}
    assert {"agent1_output.json", "generated_case.xml", "dependency_manifest.json"} <= produced_names
    stl_files = [item for item in response.produced_files if item.path.suffix.lower() == ".stl"]
    assert stl_files
    assert all(file.description == "Uploaded STL file" for file in stl_files)
    assert any(run_id in file.path.parts for file in stl_files)

    assert response.dependency_manifest is not None
    assert response.dependency_manifest.get("files")
    assert response.dependency_manifest["files"][0]["path"] == "AutoXml_script/dataset.txt"

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
    assert any(artifact.path.endswith(".stl") for artifact in stored.artifacts)
    assert stored.dependency_manifest is not None
    assert stored.dependency_manifest.get("files")
    assert stored.dependency_manifest["files"][0]["path"] == "AutoXml_script/dataset.txt"



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
