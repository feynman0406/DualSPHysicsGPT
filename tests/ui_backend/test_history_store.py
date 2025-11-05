from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui_backend.history_store import HistoryStore, RunRecord, StoredArtifact
from ui_backend.models import ResourceUsageSnapshot, RunStageStatus, StageState


def test_history_store_persists_runs(tmp_path: Path) -> None:
    store_path = tmp_path / "history.json"
    store = HistoryStore(store_path)
    run_id = "RUN-TEST-001"
    started = datetime(2025, 1, 1, tzinfo=timezone.utc)

    record = RunRecord(
        run_id=run_id,
        query="demo",
        status="running",
        started_at=started,
        output_dir=str(tmp_path / "output"),
        command=["python", "demo.py"],
        stage_checkpoints=[
            RunStageStatus(
                stage="init",
                state=StageState.RUNNING.value,
                started_at=started,
            )
        ],
        metrics=[
            ResourceUsageSnapshot(
                captured_at=started,
                cpu_percent=None,
                memory_percent=None,
                memory_used_mb=None,
                memory_total_mb=None,
                gpu=[],
                notes=["initial"],
            )
        ],
    )

    store.start_run(record)

    completed_stage = RunStageStatus(
        stage="init",
        state=StageState.COMPLETED.value,
        started_at=started,
        finished_at=started,
    )
    store.update_stage(run_id, completed_stage)

    snapshot = ResourceUsageSnapshot(
        captured_at=started,
        cpu_percent=12.5,
        memory_percent=50.0,
        memory_used_mb=256.0,
        memory_total_mb=512.0,
        gpu=[],
        notes=["post-init"],
    )
    store.append_metrics(run_id, snapshot)

    artifact = StoredArtifact(path="logs/output.txt", description="combined log")
    store.append_artifacts(run_id, [artifact])
    manifest = {"files": [{"path": "logs/output.txt", "status": "copied"}], "warnings": []}
    store.complete_run(
        run_id,
        status="success",
        finished_at=started,
        exit_code=0,
        artifacts=[artifact],
        dependency_manifest=manifest,
    )

    reopened = HistoryStore(store_path)
    stored = reopened.get_run(run_id)
    assert stored is not None
    assert stored.status == "success"
    assert len(stored.metrics) == 2
    assert stored.stage_checkpoints[-1].state == StageState.COMPLETED.value
    assert stored.artifacts[0].path == "logs/output.txt"
    assert stored.exit_code == 0
    assert stored.dependency_manifest == manifest


def test_delete_run_removes_record(tmp_path: Path) -> None:
    store_path = tmp_path / "history.json"
    store = HistoryStore(store_path)
    started = datetime(2025, 1, 1, tzinfo=timezone.utc)

    run1 = RunRecord(
        run_id="RUN-DELETE-1",
        query="first",
        status="success",
        started_at=started,
        output_dir=str(tmp_path / "out1"),
    )
    run2 = RunRecord(
        run_id="RUN-DELETE-2",
        query="second",
        status="success",
        started_at=started,
        output_dir=str(tmp_path / "out2"),
    )

    store.start_run(run1)
    store.start_run(run2)

    removed = store.delete_run(run1.run_id)
    assert removed is not None
    assert removed.run_id == run1.run_id
    assert store.get_run(run1.run_id) is None

    reloaded = HistoryStore(store_path)
    remaining = [record.run_id for record in reloaded.list_runs()]
    assert remaining == [run2.run_id]

    assert store.delete_run("missing") is None
