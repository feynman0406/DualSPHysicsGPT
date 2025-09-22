"""Retrieval helpers for DualSPHysicsGPT."""

from __future__ import annotations

import logging
import os
import pickle
from functools import lru_cache
from typing import Optional

from langchain_core.vectorstores import VectorStoreRetriever
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

LOGGER = logging.getLogger(__name__)

_DEFAULT_IDX_DIR = "rag/indexes"
_DEFAULT_TOP_K = 8
_SUPPORTED_PROVIDERS = {"openai"}


class RetrieverInitError(RuntimeError):
    """Raised when retrieval initialisation fails."""


def _idx_dir() -> str:
    return os.environ.get("IDX_DIR", _DEFAULT_IDX_DIR)


def _default_k() -> int:
    raw = os.environ.get("TOP_K", str(_DEFAULT_TOP_K))
    try:
        value = int(raw)
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        LOGGER.warning("Invalid TOP_K value '%s'; falling back to %s", raw, _DEFAULT_TOP_K)
        return _DEFAULT_TOP_K


def _provider() -> str:
    return os.environ.get("EMBEDDING_PROVIDER", "openai").lower()


def _embedding() -> OpenAIEmbeddings:
    provider = _provider()
    if provider not in _SUPPORTED_PROVIDERS:
        raise RetrieverInitError(
            f"Unsupported EMBEDDING_PROVIDER '{provider}'. Supported providers: {sorted(_SUPPORTED_PROVIDERS)}"
        )
    try:
        return OpenAIEmbeddings()
    except Exception as exc:  # pragma: no cover - defensive guard
        raise RetrieverInitError(f"Failed to initialise OpenAI embeddings: {exc}") from exc


def _load_bm25(pkl_path: str, k: int) -> Optional[BM25Retriever]:
    try:
        with open(pkl_path, "rb") as handle:
            docs = pickle.load(handle)
    except FileNotFoundError:
        LOGGER.warning("BM25 index missing: %s", pkl_path)
        return None
    except Exception as exc:
        LOGGER.error("Failed to load BM25 index %s: %s", pkl_path, exc)
        return None

    retriever = BM25Retriever.from_documents(docs)
    retriever.k = k
    return retriever


def _load_faiss(path: str, k: int) -> Optional[VectorStoreRetriever]:
    try:
        store = FAISS.load_local(path, embeddings=_embedding(), allow_dangerous_deserialization=True)
    except FileNotFoundError:
        LOGGER.warning("FAISS index missing: %s", path)
        return None
    except Exception as exc:
        LOGGER.error("Failed to load FAISS index %s: %s", path, exc)
        return None

    retriever = store.as_retriever(search_kwargs={"k": k})
    retriever.search_kwargs["k"] = k
    return retriever


def _join_idx(name: str) -> str:
    return os.path.join(_idx_dir(), name)


def _build_ensemble(name: str, *, k: int) -> Optional[EnsembleRetriever]:
    faiss_name = f"{name}_faiss"
    bm25_name = f"{name}_bm25.pkl"

    faiss_retr = _load_faiss(_join_idx(faiss_name), k)
    bm25_retr = _load_bm25(_join_idx(bm25_name), k)

    components = [r for r in (faiss_retr, bm25_retr) if r]
    if not components:
        LOGGER.warning("No retrievers available for index '%s'", name)
        return None
    if len(components) == 1:
        LOGGER.info("Using single retriever for '%s': %s", name, components[0].__class__.__name__)
        return components[0]
    return EnsembleRetriever(retrievers=components, weights=[0.6, 0.4])


@lru_cache(maxsize=4)
def _design_cached(k: int) -> Optional[EnsembleRetriever]:
    return _build_ensemble("design", k=k)


@lru_cache(maxsize=4)
def _error_cached(k: int) -> Optional[EnsembleRetriever]:
    return _build_ensemble("error", k=k)


def _normalise_k(k: Optional[int]) -> int:
    if k is None:
        return _default_k()
    try:
        value = int(k)
    except (TypeError, ValueError):
        LOGGER.warning("Invalid explicit k value %s; falling back to default", k)
        return _default_k()
    if value <= 0:
        LOGGER.warning("Explicit k must be positive (got %s); falling back to default", value)
        return _default_k()
    return value


def design_retriever(k: Optional[int] = None) -> Optional[EnsembleRetriever]:
    return _design_cached(_normalise_k(k))


def error_retriever(k: Optional[int] = None) -> Optional[EnsembleRetriever]:
    return _error_cached(_normalise_k(k))


def reset_cached_retrievers() -> None:
    """Clear cached retriever instances so new env settings take effect."""
    _design_cached.cache_clear()
    _error_cached.cache_clear()


__all__ = [
    "design_retriever",
    "error_retriever",
    "reset_cached_retrievers",
    "RetrieverInitError",
]

