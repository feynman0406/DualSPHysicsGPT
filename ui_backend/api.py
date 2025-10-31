from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .history_store import HistoryStore, RunRecord, StoredArtifact
from .models import ResourceUsageSnapshot, RunRequest, RunStageStatus
from . import model_options
from .runner import run_mvp


logger = logging.getLogger(__name__)

try:
    from llm.client import get_model_name as _llm_get_model_name, get_reasoning_config as _llm_get_reasoning_config
except Exception as exc:  # pragma: no cover - helper optional
    logger.debug('LLM helpers unavailable: %s', exc)
    _llm_get_model_name = None
    _llm_get_reasoning_config = None

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUN_OUTPUT_ROOT = _REPO_ROOT / "logs" / "ui_backend" / "runs"
_PREVIEW_BYTE_LIMIT = 2 * 1024 * 1024  # 2 MiB safeguard for UI previews


class CreateRunPayload(BaseModel):
    query: str = Field(..., min_length=1)
    pause_after_agent1: bool = Field(default=False, alias="pauseAfterAgent1")
    execute: bool = False
    model: str | None = Field(default=None, validation_alias=AliasChoices("model", "modelName"))

    model_config = ConfigDict(populate_by_name=True)


class CreateRunResponse(BaseModel):
    runId: str
    status: str


def _generate_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:6].upper()
    return f"RUN-{timestamp}-{suffix}"


def _prepare_output_dir(run_id: str) -> Path:
    target = _RUN_OUTPUT_ROOT / run_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}
    return False

def _resolve_model_metadata(preferred_model: Optional[str] = None) -> Tuple[Optional[str], Optional[dict[str, str]], Optional[str]]:
    model_name: Optional[str] = preferred_model.strip() if preferred_model else None
    reasoning_config: Optional[dict[str, str]] = None
    reasoning_level: Optional[str] = None

    if model_name is None and _llm_get_model_name is not None:
        try:
            candidate = _llm_get_model_name()
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.debug('Unable to resolve model name: %s', exc)
        else:
            if isinstance(candidate, str):
                candidate = candidate.strip()
                if candidate:
                    model_name = candidate
            elif candidate is not None:
                model_name = str(candidate)

    if _llm_get_reasoning_config is not None:
        try:
            raw_config = _llm_get_reasoning_config()
        except Exception as exc:  # pragma: no cover - best-effort logging
            logger.debug('Unable to resolve reasoning config: %s', exc)
        else:
            if isinstance(raw_config, dict):
                cleaned: dict[str, str] = {}
                for key, value in raw_config.items():
                    cleaned[str(key)] = str(value).strip()
                reasoning_config = cleaned or None
                level_candidate = cleaned.get('effort') or cleaned.get('level') or cleaned.get('intensity')
                if level_candidate is not None:
                    candidate_str = str(level_candidate).strip()
                    if candidate_str:
                        reasoning_level = candidate_str

    return model_name, reasoning_config, reasoning_level

def _store_external_stl_upload(upload: UploadFile, run_output_dir: Path) -> Path:
    filename = upload.filename or 'external_geometry.stl'
    name = Path(filename).name
    if Path(name).suffix.lower() != '.stl':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='External STL must use a .stl extension',
        )

    target_dir = run_output_dir / 'uploads'
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / name

    try:
        upload.file.seek(0)
        with target_path.open('wb') as buffer:
            shutil.copyfileobj(upload.file, buffer)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to store STL upload: {exc}',
        ) from exc
    finally:
        try:
            upload.file.close()
        except Exception:
            pass

    return target_path


def _enqueue_run(
    history: HistoryStore,
    *,
    run_id: str,
    query: str,
    output_dir: Path,
    model_name: Optional[str] = None,
    reasoning_config: Optional[dict[str, str]] = None,
    reasoning_level: Optional[str] = None,
) -> None:
    record = RunRecord(
        run_id=run_id,
        query=query,
        status="queued",
        started_at=datetime.now(timezone.utc),
        output_dir=str(output_dir),
        model_name=model_name,
        reasoning_config=reasoning_config,
        reasoning_level=reasoning_level,
    )
    history.start_run(record)


