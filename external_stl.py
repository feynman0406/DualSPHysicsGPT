from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _first_env(*keys: str) -> Optional[str]:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value else None
    try:
        return str(value)
    except Exception:
        return None


def _load_json_payload(raw: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):  # raw may be None or invalid JSON
        return None
    if isinstance(data, dict):
        return data
    return None


def _load_json_from_path(path_str: str) -> Optional[Dict[str, Any]]:
    path = Path(path_str).expanduser()
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _merge_context(base: Dict[str, Any], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not extra:
        return base
    for key, value in extra.items():
        if key not in base and value is not None:
            base[key] = value
    return base


def _normalize_context(raw: Dict[str, Any]) -> Optional[Dict[str, str]]:
    stored_rel = _coerce_str(
        raw.get("stored_relative_path")
        or raw.get("relative_path")
        or raw.get("stored_rel_path")
        or raw.get("stored_rel")
    )
    stored_path = _coerce_str(
        raw.get("stored_path")
        or raw.get("stored_full_path")
        or raw.get("stored_filepath")
        or raw.get("stored_abspath")
    )
    source_path = _coerce_str(
        raw.get("source_path")
        or raw.get("original_path")
        or raw.get("source")
        or raw.get("uploaded_path")
    )
    run_id = _coerce_str(raw.get("run_id"))
    original_filename = _coerce_str(
        raw.get("original_filename")
        or raw.get("filename")
        or raw.get("original_name")
    )
    stored_filename = _coerce_str(
        raw.get("stored_filename")
        or raw.get("target_filename")
    )

    if not original_filename and source_path:
        original_filename = Path(source_path).name
    if not original_filename and stored_path:
        original_filename = Path(stored_path).name
    if not original_filename and stored_rel:
        original_filename = Path(stored_rel).name

    if not stored_filename and stored_path:
        stored_filename = Path(stored_path).name
    if not stored_filename and stored_rel:
        stored_filename = Path(stored_rel).name

    if stored_rel:
        stored_rel = stored_rel.replace("\\", "/")

    result: Dict[str, str] = {}
    if original_filename:
        result["original_filename"] = original_filename
    if stored_filename and stored_filename != result.get("original_filename"):
        result["stored_filename"] = stored_filename
    if stored_rel:
        result["stored_relative_path"] = stored_rel
    if stored_path:
        result["stored_path"] = stored_path
    if source_path:
        result["source_path"] = source_path
    if run_id:
        result["run_id"] = run_id

    if not result.get("stored_relative_path") and not result.get("stored_path"):
        return None
    return result


def get_external_stl_context() -> Optional[Dict[str, str]]:
    """Return metadata about a user-provided external STL, when available."""
    base: Dict[str, Any] = {}

    # Direct environment variables
    base = _merge_context(
        base,
        {
            "stored_relative_path": _first_env(
                "MVP_EXTERNAL_STL_REL_PATH",
                "MVP_EXTERNAL_STL_RELATIVE_PATH",
            ),
            "stored_path": _first_env(
                "MVP_EXTERNAL_STL_STORED_PATH",
                "DSPH_EXTERNAL_STL_STORED_PATH",
            ),
            "source_path": _first_env(
                "MVP_EXTERNAL_STL_SOURCE_PATH",
                "MVP_EXTERNAL_STL_SOURCE",
            ),
            "run_id": _first_env(
                "MVP_RUN_ID",
                "DSPH_RUN_ID",
            ),
        },
    )

    # JSON blobs provided via environment variables
    for key in (
        "MVP_EXTERNAL_STL_CONTEXT",
        "DSPH_EXTERNAL_STL_CONTEXT",
        "MVP_EXTERNAL_STL_INFO",
        "DSPH_EXTERNAL_STL_INFO",
    ):
        raw = os.environ.get(key)
        if raw:
            base = _merge_context(base, _load_json_payload(raw))

    # JSON payload from file paths
    for key in (
        "MVP_EXTERNAL_STL_CONTEXT_PATH",
        "DSPH_EXTERNAL_STL_CONTEXT_PATH",
    ):
        path_value = os.environ.get(key)
        if path_value:
            base = _merge_context(base, _load_json_from_path(path_value))

    normalized = _normalize_context(base)
    return normalized


__all__ = ["get_external_stl_context"]
