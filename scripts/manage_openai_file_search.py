#!/usr/bin/env python3
"""
Utilities to purge and upload files for OpenAI File Search vector stores.

Usage examples:
  - Purge all files from a vector store (and delete underlying OpenAI files):
      python scripts/manage_openai_file_search.py purge --vector-store-id VS_ID

  - Upload all JSON files from AutoXml_script/config_library into a vector store:
      python scripts/manage_openai_file_search.py upload --vector-store-id VS_ID --dir AutoXml_script/config_library

Environment:
  - Requires OPENAI_API_KEY to be set.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Tuple

from openai import OpenAI
from openai import APIConnectionError, APITimeoutError

# Reuse our project&#x27;s OpenAI helpers for consistent httpx client/timeout/proxy settings
from rag.openai_file_search import ingest_directory  # type: ignore
from rag.openai_file_search import _client as get_oai_client  # type: ignore

LOGGER = logging.getLogger("manage_openai_file_search")


def _load_dotenv() -> None:
    """
    Lightweight .env loader (no external dependencies).
    Loads key=value pairs into os.environ if not already set.
    Searched locations:
      - Current working directory: .env
      - Project root (parent of this script's directory): .env
    """
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for p in candidates:
        try:
            if not p.exists():
                continue
            for raw in p.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
        except Exception:
            # Ignore parse errors and continue
            continue


def purge_vector_store(vector_store_id: str, delete_underlying_files: bool = True) -> Tuple[int, int]:
    """
    Remove all file associations from the given vector store.
    Optionally also delete the underlying OpenAI files.

    Returns:
        (removed_from_store_count, deleted_file_objects_count)
    """
    client: OpenAI = get_oai_client()

    removed = 0
    deleted = 0

    try:
        page = client.vector_stores.files.list(vector_store_id=vector_store_id, limit=100, order="asc")
    except Exception as exc:
        raise RuntimeError(f"Failed to list files for vector store {vector_store_id}: {exc}")

    file_ids = []
    file_id_to_name = {}
    while True:
        for item in page.data:
            file_ids.append(item.id)
            file_id_to_name[item.id] = getattr(item, "filename", None) or item.id
        if not page.has_next_page():
            break
        next_page = page.get_next_page()
        if next_page is None:
            break
        page = next_page

    if not file_ids:
        LOGGER.info("Vector store %s already empty.", vector_store_id)
        return (0, 0)

    LOGGER.info("Found %d file associations in vector store %s. Removing...", len(file_ids), vector_store_id)

    for fid in file_ids:
        fname = file_id_to_name.get(fid, fid)
        try:
            client.vector_stores.files.delete(vector_store_id=vector_store_id, file_id=fid)
            removed += 1
            LOGGER.info("Removed association: %s (%s)", fid, fname)
        except Exception as exc:
            LOGGER.error("Failed to remove association for %s (%s): %s", fid, fname, exc)

    if delete_underlying_files:
        LOGGER.info("Deleting %d underlying OpenAI file objects...", len(file_ids))
        for fid in file_ids:
            try:
                client.files.delete(fid)
                deleted += 1
                LOGGER.info("Deleted file object: %s", fid)
            except Exception as exc:
                LOGGER.warning("Failed to delete file object %s: %s", fid, exc)

    LOGGER.info("Purge complete. Removed associations: %d, Deleted files: %d", removed, deleted)
    return removed, deleted


def upload_config_directory(vector_store_id: str, directory: Path) -> None:
    """
    Upload supported files from a directory into the vector store.

    Notes:
      - We pass a metadata_fn that returns an empty dict to avoid schema assumptions.
      - Only supported extensions (per rag.openai_file_search) are uploaded.
    """
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Upload directory not found or not a directory: {directory}")
    LOGGER.info("Uploading supported files from %s into vector store %s ...", directory, vector_store_id)
    # Minimal metadata function (no filtering, no hints)
    metadata_fn = lambda _path: {}
    ingest_directory(vector_store_id=vector_store_id, root_dir=directory, metadata_fn=metadata_fn)
    LOGGER.info("Upload complete for directory: %s", directory)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    _load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")

    parser = argparse.ArgumentParser(description="Manage OpenAI File Search vector store contents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    purge_p = subparsers.add_parser("purge", help="Remove all files from a vector store (and optionally delete file objects)")
    purge_p.add_argument("--vector-store-id", required=True, help="Vector store id (e.g., vs_xxx)")
    purge_p.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep underlying OpenAI file objects (default is to delete them).",
    )

    upload_p = subparsers.add_parser("upload", help="Upload a directory of supported files into a vector store")
    upload_p.add_argument("--vector-store-id", required=True, help="Vector store id (e.g., vs_xxx)")
    upload_p.add_argument(
        "--dir",
        default="AutoXml_script/config_library",
        help="Directory to upload (default: AutoXml_script/config_library)",
    )

    args = parser.parse_args()

    if args.command == "purge":
        keep_files: bool = bool(getattr(args, "keep_files", False))
        removed, deleted = purge_vector_store(args.vector_store_id, delete_underlying_files=not keep_files)
        print({"removed_associations": removed, "deleted_files": deleted})
    elif args.command == "upload":
        directory = Path(getattr(args, "dir", "")).resolve()
        upload_config_directory(args.vector_store_id, directory)
        print({"uploaded_from": str(directory)})


if __name__ == "__main__":
    try:
        main()
    except (APIConnectionError, APITimeoutError) as e:
        LOGGER.error("Network error: %s", e)
        raise
    except Exception as e:
        LOGGER.error("Error: %s", e)
        raise
