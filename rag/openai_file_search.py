"""OpenAI Vector Store + File Search adapter for DualSPHysicsGPT."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import httpx
import time
import random
from openai import APIConnectionError, APITimeoutError
from external_stl import get_external_stl_context
from openai import OpenAI, BadRequestError
from openai.types.responses import Response
from openai.types.responses.response_file_search_tool_call import ResponseFileSearchToolCall
from openai.types.responses.response_output_text import (
    AnnotationFileCitation,
    AnnotationContainerFileCitation,
    ResponseOutputText,
)

LOGGER = logging.getLogger(__name__)

_LAST_RUN_INFO: Dict[str, Any] | None = None
_DEFAULT_SEARCH_LIMIT = 20

# Based on OpenAI API documentation and observed errors
_SUPPORTED_OPENAI_EXTS = {
    ".c", ".cpp", ".css", ".csv", ".doc", ".docx", ".gif", ".go", ".html",
    ".java", ".jpeg", ".jpg", ".js", ".json", ".md", ".pdf", ".php",
    ".pkl", ".png", ".pptx", ".py", ".rb", ".tar", ".tex", ".ts",
    ".txt", ".webp", ".xlsx", ".zip",
    # XML files are consistently rejected by the API with "File type not supported"
    # and will be handled by the local RAG implementation instead.
}


@dataclass
class NormalizedMetadata:
    """Normalized metadata returned by ingest helpers."""

    metadata: Dict[str, str]
    hint: Optional[str] = None
    skip: bool = False
    checksum: Optional[str] = None
    source_path: Optional[str] = None


def get_last_run_info() -> Optional[Dict[str, Any]]:
    """Return a deep copy of the last logged file search run."""
    if isinstance(_LAST_RUN_INFO, dict):
        return json.loads(json.dumps(_LAST_RUN_INFO))
    return None


def clear_last_run_info() -> None:
    """Clear any cached run info (mainly useful for tests)."""
    global _LAST_RUN_INFO
    _LAST_RUN_INFO = None


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")
    
    # Use httpx.Client for more robust networking, including proxy support.
    # The SSL EOF error often points to network-level issues (proxies, firewalls).
    # Configuring a client explicitly can help manage timeouts and proxy settings.
    http_client = httpx.Client(
        proxies=os.environ.get("https_proxy") or os.environ.get("http_proxy"),
        timeout=httpx.Timeout(360.0, connect=10.0),  # Increased timeout to 3 minutes
        http2=True,  # Enable HTTP/2 if available
        follow_redirects=True,
    )
    
    return OpenAI(api_key=api_key, http_client=http_client)


@lru_cache(maxsize=4)
def get_file_id_to_name_map(vector_store_id: str) -> Dict[str, str]:
    """Return a mapping from file_id to its original source_path or filename."""
    client = _client()
    mapping: Dict[str, str] = {}
    try:
        page = client.vector_stores.files.list(vector_store_id=vector_store_id, limit=100, order="asc")
        while True:
            for item in page.data:
                attrs = item.attributes or {}
                # Prioritize source_path, but fall back to filename.
                name = str(attrs.get("source_path") or item.filename or item.id)
                mapping[item.id] = name
            if not page.has_next_page():
                break
            next_page = page.get_next_page()
            if next_page is None:
                break
            page = next_page
    except Exception as exc:
        LOGGER.error("Failed to build file ID map for vector store %s: %s", vector_store_id, exc)
    return mapping


def create_or_get_vector_store(name: str) -> str:
    """Return the id for a named vector store, creating it when missing."""
    client = _client()
    page = client.vector_stores.list(limit=100, order="asc")
    while True:
        for item in page.data:
            if (getattr(item, "name", "") or "").lower() == name.lower():
                LOGGER.info("Reusing existing vector store '%s' (%s)", name, item.id)
                return item.id
        if not page.has_next_page():
            break
        next_page = page.get_next_page()
        if next_page is None:
            break
        page = next_page
    created = client.vector_stores.create(name=name)
    LOGGER.info("Created vector store '%s' (%s)", name, created.id)
    return created.id


def _serialise_metadata(raw: Dict[str, Any]) -> Dict[str, str]:
    serialised: Dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = ",".join(str(v) for v in value if v is not None)
        elif isinstance(value, bool):
            value = "1" if value else "0"
        else:
            value = str(value)
        value = value.strip()
        if not value:
            continue
        serialised[str(key)] = value[:512]
    return serialised


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_metadata(path: Path, metadata_fn: Callable[[Path], Any], root_dir: Path) -> NormalizedMetadata:
    raw = metadata_fn(path) if metadata_fn else {}
    hint: Optional[str] = None
    skip = False
    metadata: Dict[str, Any] = {}

    if isinstance(raw, tuple):
        if len(raw) >= 1 and isinstance(raw[0], dict):
            metadata = dict(raw[0])
        hint = raw[1] if len(raw) >= 2 else None
        if len(raw) >= 3:
            skip = bool(raw[2])
    elif isinstance(raw, dict):
        work = dict(raw)
        hint = work.pop("hint", None)
        skip = bool(work.pop("skip", False))
        block = work.pop("metadata", None)
        if isinstance(block, dict):
            metadata = dict(block)
        else:
            metadata = work
    elif raw is None:
        metadata = {}
    else:
        try:
            metadata = dict(raw)  # type: ignore[arg-type]
        except Exception:
            metadata = {}

    try:
        relative = str(path.relative_to(root_dir))
    except ValueError:
        relative = str(path)
    metadata.setdefault("source_path", relative)
    metadata.setdefault("filename", path.name)

    checksum = None
    try:
        checksum = _hash_file(path)
        metadata.setdefault("sha256", checksum)
    except Exception as exc:
        LOGGER.warning("Unable to compute checksum for %s: %s", path, exc)

    serialised = _serialise_metadata(metadata)
    return NormalizedMetadata(metadata=serialised, hint=hint, skip=skip, checksum=checksum, source_path=serialised.get("source_path"))


def _existing_keys(client: OpenAI, vector_store_id: str) -> Dict[Tuple[str, str], bool]:
    seen: Dict[Tuple[str, str], bool] = {}
    page = client.vector_stores.files.list(vector_store_id=vector_store_id, limit=100, order="asc")
    while True:
        for item in page.data:
            attrs = item.attributes or {}
            key = (str(attrs.get("source_path") or ""), str(attrs.get("sha256") or ""))
            if key[0] and key[1]:
                seen[key] = True
        if not page.has_next_page():
            break
        next_page = page.get_next_page()
        if next_page is None:
            break
        page = next_page
    return seen


def _upload_file_path(client: OpenAI, vector_store_id: str, path: Path, metadata: Dict[str, str]) -> str:
    with path.open("rb") as handle:
        file_obj = client.files.create(file=handle, purpose="assistants")
    client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_obj.id,
        attributes=metadata,
    )
    return file_obj.id


def _upload_hint_text(client: OpenAI, vector_store_id: str, origin_metadata: Dict[str, str], hint_text: str) -> str:
    buffer = io.BytesIO(hint_text.encode("utf-8"))
    hint_name = f"{origin_metadata.get('filename', 'hint')}.hint.txt"
    buffer.name = hint_name  # type: ignore[attr-defined]
    buffer.seek(0)
    file_obj = client.files.create(file=buffer, purpose="assistants")
    hint_metadata = dict(origin_metadata)
    hint_metadata["is_hint"] = "1"
    hint_metadata["source_path"] = f"{origin_metadata.get('source_path', hint_name)}::hint"
    client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_obj.id,
        attributes=_serialise_metadata(hint_metadata),
    )
    return file_obj.id


def ingest_directory(vector_store_id: str, root_dir: Path, metadata_fn: Callable[[Path], Any]) -> None:
    """Upload a corpus directory into a vector store with metadata-aware filtering."""
    client = _client()
    base = root_dir.expanduser().resolve()
    if not base.exists():
        raise FileNotFoundError(f"Corpus directory not found: {base}")
    if not base.is_dir():
        raise NotADirectoryError(f"Corpus path is not a directory: {base}")

    existing = _existing_keys(client, vector_store_id)
    total = uploaded = skipped = 0

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue

        # Filter by supported extensions BEFORE attempting any processing
        if path.suffix.lower() not in _SUPPORTED_OPENAI_EXTS:
            LOGGER.debug("Skipping %s (unsupported extension for OpenAI).", path)
            continue

        total += 1
        normalized = _normalize_metadata(path, metadata_fn, base)
        if normalized.skip:
            skipped += 1
            LOGGER.debug("Skipping %s due to metadata_fn skip flag.", path)
            continue
        key = (normalized.metadata.get("source_path", ""), normalized.metadata.get("sha256", ""))
        if key[0] and key[1] and key in existing:
            skipped += 1
            LOGGER.debug("Skipping %s (already ingested).", path)
            continue
        try:
            _upload_file_path(client, vector_store_id, path, normalized.metadata)
            uploaded += 1
            if key[0] and key[1]:
                existing[key] = True
            if normalized.hint and normalized.hint.strip():
                _upload_hint_text(client, vector_store_id, normalized.metadata, normalized.hint.strip())
        except Exception as exc:
            LOGGER.error("Failed to ingest %s: %s", path, exc)

    LOGGER.info(
        "Ingest summary: vector_store=%s total_supported_files=%d uploaded=%d skipped=%d",
        vector_store_id,
        total,
        uploaded,
        skipped,
    )


def _messages_to_input(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        items.append(
            {
                "type": "message",
                "role": role,
                "content": [
                    {
                        "type": "input_text",
                        "text": str(content),
                    }
                ],
            }
        )
    return items


def _build_filter_payload(metadata_filter: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not metadata_filter:
        return None
    filters = []
    for key, value in metadata_filter.items():
        if value is None:
            continue
        filters.append({"type": "eq", "key": str(key), "value": str(value)})
    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"type": "and", "filters": filters}


def _structured_query(text: str) -> Dict[str, List[str]]:
    lowered = text.lower()
    must: set[str] = set()
    should: set[str] = set()
    must_not: set[str] = set()

    def has(*variants: str) -> bool:
        return any(v in lowered for v in variants)

    if has("dambreak", "dam break", "dam-break", "溃坝", "破堤"):
        must.add("dambreak")
        should.update({"dam break", "dam-break", "溃坝", "破堤"})
        must_not.update({"wavemaker", "piston", "flap"})
    if has("mdbc", "m-dbc", "modified dynamic boundary", "modified dynamic boundary condition"):
        must.add("mdbc")
        should.update({"modified dynamic boundary", "m-dbc", "modified dynamic boundary condition"})
    if has("wavemaker", "wave maker", "wave-maker", "造波机", "造浪机"):
        must.add("wavemaker")
        should.update({"wave maker", "wave-maker", "piston wavemaker"})
        if "dambreak" not in must:
            must_not.add("dambreak")
    if has("fillbox"):
        must.add("fillbox")
    if has("sluice"):
        must.add("sluice gate")
        should.add("sluice")
    if has("piston"):
        should.add("piston")
    if has("flap"):
        should.add("flap")

    if has("2d", "2-d", "two-dimensional", "2 dimension"):
        must.add("2D")
        if "3D" not in must:
            must_not.add("3D")
    if has("3d", "3-d", "three-dimensional", "3 dimension"):
        must.add("3D")
        if "2D" not in must:
            must_not.add("2D")

    for axis in ("x", "y", "z"):
        for match in re.finditer(rf"{axis}\s*=\s*[-+]?\d*\.?\d+", text, flags=re.IGNORECASE):
            token = match.group(0).replace(" ", "")
            must.add(token)

    for token in ("inlet", "outlet", "gate", "tank", "reservoir"):
        if has(token):
            should.add(token)

    return {
        "must": sorted(must),
        "should": sorted(should),
        "must_not": sorted(must_not),
    }



def _apply_external_stl_bias(spec: Dict[str, List[str]], ctx: Optional[Dict[str, str]]) -> Dict[str, List[str]]:
    """Add the 'externalstl' keyword to query requirements when context is available."""
    if not ctx:
        return spec
    must_terms = set(spec.get("must", []))
    if "externalstl" in must_terms:
        return spec
    biased = {key: (list(value) if isinstance(value, list) else value) for key, value in spec.items()}
    must_terms.add("externalstl")
    biased["must"] = sorted(must_terms)
    if "should" not in biased:
        biased["should"] = []
    if "must_not" not in biased:
        biased["must_not"] = []
    return biased

def _compose_query_text(spec: Dict[str, List[str]], raw_query: str) -> str:
    parts: List[str] = []
    if spec["must"]:
        parts.append("MUST: " + ", ".join(spec["must"]))
    if spec["should"]:
        parts.append("SHOULD: " + ", ".join(spec["should"]))
    if spec["must_not"]:
        parts.append("AVOID: " + ", ".join(spec["must_not"]))

    raw_clean = re.sub(r"\s+", " ", raw_query).strip() if raw_query else ""
    if raw_clean:
        base_text = " | ".join(parts) if parts else ""
        separator = " | " if base_text else ""
        available = 512 - len(base_text) - len(separator) - len("RAW: ")
        if available > 0:
            parts.append(f"RAW: {raw_clean[:available]}")
    return " | ".join(parts)


def _inject_query_hint(messages: Sequence[Dict[str, Any]], spec: Dict[str, List[str]], raw_query: str) -> List[Dict[str, Any]]:
    raw_clean = re.sub(r"\s+", " ", raw_query).strip() if raw_query else ""
    if not any(spec.values()) and not raw_clean:
        return list(messages)

    hint_lines: List[str] = []
    if spec["must"]:
        hint_lines.append(f"MUST: {', '.join(spec['must'])}")
    if spec["should"]:
        hint_lines.append(f"SHOULD: {', '.join(spec['should'])}")
    if spec["must_not"]:
        hint_lines.append(f"MUST_NOT: {', '.join(spec['must_not'])}")
    if raw_clean:
        hint_lines.append(f"RAW: {raw_clean[:256]}")

    hint_text = (
        "Use the OpenAI File Search tool with the following retrieval directives.\n"
        + "\n".join(hint_lines)
    )
    return [{"role": "system", "content": hint_text}] + list(messages)


def _select_filter_and_search(
    client: OpenAI,
    vector_store_ids: Sequence[str],
    query_text: str,
    metadata_filter: Optional[Dict[str, Any]],
    rewrite: bool,
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    filter_candidates: List[Optional[Dict[str, Any]]] = []
    if metadata_filter:
        base = dict(metadata_filter)
        filter_candidates.append(base)
        if "dim" in base:
            reduced = dict(base)
            reduced.pop("dim", None)
            if reduced not in filter_candidates:
                filter_candidates.append(reduced)
        if "case_type" in base:
            reduced = dict(base)
            reduced.pop("case_type", None)
            if reduced not in filter_candidates:
                filter_candidates.append(reduced)
    filter_candidates.append(None)

    attempt_summaries: List[Dict[str, Any]] = []
    selected_filter: Optional[Dict[str, Any]] = None

    for candidate in filter_candidates:
        filter_payload = _build_filter_payload(candidate)
        attempt_entry = {
            "metadata_filter": candidate,
            "results": [],
        }
        for vs_id in vector_store_ids:
            try:
                page = client.vector_stores.search(
                    vs_id,
                    query=query_text or "",
                    filters=filter_payload,
                    max_num_results=_DEFAULT_SEARCH_LIMIT,
                    rewrite_query=rewrite,
                )
                for result in page.data: 
                    attempt_entry["results"].append(
                        {
                            "vector_store_id": vs_id,
                            "file_id": result.file_id,
                            "filename": result.filename,
                            "score": result.score,
                            "attributes": result.attributes or {},
                            "text": (result.content[0].text if getattr(result, "content", None) else "")[:600],
                        }
                    )
            except Exception as exc:
                LOGGER.warning("Vector store search failed (vs=%s): %s", vs_id, exc)
        attempt_summaries.append(attempt_entry)
        if attempt_entry["results"]:
            selected_filter = candidate
            break

    if selected_filter is None and filter_candidates:
        selected_filter = filter_candidates[-1]

    return selected_filter, attempt_summaries


def _collect_annotations(resp: Response) -> List[Dict[str, Any]]:
    annotations: List[Dict[str, Any]] = []
    if not resp.output:
        return annotations
    for item in resp.output:
        if isinstance(item, ResponseOutputText):
            for annotation in item.annotations:
                if isinstance(annotation, AnnotationFileCitation):
                    annotations.append(
                        {
                            "type": "file_citation",
                            "file_id": annotation.file_id,
                            "filename": annotation.filename,
                            "index": annotation.index,
                        }
                    )
                elif isinstance(annotation, AnnotationContainerFileCitation):
                    annotations.append(
                        {
                            "type": "container_file_citation",
                            "file_id": annotation.file_id,
                            "filename": annotation.filename,
                            "container_id": annotation.container_id,
                            "start_index": annotation.start_index,
                            "end_index": annotation.end_index,
                        }
                    )
                else:
                    annotations.append({"type": getattr(annotation, "type", "unknown")})
    return annotations


def _collect_tool_calls(resp: Response) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    if not resp.output:
        return calls
    for item in resp.output:
        if isinstance(item, ResponseFileSearchToolCall):
            calls.append(
                {
                    "id": item.id,
                    "status": item.status,
                    "queries": item.queries,
                    "results": [
                        {
                            "file_id": res.file_id,
                            "filename": res.filename,
                            "score": res.score,
                            "attributes": res.attributes or {},
                        }
                        for res in (item.results or [])
                    ],
                }
            )
    return calls


def _derive_sources(tool_calls: List[Dict[str, Any]], search_attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for call in tool_calls:
        for result in call.get("results", []):
            file_id = result.get("file_id")
            if not file_id or file_id in seen:
                continue
            entry = dict(result)
            entry["search_call_id"] = call.get("id")
            seen.add(file_id)
            sources.append(entry)
    if not sources:
        for attempt in search_attempts:
            for result in attempt.get("results", []):
                file_id = result.get("file_id")
                if not file_id or file_id in seen:
                    continue
                entry = dict(result)
                seen.add(file_id)
                sources.append(entry)
    return sources


def _persist_last_run(info: Dict[str, Any]) -> None:
    base = Path("logs/last_run")
    base.mkdir(parents=True, exist_ok=True)
    (base / "metadata.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    response_text = info.get("response_text")
    if isinstance(response_text, str):
        (base / "response.txt").write_text(response_text, encoding="utf-8")
    sources = info.get("sources")
    if sources is not None:
        (base / "sources.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")


def response_with_file_search(
    messages: List[Dict[str, Any]],
    model: str,
    vector_store_ids: List[str],
    metadata_filter: Optional[Dict[str, Any]] = None,
    max_output_tokens: int = 14000,
    query_rewrite: bool = True,
    temperature: Optional[float] = None,
    reasoning: Optional[Dict[str, Any]] = None,
    raw_query: Optional[str] = None,
) -> str:
    """Call the OpenAI Responses API with File Search enabled."""
    if not vector_store_ids:
        raise ValueError("vector_store_ids must contain at least one id.")

    client = _client()

    prompt_hash = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    combined_text = " ".join(
        str(m.get("content", "")) for m in messages if str(m.get("role", "user")).lower() != "assistant"
    )
    user_segments = [
        str(m.get("content", "")) for m in messages if str(m.get("role", "")).lower() == "user"
    ]
    user_text = " ".join(user_segments).strip()
    effective_raw = (raw_query or user_text or combined_text).strip()

    query_spec = _structured_query(effective_raw)
    external_stl_ctx = get_external_stl_context()
    query_spec = _apply_external_stl_bias(query_spec, external_stl_ctx)
    query_text = _compose_query_text(query_spec, effective_raw) or raw_query[:512]
    selected_filter, search_attempts = _select_filter_and_search(
        client, vector_store_ids, query_text, metadata_filter, query_rewrite
    )

    messages_with_hint = _inject_query_hint(messages, query_spec, effective_raw)
    matches_found = any(entry.get("results") for entry in search_attempts if entry.get("metadata_filter") == selected_filter)
    if not matches_found and search_attempts:
        messages_with_hint = [
            {
                "role": "system",
                "content": (
                    "No corpus files matched the retrieval filters. "
                    "Answer from general knowledge and make sure run logs record 'No source matched'."
                ),
            },
            *messages_with_hint,
        ]

    input_payload = _messages_to_input(messages_with_hint)
    tool_config: Dict[str, Any] = {
        "type": "file_search",
        "vector_store_ids": list(vector_store_ids),
    }
    filter_payload = _build_filter_payload(selected_filter)
    if filter_payload:
        tool_config["filters"] = filter_payload

    request_kwargs: Dict[str, Any] = {
        "model": model,
        "input": input_payload,
        "tools": [tool_config],
        "max_output_tokens": max_output_tokens,
    }
    if temperature is not None:
        request_kwargs["temperature"] = float(temperature)
    if reasoning:
        request_kwargs["reasoning"] = reasoning

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            response = client.responses.create(**request_kwargs)
            break
        except (APIConnectionError, APITimeoutError) as e:
            if attempt < max_retries:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                LOGGER.warning(f"Connection/timeout error on attempt {attempt + 1}, retrying in {wait_time:.1f}s: {e}")
                time.sleep(wait_time)
                continue
            else:
                raise
        except Exception as e:
            # Re-raise non-connection errors immediately
            raise

    text = (getattr(response, "output_text", None) or "").strip()
    tool_calls = _collect_tool_calls(response)
    annotations = _collect_annotations(response)
    sources = _derive_sources(tool_calls, search_attempts)
    if not sources:
        sources = [{"note": "no_source_matched"}]

    info = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "model": model,
        "prompt_sha256": prompt_hash,
        "vector_store_ids": list(vector_store_ids),
        "original_metadata_filter": metadata_filter,
        "applied_metadata_filter": selected_filter,
        "query_text": query_text,
        "raw_query": effective_raw,
        "query_spec": query_spec,
        "search_attempts": search_attempts,
        "tool_calls": tool_calls,
        "annotations": annotations,
        "response_text": text,
        "max_output_tokens": max_output_tokens,
        "query_rewrite": query_rewrite,
        "temperature": temperature,
        "reasoning": json.loads(json.dumps(reasoning)) if reasoning else None,
        "sources": sources,
    }

    global _LAST_RUN_INFO
    _LAST_RUN_INFO = json.loads(json.dumps(info))
    _persist_last_run(info)

    if not text:
        raise RuntimeError("File Search request completed but the model returned no text.")
    return text


__all__ = [
    "create_or_get_vector_store",
    "ingest_directory",
    "response_with_file_search",
    "get_last_run_info",
    "clear_last_run_info",
    "get_file_id_to_name_map",
]



