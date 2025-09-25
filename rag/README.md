# RAG Index Builder

The retrieval indexes used by DualSPHysicsGPT live under `rag/indexes/` and can be refreshed with:

```
python rag/build_indices.py --design_dir data/design_corpus --error_dir data/error_corpus --out_dir rag/indexes
```

The script validates the corpus directories, filters unsupported or empty files, and regenerates FAISS/BM25 artifacts:

- `design_faiss/`, `design_bm25.pkl`
- `error_faiss/`, `error_bm25.pkl`

Set `OPENAI_API_KEY` in your environment (or `.env`) before running to allow the embedding builder to initialise.

# OpenAI Vector Store Management

The RAG system also uses OpenAI's File Search API, which requires ingesting corpora into cloud-based vector stores. Separate stores are used for the design and error corpora.

## Updating Vector Stores

To keep the vector stores synchronized with your local file corpora, you need to run the ingestion scripts located in `scripts/`. These scripts handle creating/reusing vector stores, uploading only new or modified files (based on SHA256 checksums), and updating local configuration.

### Prerequisites
1.  **Set Environment Variables**: Ensure `OPENAI_API_KEY` is set in your `.env` file or system environment.
2.  **Install Dependencies**: Run `pip install -r requirements.txt` to ensure `openai`, `xmltodict`, and other required packages are installed.
3.  **Verify Corpora**: Make sure your `data/design_corpus` and `data/error_corpus` directories are populated.

### 1. Update the Design Corpus Store

The design corpus consists of XML files, which are not directly supported by the OpenAI API. This script sanitizes them, converts them to JSON, and uploads the JSON data.

**Command:**
```sh
python scripts/ingest_design_corpus.py
```

**Process:**
1.  Scans `data/design_corpus` for `.xml` files.
2.  Sanitizes and converts each XML file to a temporary JSON file.
3.  Uploads new/modified files to the `DualSPHysics-Design` vector store.
4.  Updates `rag/vector_stores.json` and `.env` (`OPENAI_RAG_VS_DESIGN_ID`) with the store ID.

### 2. Update the Error Corpus Store

The error corpus ingestion is more direct and populates the `DualSPHysics-Error` vector store.

**Command:**
```sh
python scripts/ingest_error.py
```

**Process:**
1.  Scans `data/error_corpus` for supported files (e.g., `.txt`, `.md`).
2.  Uploads new/modified files.
3.  Updates `rag/vector_stores.json` and `.env` (`OPENAI_RAG_VS_ERROR_ID`) with the store ID.
You can use arguments like `--root <path>` or `--name <store_name>` to customize its behavior.
