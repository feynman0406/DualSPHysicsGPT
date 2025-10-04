# DualSPHysicsGPT

A small agentic workflow for generating and iterating DualSPHysics Case_Def.xml using an LLM, with optional Retrieval Augmented Generation (RAG) for better context.

## Quick Start

1) Install Python dependencies (recommend a fresh virtual environment):

```
pip install -r requirements.txt
```

2) Create a `.env` file (copy and edit as needed):

```
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o                      # legacy chat fallback
OPENAI_MODEL_RESPONSES=gpt-4.1           # OpenAI Responses + File Search default
OPENAI_API_KEY=sk-...                    # your key

# RAG toggles
USE_RAG=1
USE_OPENAI_FILE_SEARCH=1
OPENAI_RAG_VS_DESIGN_ID=vs-...           # filled by scripts/ingest_design.py
OPENAI_RAG_VS_ERROR_ID=vs-...            # filled by scripts/ingest_error.py

# Legacy local indexes (only when USE_OPENAI_FILE_SEARCH=0)
IDX_DIR=rag/indexes
TOP_K=8
EMBEDDING_PROVIDER=openai

# Execution
DSPH_WORKDIR=.
```

3) Build retrieval indexes (optional but recommended when `USE_RAG=1`):

```
python rag/build_indices.py --design_dir data/design_corpus --error_dir data/error_corpus --out_dir rag/indexes
```

- The builder scans supported text-like files: `.md`, `.txt`, `.xml`, `.log`, `.yaml`, `.yml`.
- Outputs are written to `rag/indexes/`: `design_faiss/`, `design_bm25.pkl`, `error_faiss/`, `error_bm25.pkl`.
- Re-run the same command any time you add/remove corpus files to refresh the indexes.

4) Run from the CLI:

```
python -m cli.dsph run "2D dambreak case"
```

- Prints a session id, status, and artifacts directory.
- Review/accept with:

```
python -m cli.dsph review <session_id> accept
```

Show session artifacts:

```
python -m cli.dsph show <session_id>
```

Validate your binary setup (paths, GPU availability):

```
python -m cli.dsph check --bin path/to/bin/windows
```

## RAG via OpenAI File Search

- **Ingest Design Corpus**: Run `python scripts/ingest_design_corpus.py`. This script is the official tool for processing and uploading the design corpus. It performs several critical steps:
  1.  It automatically converts the `.xml` design files to `.json` format in memory. This is necessary because the OpenAI File Search API does not support `.xml` files directly.
  2.  It sanitizes the XML content during conversion to fix common formatting errors, ensuring all valid cases can be processed.
  3.  It uploads the resulting JSON data to the `DualSPHysics-Design` vector store.
  4.  It updates the `.env` and `rag/vector_stores.json` files with the correct vector store ID.
- **Ingest Error Corpus**: Run `python scripts/ingest_error.py` to upload error log data.
- **Env vars**: confirm `OPENAI_API_KEY`, `OPENAI_MODEL_RESPONSES`, `USE_RAG=1`, `USE_OPENAI_FILE_SEARCH=1`, `OPENAI_RAG_VS_DESIGN_ID`, and `OPENAI_RAG_VS_ERROR_ID`; the ingest scripts fill the two IDs.
- **Run agents**: keep `USE_RAG=1` so `chains/generator.py` hits the design store and `chains/fixer.py` uses both design + error stores, e.g. `python -m cli.dsph run "2D dambreak case"`.
- **Audit sources**: every File Search call writes `logs/last_run/metadata.json`, `logs/last_run/response.txt`, and `logs/last_run/<agent>_sources.json` for traceability.
- **Evaluate**: `python scripts/eval_rag.py --threshold 0.8` reports Recall@5 for a small dev set and fails CI if recall dips below the target.
- **Legacy fallback**: set `USE_OPENAI_FILE_SEARCH=0` to reuse the FAISS/BM25 indexes; rebuild them with `python rag/build_indices.py --design_dir ... --error_dir ...` when corpora change.

## RAG Controls

You can configure retrieval behaviour via .env or CLI flags (flags override .env):

- `USE_RAG=1` enables retrieval for generator/fixer chains.
- `USE_OPENAI_FILE_SEARCH=1` routes calls through OpenAI Vector Stores; set to `0` to fall back to the legacy FAISS/BM25 indexes.
- `OPENAI_RAG_VS_DESIGN_ID` / `OPENAI_RAG_VS_ERROR_ID` identify the design/error vector stores (filled by the ingest scripts).
- `IDX_DIR` and `TOP_K` only apply when `USE_OPENAI_FILE_SEARCH=0`.
- `EMBEDDING_PROVIDER` selects the embeddings backend for the legacy indexes.

CLI overrides (may be combined with other flags):

```
python -m cli.dsph run \
  --rag-index-dir rag/indexes \
  --rag-top-k 8 \
  --rag-provider openai \
  "2D dambreak case"
```

Internally, the generator targets the design vector store (or FAISS index) while the fixer uses both the design and error stores/indexes. Retrieved text is injected deterministically into the prompt under a References section.

## Updating the Corpus

- Add or edit files under `data/design_corpus` (reference designs) and `data/error_corpus` (error diagnostics + fix snippets).
- Re-ingest the design corpus: `python scripts/ingest_design_corpus.py`.
- Re-ingest the error corpus: `python scripts/ingest_error.py`.
- Legacy indexes (only when `USE_OPENAI_FILE_SEARCH=0`): `python rag/build_indices.py --design_dir data/design_corpus --error_dir data/error_corpus --out_dir rag/indexes`.

## Troubleshooting

- "Failed to initialise OpenAI embeddings": ensure `OPENAI_API_KEY` is set (via shell env or `.env`).
- "No retrievers available": indexes are missing. Build them or set `USE_RAG=0`.
- Windows encoding: all corpus files are read as UTF-8 with errors ignored; prefer UTF-8 to avoid weird characters.
- Long files: if recall degrades for very long documents, consider chunking in a future iteration.

## Notes

- The solver always runs DualSPHysics binaries; ensure `DSPH_BIN_DIR` points to a valid installation.
- Session artifacts are written to `sessions/<session_id>/` to make runs reviewable and reproducible.
