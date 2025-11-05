from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import BytesIO

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import pytest

from ui_backend.api import create_router
from ui_backend.history_store import HistoryStore, RunRecord, StoredArtifact
from ui_backend.models import ResourceUsageSnapshot, RunRequest, RunStageStatus, StageState


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
        dependency_manifest={"files": [{"path": "generated_case.xml", "status": "copied"}], "warnings": []},
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
    assert second.get("summary", {}).get("dependencyCount") == 1


def test_get_run_detail_includes_stage_checkpoints(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runId"] == "RUN-1"
    assert payload.get("dependencyManifest")
    assert payload["dependencyManifest"]["files"][0]["path"] == "generated_case.xml"
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
    assert artifacts[0]["downloadUrl"] == "/api/runs/RUN-1/artifacts/download?path=generated_case.xml"



def test_get_artifact_content_returns_text(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-1/artifacts/content", params={"path": "generated_case.xml"})
    assert response.status_code == 200
    assert "example" in response.text

def test_download_artifact_returns_file(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get('/api/runs/RUN-1/artifacts/download', params={'path': 'generated_case.xml'})
    assert response.status_code == 200
    disposition = response.headers.get('content-disposition', '')
    assert 'attachment' in disposition
    assert b'example' in response.content


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
        captured["request"] = request
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

    request = captured["request"]
    assert isinstance(request, RunRequest)
    assert request.run_id == payload["runId"]
    assert request.external_stl is None
    assert request.pause_after_agent1 is True
    assert request.execute is False
    assert captured["history"] is store

    run_dir = tmp_path / "runs" / request.run_id
    assert run_dir.exists()

    records = store.list_runs()
    assert len(records) == 1
    assert records[0].run_id == request.run_id
    assert records[0].status == "queued"


def test_create_run_accepts_external_stl_upload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json")
    client = _client_with_store(store)

    captured: dict[str, object] = {}

    def fake_spawn(request, history):
        captured["request"] = request
        captured["history"] = history

    run_root = tmp_path / "runs"
    monkeypatch.setattr("ui_backend.api._RUN_OUTPUT_ROOT", run_root)
    monkeypatch.setattr("ui_backend.api._spawn_run", fake_spawn)

    files = {"externalStl": ("duck.stl", BytesIO(b"solid mesh"), "application/sla")}
    data = {"query": "with stl", "pauseAfterAgent1": "false", "execute": "true"}

    response = client.post("/api/runs", data=data, files=files)

    assert response.status_code == 201
    payload = response.json()
    request = captured["request"]
    assert isinstance(request, RunRequest)
    assert request.external_stl is not None
    assert request.external_stl.exists()
    assert request.run_id == payload["runId"]
    assert request.execute is True
    assert request.pause_after_agent1 is False
    assert captured["history"] is store

    stored_path = run_root / request.run_id / "uploads" / "duck.stl"
    assert stored_path.exists()
    assert request.external_stl == stored_path
    assert stored_path.read_bytes() == b"solid mesh"

    records = store.list_runs()
    assert len(records) == 1
    assert records[0].run_id == request.run_id
    assert records[0].status == "queued"


def test_create_run_rejects_non_stl_upload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json")
    client = _client_with_store(store)

    run_root = tmp_path / "runs"
    monkeypatch.setattr("ui_backend.api._RUN_OUTPUT_ROOT", run_root)

    response = client.post(
        "/api/runs",
        data={"query": "bad upload"},
        files={"externalStl": ("notes.txt", BytesIO(b"bad"), "text/plain")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "External STL must use a .stl extension"
    assert store.list_runs() == []



def test_delete_run_endpoint_removes_history_and_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_root = tmp_path / "runs"
    run_root.mkdir()
    monkeypatch.setattr("ui_backend.api._RUN_OUTPUT_ROOT", run_root)

    store = HistoryStore(tmp_path / "history.json")
    started = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    run_dir = run_root / "RUN-REMOVE"
    run_dir.mkdir(parents=True)
    (run_dir / "artifact.txt").write_text("payload", encoding="utf-8")

    removable = _build_record("RUN-REMOVE", started, run_dir)
    retained_dir = run_root / "RUN-KEEP"
    retained_dir.mkdir(parents=True)
    retained = _build_record("RUN-KEEP", started + timedelta(minutes=5), retained_dir)

    store.start_run(removable)
    store.start_run(retained)

    client = _client_with_store(store)
    response = client.delete("/api/runs/RUN-REMOVE")
    assert response.status_code == 204
    assert store.get_run("RUN-REMOVE") is None
    assert not run_dir.exists()

    remaining_ids = [record.run_id for record in store.list_runs()]
    assert remaining_ids == ["RUN-KEEP"]


def test_delete_run_endpoint_returns_not_found(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.delete("/api/runs/DOES-NOT-EXIST")
    assert response.status_code == 404
def test_get_run_dependencies_endpoint(tmp_path: Path) -> None:
    store = _prepare_store(tmp_path)
    client = _client_with_store(store)

    response = client.get("/api/runs/RUN-1/dependencies")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["files"][0]["path"] == "generated_case.xml"

    response_empty = client.get("/api/runs/RUN-2/dependencies")
    assert response_empty.status_code == 204