def _execute_run(request: RunRequest, history: HistoryStore) -> None:
    try:
        run_mvp(request, store=history)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Run %s failed before completion", request.run_id)
        try:
            history.complete_run(
                request.run_id,
                status="failed",
                finished_at=datetime.now(timezone.utc),
                exit_code=None,
                artifacts=[],
                error={"message": str(exc)},
            )
        except Exception:  # pragma: no cover - best-effort cleanup
            logger.exception("Unable to record failure for run %s", request.run_id)


def _spawn_run(request: RunRequest, history: HistoryStore) -> threading.Thread:
    thread = threading.Thread(
        target=_execute_run,
        args=(request, history),
        name=f"run-{request.run_id}",
        daemon=True,
    )
    thread.start()
    return thread


def _format_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone().isoformat()


def _duration_seconds(start: Optional[datetime], finish: Optional[datetime]) -> Optional[float]:
    if start is None or finish is None:
        return None
    return (finish - start).total_seconds()


def _omit_none(payload: dict[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if value is not None}


def _resolve_output_dir(record: RunRecord) -> Optional[Path]:
    if not record.output_dir:
        return None
    try:
        return Path(record.output_dir).resolve()
    except Exception:
        logger.debug("Unable to resolve output directory for run %s", record.run_id)
        return None



def _delete_output_directory(path: Path) -> None:
    try:
        path.relative_to(_RUN_OUTPUT_ROOT)
    except ValueError:
        logger.warning("Skipping deletion of %s because it is outside managed run directory", path)
        return
    if path == _RUN_OUTPUT_ROOT:
        logger.warning("Refusing to delete run output root %s", path)
        return
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except OSError:
        logger.exception("Failed to delete run output directory %s", path)


def _resolve_artifact_path(record: RunRecord, artifact_path: str) -> Optional[Path]:
    output_dir = _resolve_output_dir(record)
    candidate = Path(artifact_path)

    try:
        if output_dir is not None:
            if candidate.is_absolute():
                resolved = candidate.resolve()
            else:
                resolved = (output_dir / candidate).resolve()
            resolved.relative_to(output_dir)
            return resolved
        if candidate.is_absolute():
            resolved = candidate.resolve()
            # Only allow reading paths under the repo's run root for safety
            resolved.relative_to(_RUN_OUTPUT_ROOT)
            return resolved
    except (OSError, ValueError):
        return None

    if output_dir is not None:
        fallback = (output_dir / candidate).resolve()
        try:
            fallback.relative_to(output_dir)
            return fallback
        except ValueError:
            return None

    return None


def _serialize_stage(stage: RunStageStatus) -> dict[str, object]:
    payload = {
        "step": stage.stage,
        "state": stage.state,
        "startedAt": _format_datetime(stage.started_at),
        "finishedAt": _format_datetime(stage.finished_at),
        "message": stage.message,
    }
    return _omit_none(payload)


def _serialize_resource(snapshot: ResourceUsageSnapshot) -> dict[str, object]:
    gpu_entries = [
        _omit_none(
            {
                "name": gpu.name,
                "utilizationPercent": gpu.utilization_percent,
                "memoryUsedMb": gpu.memory_used_mb,
                "memoryTotalMb": gpu.memory_total_mb,
            }
        )
        for gpu in snapshot.gpu
    ]
    payload = {
        "capturedAt": _format_datetime(snapshot.captured_at),
        "cpuPercent": snapshot.cpu_percent,
        "memoryPercent": snapshot.memory_percent,
        "memoryUsedMb": snapshot.memory_used_mb,
        "memoryTotalMb": snapshot.memory_total_mb,
        "gpu": gpu_entries,
        "notes": list(snapshot.notes),
    }
    return _omit_none(payload)


def _serialize_artifact(record: RunRecord, artifact: StoredArtifact) -> dict[str, object]:
    resolved = _resolve_artifact_path(record, artifact.path)
    display_path = artifact.path
    size_bytes: Optional[int] = None
    preview_available = True

    if resolved is not None:
        try:
            size_bytes = resolved.stat().st_size
            output_dir = _resolve_output_dir(record)
            if output_dir is not None:
                try:
                    display_path = str(resolved.relative_to(output_dir))
                except ValueError:
                    display_path = str(resolved)
        except OSError:
            preview_available = False
    else:
        preview_available = False

    payload = {
        "runId": record.run_id,
        "path": display_path,
        "label": artifact.description or Path(display_path).name,
        "sizeBytes": size_bytes,
        "previewAvailable": preview_available,
    }
    return _omit_none(payload)


def _serialize_summary(record: RunRecord) -> dict[str, object]:
    summary: dict[str, object] = {}
    if record.artifacts:
        summary["artifactCount"] = len(record.artifacts)
        summary["primaryOutput"] = record.artifacts[0].path
    if record.error is not None:
        summary["hasFailures"] = True
    return summary


def _serialize_run(record: RunRecord) -> dict[str, object]:
    base = {
        "runId": record.run_id,
        "query": record.query,
        "status": record.status,
        "exitCode": record.exit_code,
        "startedAt": _format_datetime(record.started_at),
        "finishedAt": _format_datetime(record.finished_at),
        "durationSeconds": _duration_seconds(record.started_at, record.finished_at),
    }
    payload = _omit_none(base)
    if record.model_name:
        payload["modelName"] = record.model_name
    if record.reasoning_config:
        payload["reasoningConfig"] = record.reasoning_config
    reasoning_level = record.reasoning_level
    if reasoning_level:
        payload["reasoningLevel"] = reasoning_level
    elif record.reasoning_config:
        inferred_level = record.reasoning_config.get("effort") or record.reasoning_config.get("level") or record.reasoning_config.get("intensity")
        if inferred_level:
            candidate = str(inferred_level).strip()
            if candidate:
                payload["reasoningLevel"] = candidate
    summary = _serialize_summary(record)
    if summary:
        payload["summary"] = summary
    stages = [_serialize_stage(stage) for stage in record.stage_checkpoints]
    if stages:
        payload["stageCheckpoints"] = stages
    return payload


def _store_dependency_factory(store: HistoryStore | None):
    if store is None:
        def _default_store():
            return HistoryStore()

        return _default_store

    def _inner():
        return store

    return _inner


def create_router(store: HistoryStore | None = None) -> APIRouter:
    """Create a FastAPI router exposing run history endpoints."""

    router = APIRouter(prefix="/runs", tags=["runs"])
    get_store = _store_dependency_factory(store)

    @router.post("", response_model=CreateRunResponse, status_code=status.HTTP_201_CREATED)
    async def create_run_endpoint(
        request: Request,
        history = Depends(get_store),
    ) -> CreateRunResponse:
        content_type = (request.headers.get("content-type") or "").lower()
        query = ""
        pause_after_agent1 = False
        execute = False
        external_upload: UploadFile | None = None
        requested_model: str | None = None

        if "multipart/form-data" in content_type:
            form = await request.form()
            query_value = form.get("query")
            query = str(query_value).strip() if query_value is not None else ""
            if not query:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query is required")
            pause_after_agent1 = _parse_bool(form.get("pauseAfterAgent1") or form.get("pause_after_agent1"))
            execute = _parse_bool(form.get("execute"))
            model_value = form.get("model") or form.get("modelName")
            if model_value is not None:
                requested_model = str(model_value).strip() or None
            values = form.getlist("externalStl")
            candidate = values[0] if values else form.get("externalStl")

            upload_candidate: UploadFile | None
            if isinstance(candidate, UploadFile):
                upload_candidate = candidate
            elif candidate is not None and hasattr(candidate, "filename"):
                upload_candidate = candidate  # type: ignore[assignment]
            else:
                upload_candidate = None

            if upload_candidate and (upload_candidate.filename or "").strip():
                external_upload = upload_candidate
            elif upload_candidate:
                try:
                    upload_candidate.file.close()
                except Exception:  # pragma: no cover - best effort cleanup
                    pass
        else:
            try:
                payload_data = await request.json()
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON body: {exc}",
                ) from exc
            payload = CreateRunPayload.model_validate(payload_data)
            query = payload.query
            pause_after_agent1 = payload.pause_after_agent1
            execute = payload.execute
            requested_model = payload.model.strip() if payload.model else None

        selected_model: str | None = None
        if requested_model:
            selected_model = model_options.coerce_model(requested_model)
            if selected_model is None:
                allowed = ", ".join(model_options.ALLOWED_MODELS)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported model '{requested_model}'. Choose one of: {allowed}",
                )

        run_id = _generate_run_id()
        output_dir = _prepare_output_dir(run_id)

        stored_external: Path | None = None
        if external_upload is not None:
            stored_external = _store_external_stl_upload(external_upload, output_dir)

        request_model = RunRequest(
            query=query,
            output_dir=output_dir,
            pause_after_agent1=pause_after_agent1,
            execute=execute,
            run_id=run_id,
            model_name=selected_model,
            external_stl=stored_external,
        )

        model_name, reasoning_config, reasoning_level = _resolve_model_metadata(selected_model)
        if model_name and request_model.model_name is None:
            request_model.model_name = model_name

        try:
            _enqueue_run(
                history,
                run_id=run_id,
                query=query,
                output_dir=output_dir,
                model_name=model_name,
                reasoning_config=reasoning_config,
                reasoning_level=reasoning_level,
            )
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Failed to persist queued record for run %s", run_id)

        _spawn_run(request_model, history)
        return CreateRunResponse(runId=run_id, status="queued")

    router.add_api_route(
        "/",
        create_run_endpoint,
        methods=["POST"],
        include_in_schema=False,
    )

    @router.get("")
    def list_runs(history = Depends(get_store)) -> list[dict[str, object]]:
        records = history.list_runs()
        return [_serialize_run(record) for record in records]

    router.add_api_route(
        "/",
        list_runs,
        methods=["GET"],
        include_in_schema=False,
    )

    @router.get("/{run_id}")
    def get_run(
        run_id: str,
        history = Depends(get_store),
    ) -> dict[str, object]:
        record = history.get_run(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )
        return _serialize_run(record)


    @router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_run_endpoint(
        run_id: str,
        history = Depends(get_store),
    ) -> Response:
        record = history.delete_run(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )
        output_dir = _resolve_output_dir(record)
        if output_dir is not None:
            _delete_output_directory(output_dir)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/{run_id}/metrics", response_model=None)
    def get_run_metrics(run_id: str, history = Depends(get_store)):
        record = history.get_run(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )
        if not record.metrics:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        snapshots = [_serialize_resource(snapshot) for snapshot in record.metrics]
        payload: dict[str, object] = {
            "runId": record.run_id,
            "capturedAt": snapshots[-1].get("capturedAt"),
            "durationSeconds": _duration_seconds(record.started_at, record.finished_at),
            "resourceUsage": snapshots,
        }
        return _omit_none(payload)

    @router.get("/{run_id}/artifacts")
    def get_run_artifacts(
        run_id: str,
        history = Depends(get_store),
    ) -> list[dict[str, object]]:
        record = history.get_run(run_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )
        return [
            _serialize_artifact(record, artifact)
            for artifact in record.artifacts
        ]

    @router.get("/{run_id}/artifacts/content", response_class=PlainTextResponse)
    def get_artifact_content(
        run_id: str,
        path: str = Query(..., description="Artifact path as returned by the listing endpoint"),
        history = Depends(get_store),
    ) -> PlainTextResponse:
        record = history.get_run(run_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

        resolved = _resolve_artifact_path(record, path)
        if resolved is None or not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        try:
            if resolved.stat().st_size > _PREVIEW_BYTE_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Artifact exceeds preview size limit",
                )
            text = resolved.read_text(encoding="utf-8", errors="replace")
            return PlainTextResponse(text)
        except OSError as exc:
            logger.exception("Failed to read artifact %s for run %s", resolved, run_id)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return router


__all__ = ["create_router"]


