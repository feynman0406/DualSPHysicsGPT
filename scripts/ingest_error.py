#!/usr/bin/env python
"""Ingest the error corpus into an OpenAI vector store."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.openai_file_search import create_or_get_vector_store, ingest_directory

DEFAULT_ROOT = REPO_ROOT / "data" / "error_corpus"
DEFAULT_STORE_NAME = "DualSPHysics-Error"
REGISTRY_PATH = REPO_ROOT / "rag" / "vector_stores.json"
ENV_PATH = REPO_ROOT / ".env"

_CASE_PATTERNS = [
    ("dambreak", "dambreak"),
    ("wavemaker", "wavemaker"),
    ("sloshing", "sloshing"),
    ("poiseuille", "poiseuille"),
    ("floating", "floating"),
    ("rolling", "rolling_tank"),
    ("pump", "pump"),
]


def _read_preview(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return path.name


def _classify_case(text: str, path: Path) -> str:
    haystack = f"{path.name.lower()}\n{text.lower()}"
    for needle, label in _CASE_PATTERNS:
        if needle in haystack:
            return label
    return "generic"


def _classify_dim(text: str) -> str:
    lower = text.lower()
    if "3d" in lower or "three-dimensional" in lower:
        return "3D"
    if "2d" in lower or "two-dimensional" in lower:
        return "2D"
    return "na"


def _error_metadata(path: Path) -> Dict[str, Any]:
    preview = _read_preview(path)
    case_type = _classify_case(preview, path)
    dim = _classify_dim(preview)
    metadata = {
        "corpus": "error",
        "case_type": case_type,
        "dim": dim,
        "lang": "en",
        "file_ext": path.suffix.lower().lstrip(".") or "txt",
    }
    hint = f"{case_type.replace('_', ' ')} issue log ({path.name})" if case_type else None
    return {"metadata": metadata, "hint": hint}


def _update_registry(registry_path: Path, key: str, value: str) -> None:
    registry: Dict[str, str] = {}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception:
            registry = {}
    registry[key] = value
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


def _update_env_var(env_path: Path, key: str, value: str) -> None:
    lines: list[str]
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
    updated = False
    for idx, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[idx] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest the error corpus into an OpenAI vector store.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Root directory containing error corpus files")
    parser.add_argument("--name", default=DEFAULT_STORE_NAME, help="Vector store name to create or reuse")
    parser.add_argument("--no-env", action="store_true", help="Skip updating the .env file with the resulting ID")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH, help="Path to the vector store registry JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()

    root = args.root.resolve()
    if not root.exists():
        raise SystemExit(f"Corpus directory not found: {root}")

    store_id = create_or_get_vector_store(args.name)
    ingest_directory(store_id, root, _error_metadata)

    _update_registry(args.registry, "error", store_id)
    if not args.no_env:
        _update_env_var(ENV_PATH, "OPENAI_RAG_VS_ERROR_ID", store_id)

    print(f"Vector store '{args.name}' ready: {store_id}")
    print(f"Registry updated at {args.registry}")
    if args.no_env:
        print("Update .env with: OPENAI_RAG_VS_ERROR_ID=" + store_id)
    else:
        print(f".env updated with OPENAI_RAG_VS_ERROR_ID={store_id}")


if __name__ == "__main__":
    main()
