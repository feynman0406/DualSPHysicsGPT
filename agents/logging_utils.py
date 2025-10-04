"""Logging utilities for Planning Agent pipeline."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

LOGGER = logging.getLogger(__name__)

# Logging paths
LOGS_DIR = Path("logs/last_run")
METRICS_DIR = Path("metrics")
METRICS_CSV = METRICS_DIR / "plan_runs.csv"

# CSV headers
METRICS_HEADERS = [
    "timestamp",
    "query_sha256",
    "status",
    "completion_rate",
    "stage2_passed",
    "retry_count",
    "mode",
    "notes",
]

# Rolling log limit
MAX_ROLLING_LOGS = 5


def _ensure_dir(path: Path) -> None:
    """Ensure directory exists."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        LOGGER.warning("Failed to create directory %s: %s", path, exc)


def _rotate_file(path: Path, max_versions: int = MAX_ROLLING_LOGS) -> None:
    """Rotate file by appending version numbers."""
    if not path.exists():
        return
    
    # Shift existing versions
    for i in range(max_versions - 1, 0, -1):
        old_path = path.with_suffix(f".{i}{path.suffix}")
        new_path = path.with_suffix(f".{i + 1}{path.suffix}")
        if old_path.exists():
            try:
                old_path.rename(new_path)
            except Exception as exc:
                LOGGER.warning("Failed to rotate %s: %s", old_path, exc)
    
    # Move current to .1
    try:
        versioned = path.with_suffix(f".1{path.suffix}")
        path.rename(versioned)
    except Exception as exc:
        LOGGER.warning("Failed to rotate %s: %s", path, exc)


def persist_plan_json(plan: Mapping[str, Any], attempt: int = 1) -> Path:
    """
    Persist Plan JSON to logs directory with rotation.
    
    Args:
        plan: The plan dictionary to persist
        attempt: Attempt number for this plan
    
    Returns:
        Path where the plan was saved
    """
    _ensure_dir(LOGS_DIR)
    
    target = LOGS_DIR / "planning_plan.json"
    
    # Rotate existing file
    _rotate_file(target)
    
    # Add metadata
    enriched = dict(plan)
    enriched.setdefault("attempt", attempt)
    enriched.setdefault("persisted_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    
    try:
        target.write_text(
            json.dumps(enriched, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        LOGGER.info("Persisted Plan JSON to %s (attempt %d)", target, attempt)
    except Exception as exc:
        LOGGER.error("Failed to persist Plan JSON: %s", exc)
        raise
    
    return target


def load_last_plan_json() -> dict[str, Any] | None:
    """
    Load the most recent Plan JSON from logs.
    
    Returns:
        Plan dictionary or None if not found
    """
    target = LOGS_DIR / "planning_plan.json"
    if not target.exists():
        return None
    
    try:
        with target.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        LOGGER.error("Failed to load last plan JSON: %s", exc)
        return None


def init_metrics_csv() -> None:
    """Initialize metrics CSV with headers if it doesn't exist."""
    _ensure_dir(METRICS_DIR)
    
    if METRICS_CSV.exists():
        return
    
    try:
        with METRICS_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(METRICS_HEADERS)
        LOGGER.info("Initialized metrics CSV at %s", METRICS_CSV)
    except Exception as exc:
        LOGGER.error("Failed to initialize metrics CSV: %s", exc)


def append_metrics(
    query: str,
    status: str,
    completion_rate: float | None,
    stage2_passed: bool,
    retry_count: int,
    mode: str,
    notes: str = "",
) -> None:
    """
    Append a metrics entry to the CSV.
    
    Args:
        query: Original query text
        status: Plan status (completed, no_results, retrying)
        completion_rate: Fraction of fields covered (0.0-1.0)
        stage2_passed: Whether Stage 2 succeeded
        retry_count: Number of retries
        mode: Planning mode (two-requests, single-request)
        notes: Additional notes or error summaries
    """
    init_metrics_csv()
    
    # Compute query hash
    query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    
    # Format values
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    completion_str = f"{completion_rate:.2f}" if completion_rate is not None else ""
    stage2_str = "true" if stage2_passed else "false"
    
    row = [
        timestamp,
        query_hash,
        status,
        completion_str,
        stage2_str,
        str(retry_count),
        mode,
        notes[:200],  # Truncate notes
    ]
    
    try:
        with METRICS_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
        LOGGER.info("Appended metrics entry: status=%s, completion=%.2f", status, completion_rate or 0.0)
    except Exception as exc:
        LOGGER.error("Failed to append metrics: %s", exc)
    
    # Check file size and rotate if needed
    _check_and_rotate_metrics()


def _check_and_rotate_metrics() -> None:
    """Rotate metrics CSV if it exceeds size limit."""
    if not METRICS_CSV.exists():
        return
    
    try:
        line_count = sum(1 for _ in METRICS_CSV.open("r", encoding="utf-8"))
        if line_count > 10000:
            LOGGER.info("Rotating metrics CSV (line count: %d)", line_count)
            _rotate_file(METRICS_CSV)
            init_metrics_csv()
    except Exception as exc:
        LOGGER.warning("Failed to check/rotate metrics CSV: %s", exc)


def persist_two_stage_search(search_data: Mapping[str, Any]) -> Path:
    """
    Persist two-stage search summary to logs.
    
    Args:
        search_data: Search results and metadata
    
    Returns:
        Path where data was saved
    """
    _ensure_dir(LOGS_DIR)
    
    target = LOGS_DIR / "two_stage_search.json"
    _rotate_file(target)
    
    try:
        target.write_text(
            json.dumps(search_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        LOGGER.info("Persisted two-stage search data to %s", target)
    except Exception as exc:
        LOGGER.error("Failed to persist search data: %s", exc)
        raise
    
    return target


def calculate_completion_rate(plan: Mapping[str, Any], required_fields: set[str]) -> float:
    """
    Calculate plan completion rate based on covered required fields.
    
    Formula: covered_fields / total_required_fields
    
    Args:
        plan: The plan dictionary
        required_fields: Set of required field names to check
    
    Returns:
        Completion rate between 0.0 and 1.0
    """
    if not required_fields:
        return 1.0
    
    covered = 0
    
    # Check extracted_params
    extracted = plan.get("extracted_params", [])
    if isinstance(extracted, list):
        extracted_names = {
            param.get("name") for param in extracted if isinstance(param, dict)
        }
        covered += len(required_fields & extracted_names)
    
    # Check if missing_params explicitly lists uncovered fields
    missing = plan.get("missing_params", [])
    if isinstance(missing, list):
        missing_set = set(missing)
        # Fields in missing_params are acknowledged but not covered
        covered += len(required_fields - missing_set - (extracted_names if 'extracted_names' in locals() else set()))
    
    return round(covered / len(required_fields), 2)


__all__ = [
    "persist_plan_json",
    "load_last_plan_json",
    "init_metrics_csv",
    "append_metrics",
    "persist_two_stage_search",
    "calculate_completion_rate",
]
