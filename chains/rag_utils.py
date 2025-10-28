"""Shared helpers for RAG metadata and logging."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from rag.openai_file_search import get_last_run_info
from external_stl import get_external_stl_context

_CASE_PATTERNS = [
    # Note: keep more specific patterns first
    (("solitarywave", "solitary wave"), "solitary_wave"),
    (("waverunup",), "wave_runup"),
    (("wavemaker", "wave maker"), "wavemaker"),
    (("piston",), "wavemaker"),
    (("flap",), "wavemaker"),
    (("wavesfrcylinder",), "flow_around_object"),
    (("wave",), "wave"),
    (("dambreak", "dam break"), "dambreak"),
    (("fsi",), "floating_body"),
    (("floating",), "floating_body"),
    (("movingsquare", "moving square"), "moving_body"),
    (("turekhron",), "moving_body"),
    (("flowfrcylinder",), "flow_around_object"),
    (("poiseuille",), "channel_flow"),
    (("sloshing",), "sloshing"),
    (("pump",), "pump"),
    (("rollingtank",), "rolling_tank"),
    (("duckling",), "duckling"),
    (("bathymetry",), "bathymetry"),
    (("damping",), "damping"),
    (("periodicity",), "periodicity"),
    (("bowling",), "bowling"),
    (("solids",), "solids"),
]

_FEATURE_PATTERNS = [
    (("mdbc",), "mDBC"),
    (("dbc",), "DBC"),
    (("chrono",), "Chrono"),
    (("ns", "non-newtonian"), "Non-Newtonian"),
    # Note: "fsi" is also a case_type, which is fine
    (("fsi",), "FSI"),
    (("fs",), "FS"),
]


def use_openai_file_search() -> bool:
    """Return True when OpenAI File Search RAG backend is enabled."""
    return os.environ.get("USE_OPENAI_FILE_SEARCH", "1") == "1"


def build_metadata_filter(text: str) -> Dict[str, str]:
    """Derive simple metadata filters from task text."""
    filters: Dict[str, str] = {}
    lowered = (text or "").lower()

    # Find case_type (stop after first match)
    for needles, label in _CASE_PATTERNS:
        if any(token in lowered for token in needles):
            filters["case_type"] = label
            break

    # Find dimension
    if any(token in lowered for token in ("3d", "3-d", "three-dimensional", "3 dimension")):
        filters["dim"] = "3D"
    elif any(token in lowered for token in ("2d", "2-d", "two-dimensional", "2 dimension")):
        filters["dim"] = "2D"

    if get_external_stl_context():
        filters["features"] = "externalstl"

    return filters


def persist_sources(role: str) -> None:
    """Persist the latest file-search sources for a given agent role."""
    info = get_last_run_info()
    if not info:
        return
    sources = info.get("sources")
    if sources is None:
        return
    base = Path("logs/last_run")
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    target = base / f"{role}_sources.json"
    summary_target = base / f"{role}_sources.txt"
    try:
        payload = json.dumps(sources, indent=2, ensure_ascii=False)
        target.write_text(payload, encoding="utf-8")

        summary_lines = []
        for idx, source in enumerate(sources, 1):
            meta = source.get("metadata") or source.get("attributes") or {}
            if not isinstance(meta, dict):
                meta = {}
            label = (
                source.get("filename")
                or meta.get("source_path")
                or meta.get("filename")
                or source.get("file_id")
                or f"source_{idx}"
            )
            score = source.get("score")
            header = f"[{idx}] {label}"
            if score is not None:
                header += f" (score={score})"
            summary_lines.append(header)
            snippets = source.get("snippets")
            if isinstance(snippets, list):
                for snippet in snippets[:3]:
                    if not isinstance(snippet, str):
                        continue
                    snippet_clean = " ".join(snippet.strip().split())
                    if len(snippet_clean) > 280:
                        snippet_clean = snippet_clean[:277] + "..."
                    summary_lines.append(f"    {snippet_clean}")
            summary_lines.append("")

        summary_text = "\n".join(summary_lines).strip()
        if summary_text:
            summary_target.write_text(summary_text + "\n", encoding="utf-8")
        elif summary_target.exists():
            try:
                summary_target.unlink()
            except Exception:
                pass
    except Exception:
        return


