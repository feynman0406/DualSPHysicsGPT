from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .models import ProducedFile, ResourceUsageSnapshot, RunStageStatus

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StoredArtifact:
    """Artifact metadata persisted in the history store."""

    path: str
    description: Optional[str] = None


@dataclass(slots=True)
class RunRecord:
    """Serialized representation of a recorded run."""

    run_id: str
    query: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    output_dir: Optional[str] = None
    command: Sequence[str] = field(default_factory=list)
    artifacts: List[StoredArtifact] = field(default_factory=list)
    stage_checkpoints: List[RunStageStatus] = field(default_factory=list)
    metrics: List[ResourceUsageSnapshot] = field(default_factory=list)
    error: Optional[dict[str, Optional[str]]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_timezone(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return _ensure_timezone(value).isoformat()


def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        logger.warning("Failed to parse datetime '%s' from history store", raw)
        return None


def _serialize_stage(stage: RunStageStatus) -> dict[str, Optional[str]]:
    return {
        "stage": stage.stage,
        "state": stage.state,
        "started_at": _serialize_datetime(stage.started_at),
        "finished_at": _serialize_datetime(stage.finished_at),
        "message": stage.message,
    }


def _deserialize_stage(payload: dict[str, Optional[str]]) -> RunStageStatus:
    return RunStageStatus(
        stage=payload.get("stage", ""),
        state=payload.get("state", ""),
        started_at=_parse_datetime(payload.get("started_at")),
        finished_at=_parse_datetime(payload.get("finished_at")),
        message=payload.get("message"),
    )


def _serialize_gpu(snapshot: ResourceUsageSnapshot) -> List[dict[str, Optional[float]]]:
    return [
        {
            "name": gpu.name,
            "utilization_percent": gpu.utilization_percent,
            "memory_used_mb": gpu.memory_used_mb,
            "memory_total_mb": gpu.memory_total_mb,
        }
        for gpu in snapshot.gpu
    ]


def _serialize_metrics(snapshot: ResourceUsageSnapshot) -> dict[str, object]:
    return {
        "captured_at": _serialize_datetime(snapshot.captured_at),
        "cpu_percent": snapshot.cpu_percent,
        "memory_percent": snapshot.memory_percent,
        "memory_used_mb": snapshot.memory_used_mb,
        "memory_total_mb": snapshot.memory_total_mb,
        "gpu": _serialize_gpu(snapshot),
        "notes": list(snapshot.notes),
    }


def _deserialize_metrics(payload: dict[str, object]) -> ResourceUsageSnapshot:
    from .models import GpuMetrics, ResourceUsageSnapshot  # Local import to avoid cycle

    gpu_payload = payload.get("gpu", []) or []
    gpu_entries = [
        GpuMetrics(
            name=str(item.get("name", "")),
            utilization_percent=item.get("utilization_percent"),
            memory_used_mb=item.get("memory_used_mb"),
            memory_total_mb=item.get("memory_total_mb"),
        )
        for item in gpu_payload
    ]
    notes_field = payload.get("notes")
    if isinstance(notes_field, list):
        notes = [str(item) for item in notes_field]
    elif notes_field is None:
        notes = []
    else:
        notes = [str(notes_field)]

    return ResourceUsageSnapshot(
        captured_at=_parse_datetime(payload.get("captured_at")) or _now(),
        cpu_percent=payload.get("cpu_percent"),
        memory_percent=payload.get("memory_percent"),
        memory_used_mb=payload.get("memory_used_mb"),
        memory_total_mb=payload.get("memory_total_mb"),
        gpu=gpu_entries,
        notes=notes,
    )


def _serialize_artifact(artifact: StoredArtifact) -> dict[str, Optional[str]]:
    return {
        "path": artifact.path,
        "description": artifact.description,
    }


def _deserialize_artifact(payload: dict[str, Optional[str]]) -> StoredArtifact:
    return StoredArtifact(path=str(payload.get("path", "")), description=payload.get("description"))


def _record_to_dict(record: RunRecord) -> dict[str, object]:
    return {
        "run_id": record.run_id,
        "query": record.query,
        "status": record.status,
        "started_at": _serialize_datetime(record.started_at),
        "finished_at": _serialize_datetime(record.finished_at),
        "exit_code": record.exit_code,
        "output_dir": record.output_dir,
        "command": list(record.command),
        "artifacts": [_serialize_artifact(item) for item in record.artifacts],
        "stage_checkpoints": [_serialize_stage(stage) for stage in record.stage_checkpoints],
        "metrics": [_serialize_metrics(snapshot) for snapshot in record.metrics],
        "error": record.error,
        "created_at": _serialize_datetime(record.created_at),
        "updated_at": _serialize_datetime(record.updated_at),
    }


def _dict_to_record(payload: dict[str, object]) -> RunRecord:
    artifacts = [_deserialize_artifact(item) for item in payload.get("artifacts", []) or []]
    stages = [_deserialize_stage(item) for item in payload.get("stage_checkpoints", []) or []]
    metrics = [_deserialize_metrics(item) for item in payload.get("metrics", []) or []]

    return RunRecord(
        run_id=str(payload.get("run_id", "")),
        query=str(payload.get("query", "")),
        status=str(payload.get("status", "")),
        started_at=_parse_datetime(payload.get("started_at")) or _now(),
        finished_at=_parse_datetime(payload.get("finished_at")),
        exit_code=payload.get("exit_code"),
        output_dir=payload.get("output_dir"),
        command=list(payload.get("command", []) or []),
        artifacts=artifacts,
        stage_checkpoints=stages,
        metrics=metrics,
        error=payload.get("error"),
        created_at=_parse_datetime(payload.get("created_at")) or _now(),
        updated_at=_parse_datetime(payload.get("updated_at")) or _now(),
    )


def _as_stored_artifact(artifact: ProducedFile | StoredArtifact) -> StoredArtifact:
    if isinstance(artifact, StoredArtifact):
        return artifact
    return StoredArtifact(path=str(artifact.path), description=artifact.description)


def _merge_stage(original: RunStageStatus, update: RunStageStatus) -> RunStageStatus:
    return RunStageStatus(
        stage=update.stage or original.stage,
        state=update.state or original.state,
        started_at=update.started_at or original.started_at,
        finished_at=update.finished_at or original.finished_at,
        message=update.message if update.message is not None else original.message,
    )


def _update_stage_in_list(
    stages: List[RunStageStatus],
    checkpoint: RunStageStatus,
) -> List[RunStageStatus]:
    updated: List[RunStageStatus] = []
    replaced = False
    for existing in stages:
        if existing.stage == checkpoint.stage:
            updated.append(_merge_stage(existing, checkpoint))
            replaced = True
        else:
            updated.append(existing)
    if not replaced:
        updated.append(checkpoint)
    return updated


class HistoryStore:
    """Filesystem-backed persistence for run metadata."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or Path(__file__).resolve().parent / "data" / "run_history.json"
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text(json.dumps({"runs": []}, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, object]:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"runs": []}
        if not text.strip():
            return {"runs": []}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("History store contained invalid JSON; resetting cache")
            return {"runs": []}
        if "runs" not in payload or not isinstance(payload["runs"], list):
            return {"runs": []}
        return payload

    def _save(self, payload: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _mutate_run(self, run_id: str, mutator):
        with self._lock:
            payload = self._load()
            runs = payload.get("runs", [])
            if not isinstance(runs, list):
                runs = []
            for index, raw in enumerate(runs):
                if not isinstance(raw, dict):
                    continue
                if str(raw.get("run_id")) != run_id:
                    continue
                record = _dict_to_record(raw)
                mutator(record)
                record.updated_at = _now()
                runs[index] = _record_to_dict(record)
                payload["runs"] = runs
                self._save(payload)
                return
            logger.warning("Run '%s' not found when attempting to mutate history", run_id)

    def start_run(self, record: RunRecord) -> None:
        record.created_at = _now()
        record.updated_at = record.created_at
        with self._lock:
            payload = self._load()
            runs = payload.get("runs", [])
            if not isinstance(runs, list):
                runs = []
            runs = [
                raw
                for raw in runs
                if isinstance(raw, dict) and str(raw.get("run_id")) != record.run_id
            ]
            runs.append(_record_to_dict(record))
            payload["runs"] = runs
            self._save(payload)

    def update_stage(self, run_id: str, checkpoint: RunStageStatus) -> None:
        def mutator(record: RunRecord) -> None:
            record.stage_checkpoints = _update_stage_in_list(record.stage_checkpoints, checkpoint)

        self._mutate_run(run_id, mutator)

    def append_metrics(self, run_id: str, snapshot: ResourceUsageSnapshot) -> None:
        def mutator(record: RunRecord) -> None:
            record.metrics.append(snapshot)

        self._mutate_run(run_id, mutator)

    def append_artifacts(
        self,
        run_id: str,
        artifacts: Iterable[ProducedFile | StoredArtifact],
    ) -> None:
        materialized = [_as_stored_artifact(item) for item in artifacts]

        def mutator(record: RunRecord) -> None:
            existing_paths = {item.path for item in record.artifacts}
            for artifact in materialized:
                if artifact.path not in existing_paths:
                    record.artifacts.append(artifact)

        self._mutate_run(run_id, mutator)

    def complete_run(
        self,
        run_id: str,
        *,
        status: str,
        finished_at: Optional[datetime],
        exit_code: Optional[int],
        artifacts: Iterable[ProducedFile | StoredArtifact],
        error: Optional[dict[str, Optional[str]]] = None,
    ) -> None:
        materialized = [_as_stored_artifact(item) for item in artifacts]

        def mutator(record: RunRecord) -> None:
            record.status = status
            record.finished_at = finished_at or record.finished_at
            record.exit_code = exit_code
            record.error = error
            record.artifacts = materialized or record.artifacts

        self._mutate_run(run_id, mutator)

    def delete_run(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            payload = self._load()
            runs_payload = payload.get("runs", []) or []
            if not isinstance(runs_payload, list):
                runs_payload = []
            remaining = []
            removed: Optional[RunRecord] = None
            for raw in runs_payload:
                if not isinstance(raw, dict):
                    remaining.append(raw)
                    continue
                if removed is None and str(raw.get("run_id")) == run_id:
                    removed = _dict_to_record(raw)
                    continue
                remaining.append(raw)
            if removed is None:
                return None
            payload["runs"] = remaining
            self._save(payload)
            return removed



    def list_runs(self, *, limit: Optional[int] = None) -> List[RunRecord]:
        with self._lock:
            payload = self._load()
        runs = [_dict_to_record(raw) for raw in payload.get("runs", []) or []]
        runs.sort(
            key=lambda record: record.started_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        if limit is not None:
            return runs[:limit]
        return runs

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            payload = self._load()
        for raw in payload.get("runs", []) or []:
            if not isinstance(raw, dict):
                continue
            if str(raw.get("run_id")) == run_id:
                return _dict_to_record(raw)
        return None


__all__ = [
    "HistoryStore",
    "RunRecord",
    "StoredArtifact",
]





