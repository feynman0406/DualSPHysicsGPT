from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence


class RunStatus(str, Enum):
    """Execution status for MVP runs."""

    SUCCESS = "success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class StageState(str, Enum):
    """Lifecycle state for individual execution stages."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class RunRequest:
    """Parameters for invoking the MVP pipeline wrapper."""

    query: str
    output_dir: Path
    pause_after_agent1: bool = False
    execute: bool = False
    timeout: Optional[float] = None
    env: Optional[dict[str, str]] = None
    run_id: Optional[str] = None
    model_name: Optional[str] = None
    external_stl: Optional[Path] = None

    def as_argv(self) -> List[str]:
        """Translate the request into CLI arguments for the subprocess."""

        argv: List[str] = ["--query", self.query]
        if self.pause_after_agent1:
            argv.append("--pause-after-agent1")
        if self.execute:
            argv.append("--execute")
        if self.run_id:
            argv.extend(["--run-id", self.run_id])
        if self.external_stl:
            argv.extend(["--external-stl", str(self.external_stl)])
        return argv


@dataclass(slots=True)
class ProducedFile:
    """File emitted by the MVP pipeline."""

    path: Path
    description: Optional[str] = None


@dataclass(slots=True)
class ErrorInfo:
    """Structured information describing a process failure."""

    message: str
    details: Optional[str] = None
    hint: Optional[str] = None


@dataclass(slots=True)
class RunStageStatus:
    """Status for a logical stage within the MVP wrapper."""

    stage: str
    state: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: Optional[str] = None


@dataclass(slots=True)
class GpuMetrics:
    """Per-GPU utilisation snapshot."""

    name: str
    utilization_percent: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_total_mb: Optional[float] = None


@dataclass(slots=True)
class ResourceUsageSnapshot:
    """System resource snapshot captured during a run."""

    captured_at: datetime
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_total_mb: Optional[float] = None
    gpu: List[GpuMetrics] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class RunResponse:
    """Outcome metadata for an MVP pipeline execution."""

    status: RunStatus
    exit_code: int
    started_at: datetime
    finished_at: datetime
    command: Sequence[str]
    log_path: Path
    output_dir: Path
    run_id: str
    produced_files: List[ProducedFile] = field(default_factory=list)
    error: Optional[ErrorInfo] = None
    stage_checkpoints: List[RunStageStatus] = field(default_factory=list)
    metrics: List[ResourceUsageSnapshot] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Return total elapsed time in seconds."""

        return (self.finished_at - self.started_at).total_seconds()

