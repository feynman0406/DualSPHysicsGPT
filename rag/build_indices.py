"""Build FAISS + BM25 indexes for DualSPHysicsGPT retrieval.

Usage:
    python rag/build_indices.py --design_dir data/design_corpus --error_dir data/error_corpus --out_dir rag/indexes

The command reads text-like corpora, filters unsupported or empty files, then writes FAISS stores and
pickleable BM25 document lists under the requested output directory. Existing indexes are overwritten.
"""

import argparse
import pickle
import sys
from pathlib import Path
from typing import Iterable, List

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from dotenv import load_dotenv

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise ImportError('Install langchain-text-splitters to enable document chunking.') from exc

load_dotenv()

SUPPORTED_EXTS = (".md", ".txt", ".xml", ".log", ".yaml", ".yml")
NO_CHUNK_EXTS = {".xml"}

# Keeps embedding batches below OpenAI token limits
EMBED_BATCH_SIZE = 64

# Chunk long files so individual embeddings stay small
TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=200,
)



class IndexBuildError(RuntimeError):
    """Raised when index building fails due to configuration issues."""


def validate_corpus_dir(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise IndexBuildError(f"[ERROR] {label} corpus directory not found: {resolved}")
    if not resolved.is_dir():
        raise IndexBuildError(f"[ERROR] {label} corpus path is not a directory: {resolved}")
    return resolved


def ensure_out_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise IndexBuildError(f"[ERROR] Output path exists but is not a directory: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def load_corpus(dirpath: Path, corpus_type: str) -> List[Document]:
    docs: List[Document] = []
    skipped_empty = 0
    for file_path in sorted(dirpath.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception as exc:
            print(f"[warn] {corpus_type}: skip {file_path} ({exc})")
            continue
        if not text:
            skipped_empty += 1
            continue
        if file_path.suffix.lower() in NO_CHUNK_EXTS:
            raw_chunks = [text]
        else:
            raw_chunks = TEXT_SPLITTER.split_text(text)
        chunks = [chunk.strip() for chunk in raw_chunks if chunk.strip()]
        if not chunks:
            skipped_empty += 1
            continue
        chunk_total = len(chunks)
        for idx, chunk in enumerate(chunks):
            meta = {
                "source": str(file_path),
                "corpus": corpus_type,
                "chunk": idx,
                "num_chunks": chunk_total,
            }
            docs.append(Document(page_content=chunk, metadata=meta))
        if chunk_total > 1:
            print(f"[info] {corpus_type}: split {file_path} into {chunk_total} chunks")
    if skipped_empty:
        print(f"[info] {corpus_type}: skipped {skipped_empty} empty files")
    return docs


def build_faiss(docs: List[Document], embeddings: OpenAIEmbeddings, path: Path) -> None:
    store = FAISS.from_documents(docs, embedding=embeddings)
    store.save_local(str(path))


def build_bm25_docs(docs: List[Document], path: Path) -> None:
    with path.open("wb") as fh:
        pickle.dump(docs, fh)


def log_summary(label: str, docs: Iterable[Document], out_dir: Path) -> None:
    count = len(list(docs)) if not isinstance(docs, list) else len(docs)
    if count:
        print(f"[ok] {label}: built {count} documents -> {out_dir}")
    else:
        print(f"[warn] {label}: no documents found; indexes not written")


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build FAISS/BM25 indexes for DualSPHysicsGPT retrievers")
    parser.add_argument("--design_dir", default="data/design_corpus", help="Path to design corpus directory")
    parser.add_argument("--error_dir", default="data/error_corpus", help="Path to error corpus directory")
    parser.add_argument("--out_dir", default="rag/indexes", help="Directory to store generated indexes")
    args = parser.parse_args(argv)

    try:
        design_dir = validate_corpus_dir(Path(args.design_dir), "design")
        error_dir = validate_corpus_dir(Path(args.error_dir), "error")
        out_dir = ensure_out_dir(Path(args.out_dir))
    except IndexBuildError as err:
        print(err)
        raise SystemExit(1) from err

    try:
        embeddings = OpenAIEmbeddings(chunk_size=EMBED_BATCH_SIZE)
    except Exception as exc:
        print("[ERROR] Failed to initialise OpenAI embeddings. Ensure OPENAI_API_KEY is set.")
        raise SystemExit(1) from exc

    design_docs = load_corpus(design_dir, "design")
    if design_docs:
        build_faiss(design_docs, embeddings, out_dir / "design_faiss")
        build_bm25_docs(design_docs, out_dir / "design_bm25.pkl")
        log_summary("design", design_docs, out_dir)
    else:
        print("[warn] design: corpus directory contains no supported files; skipping index build")

    error_docs = load_corpus(error_dir, "error")
    if error_docs:
        build_faiss(error_docs, embeddings, out_dir / "error_faiss")
        build_bm25_docs(error_docs, out_dir / "error_bm25.pkl")
        log_summary("error", error_docs, out_dir)
    else:
        print("[warn] error: corpus directory contains no supported files; skipping index build")


if __name__ == "__main__":
    main()

