from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import pytest

from ui_backend.api import create_router
from ui_backend.history_store import HistoryStore, RunRecord, StoredArtifact
from ui_backend.models import ResourceUsageSnapshot, RunStageStatus, StageState


def _build_record(run_id: str, start: datetime, output_dir: Path) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        query="demo",
        status="running",
        started_at=start,
        finished_at=None,
        exit_code=None,
        output_dir=str(output_dir),
        command=["python", "-m", "demo"],
        artifacts=[],
        stage_checkpoints=[],
        metrics=[],
        error=None,
    )


def _prepare_store(tmp_path: Path) -> HistoryStore:
    store_path = tmp_path / "history.json"
    store = HistoryStore(store_path)

    run1_output = tmp_path / "output"
    run1_output.mkdir(parents=True, exist_ok=True)
    artifact_file = run1_output / "generated_case.xml"
    artifact_file.write_text("<xml>example</xml>\n", encoding="utf-8")

    started = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    record = _build_record("RUN-1", started, run1_output)
    store.start_run(record)

    store.update_stage(
        "RUN-1",
        RunStageStatus(
            stage="init",
            state=StageState.COMPLETED.value,
            started_at=started,
            finished_at=started + timedelta(seconds=8),
            message=None,
        ),
    )
    store.update_stage(
        "RUN-1",
        RunStageStatus(
            stage="sim",
            state=StageState.COMPLETED.value,
            started_at=started + timedelta(seconds=8),
            finished_at=started + timedelta(minutes=7),
            message=None,
        ),
    )
    store.update_stage(
        "RUN-1",
        RunStageStatus(
            stage="post",
            state=StageState.COMPLETED.value,
            started_at=started + timedelta(minutes=7),
            finished_at=started + timedelta(minutes=7, seconds=40),
            message=None,
        ),
    )

    snapshot = ResourceUsageSnapshot(
        captured_at=started + timedelta(seconds=10),
        cpu_percent=55.0,
        memory_percent=72.0,
        memory_used_mb=4096.0,
        memory_total_mb=8192.0,
        gpu=[],
        notes=["init: starting run"],
    )
    store.append_metrics("RUN-1", snapshot)

    store.complete_run(
        "RUN-1",
        status="success",
        finished_at=started + timedelta(minutes=7, seconds=40),
        exit_code=0,
        artifacts=[StoredArtifact(path=str(artifact_file), description="Generated XML case")],
    )

    run2_output = tmp_path / "out2"
    run2_output.mkdir(parents=True, exist_ok=True)
    secondary = _build_record("RUN-2", started + timedelta(hours=1), run2_output)
    store.start_run(secondary)
    store.complete_run(
        "RUN-2",
        status="failed",
        finished_at=started + timedelta(hours=1, minutes=2),
        exit_code=1,
        artifacts=[],
        error={"message": "failed"},
    )
    return store


def _client_with_store(store: HistoryStore) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_router(store), prefix="/api")
    return TestClient(app)


def test_list_runs_returns_serialized_history(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    first = payload[0]
    assert first["runId"] == "RUN-2"
    assert first["status"] == "failed"
    assert first["summary"]["hasFailures"] is True
    second = payload[1]
    assert second["runId"] == "RUN-1"
    assert len(second["stageCheckpoints"]) == 3


def test_get_run_detail_includes_stage_checkpoints(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"] == "RUN-1"
    stages = payload["stageCheckpoints"]
    assert stages[0]["step"] == "init"
    assert stages[0]["state"] == StageState.COMPLETED.value


def test_get_metrics_returns_latest_snapshot(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-1/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"] == "RUN-1"
    resource = payload["resourceUsage"][0]
    assert resource["cpuPercent"] == 55.0
    assert resource["notes"] == ["init: starting run"]



def test_get_metrics_returns_204_when_absent(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-2/metrics")
    assert response.status_code == 204


def test_get_artifacts_returns_history_entries(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-1/artifacts")
    assert response.status_code == 200
    artifacts = response.json()
    assert artifacts[0]["runId"] == "RUN-1"
    assert artifacts[0]["path"] == "generated_case.xml"
    assert artifacts[0]["label"] == "Generated XML case"
    assert artifacts[0]["sizeBytes"] > 0
    assert artifacts[0]["previewAvailable"] is True



def test_get_artifact_content_returns_text(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-1/artifacts/content", params={"path": "generated_case.xml"})
    assert response.status_code == 200
    assert "example" in response.text

def test_runs_endpoint_does_not_redirect(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs")
    assert response.status_code == 200
    assert response.history == []



def test_run_list_omits_null_fields(tmp_path: Path) -> None:
    store_path = tmp_path / "history.json"
    store = HistoryStore(store_path)
    started = datetime(2025, 1, 1, 15, 0, tzinfo=timezone.utc)
    queued_record = RunRecord(
        run_id="RUN-QUEUED",
        query="queued run",
        status="queued",
        started_at=started,
        finished_at=None,
        exit_code=None,
        output_dir=str(tmp_path / "queued"),
        command=["python"],
        artifacts=[],
        stage_checkpoints=[
            RunStageStatus(stage="init", state=StageState.PENDING.value, message=None),
        ],
        metrics=[],
        error=None,
    )
    store.start_run(queued_record)

    client = _client_with_store(store)
    response = client.get("/api/runs")
    assert response.status_code == 200
    payload = response.json()
    queued = next(item for item in payload if item["runId"] == "RUN-QUEUED")
    assert "finishedAt" not in queued
    assert "durationSeconds" not in queued
    assert "exitCode" not in queued
    stage = queued["stageCheckpoints"][0]
    assert "message" not in stage
    assert "startedAt" not in stage
    assert "finishedAt" not in stage

def test_create_run_preflight_succeeds(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json")
    client = _client_with_store(store)

    response = client.options(
        "/api/runs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in {
        "http://localhost:5173",
        "*",
    }
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods


def test_create_run_invokes_runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json")
    client = _client_with_store(store)

    captured: dict[str, object] = {}

    def fake_spawn(request, history):
        captured["run_id"] = request.run_id
        captured["output_dir"] = request.output_dir
        captured["pause_after_agent1"] = request.pause_after_agent1
        captured["execute"] = request.execute
        captured["history"] = history

    monkeypatch.setattr("ui_backend.api._RUN_OUTPUT_ROOT", tmp_path / "runs")
    monkeypatch.setattr("ui_backend.api._spawn_run", fake_spawn)

    response = client.post(
        "/api/runs",
        json={"query": "demo run", "pauseAfterAgent1": True, "execute": False},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "queued"

    assert captured["run_id"] == payload["runId"]
    assert captured["pause_after_agent1"] is True
    assert captured["execute"] is False
    assert captured["history"] is store
    assert (tmp_path / "runs" / captured["run_id"]).exists()

    records = store.list_runs()
    assert len(records) == 1
    assert records[0].run_id == captured["run_id"]
    assert records[0].status == "queued"
