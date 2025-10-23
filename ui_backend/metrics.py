from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime, timezone
from typing import List, Optional

from .models import GpuMetrics, ResourceUsageSnapshot

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - exercised via test fallback
    psutil = None  # type: ignore

logger = logging.getLogger(__name__)


def _safe_float(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _collect_gpu_metrics(notes: List[str]) -> List[GpuMetrics]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        notes.append("nvidia-smi not found; GPU metrics unavailable")
        return []

    try:
        result = subprocess.run(
            [
                binary,
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except FileNotFoundError:
        notes.append("nvidia-smi not found; GPU metrics unavailable")
        return []
    except subprocess.CalledProcessError as exc:
        notes.append(f"nvidia-smi failed (exit {exc.returncode})")
        logger.debug("nvidia-smi stderr: %s", exc.stderr)
        return []
    except subprocess.SubprocessError as exc:
        notes.append(f"nvidia-smi error: {exc}")
        return []

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    metrics: List[GpuMetrics] = []
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        metrics.append(
            GpuMetrics(
                name=parts[0],
                utilization_percent=_safe_float(parts[1]),
                memory_used_mb=_safe_float(parts[2]),
                memory_total_mb=_safe_float(parts[3]),
            )
        )
    if not metrics:
        notes.append("nvidia-smi returned no GPU records")
    return metrics


def collect_resource_snapshot() -> ResourceUsageSnapshot:
    """Capture a snapshot of local CPU, memory, and GPU utilisation."""

    captured_at = datetime.now(timezone.utc)
    notes: List[str] = []

    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_total_mb: Optional[float] = None

    if psutil is None:
        notes.append("psutil unavailable; CPU/memory metrics disabled")
    else:
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            virtual_memory = psutil.virtual_memory()
            memory_percent = getattr(virtual_memory, "percent", None)
            used = getattr(virtual_memory, "used", None)
            total = getattr(virtual_memory, "total", None)
            if used is not None:
                memory_used_mb = round(float(used) / (1024 * 1024), 2)
            if total is not None:
                memory_total_mb = round(float(total) / (1024 * 1024), 2)
        except Exception as exc:  # pragma: no cover - defensive guard
            notes.append(f"psutil error: {exc}")
            logger.debug("psutil metrics collection failed", exc_info=exc)

    gpu_metrics = _collect_gpu_metrics(notes)

    return ResourceUsageSnapshot(
        captured_at=captured_at,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        memory_used_mb=memory_used_mb,
        memory_total_mb=memory_total_mb,
        gpu=gpu_metrics,
        notes=notes,
    )


__all__ = ["collect_resource_snapshot"]
