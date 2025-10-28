import os
from dotenv import load_dotenv
from rag.openai_file_search import response_with_file_search, get_last_run_info


def main() -> None:
    load_dotenv()
    vector_store_id = os.environ.get("OPENAI_RAG_VS_DESIGN_ID")
    if not vector_store_id:
        raise SystemExit("OPENAI_RAG_VS_DESIGN_ID is not set")

    model = os.environ.get("OPENAI_MODEL", "gpt-5")

    try:
        response_with_file_search(
            messages=[
                {"role": "system", "content": "test"},
                {"role": "user", "content": "generate 2D dambreak xml file"},
            ],
            model=model,
            vector_store_ids=[vector_store_id],
            max_output_tokens=64,
            query_rewrite=True,
            raw_query="generate 2D dambreak xml file",
        )
    except Exception as exc:
        print(f"response_with_file_search raised: {exc}")

    info = get_last_run_info()
    sources = info.get("sources", []) if info else []
    print(f"Sources returned: {len(sources)}")
    for idx, src in enumerate(sources, 1):
        meta = src.get("metadata") or src.get("attributes") or {}
        if not isinstance(meta, dict):
            meta = {}
        filename = src.get("filename") or meta.get("source_path") or meta.get("filename") or src.get("file_id")
        score = src.get("score")
        line = f"{idx}. {filename or 'unknown'}"
        if score is not None:
            line += f" (score={score})"
        print(line)
        snippets = src.get("snippets")
        if isinstance(snippets, list) and snippets:
            snippet_clean = " ".join(str(snippets[0]).split())
            if len(snippet_clean) > 120:
                snippet_clean = snippet_clean[:117] + "..."
            print(f"   snippet: {snippet_clean}")
        source_path = meta.get("source_path")
        if source_path:
            print(f"   source_path: {source_path}")


if __name__ == "__main__":
    main()
