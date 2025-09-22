# RAG Index Builder

The retrieval indexes used by DualSPHysicsGPT live under `rag/indexes/` and can be refreshed with:

```
python rag/build_indices.py --design_dir data/design_corpus --error_dir data/error_corpus --out_dir rag/indexes
```

The script validates the corpus directories, filters unsupported or empty files, and regenerates FAISS/BM25 artifacts:

- `design_faiss/`, `design_bm25.pkl`
- `error_faiss/`, `error_bm25.pkl`

Set `OPENAI_API_KEY` in your environment (or `.env`) before running to allow the embedding builder to initialise.
