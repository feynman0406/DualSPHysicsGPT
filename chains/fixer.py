import os

from rag.retrievers import error_retriever
from chains.rag_utils import use_openai_file_search, build_metadata_filter, persist_sources
from llm.client import llm_call, get_model_name, get_reasoning_config

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "GPT-5-THINKING")

def _rag_flag_from_env() -> bool:
    return os.environ.get("USE_RAG", "0") == "1"


_USE_RAG = _rag_flag_from_env()


def _should_use_file_search() -> bool:
    return is_rag_enabled() and use_openai_file_search()


def is_rag_enabled() -> bool:
    """Return the cached RAG toggle flag."""
    return _USE_RAG


def reload_use_rag() -> bool:
    """Refresh the cached RAG toggle from the current environment."""
    global _USE_RAG
    _USE_RAG = _rag_flag_from_env()
    return _USE_RAG

PROMPT_PATH = os.environ.get("FIXER_PROMPT_PATH", "prompts/fixer_system_prompt.md")  # optional custom instructions

def _read(path:str) -> str:
    return open(path, "r", encoding="utf-8", errors="ignore").read() if os.path.exists(path) else ""

def _assemble_context(docs) -> str:
    parts = []
    for d in docs:
        parts.append(f"[{d.metadata.get('source','')}] {d.page_content}")
    return "\n\n".join(parts)

def fixer_chain(prev_xml: str, error_msg: str, prompt_template: str | None = None) -> str:
    """Produce a textual fix suggestion instead of a replacement XML."""
    sys_prompt = _read(PROMPT_PATH)

    design_vs_id = os.environ.get("OPENAI_RAG_VS_DESIGN_ID")
    error_vs_id = os.environ.get("OPENAI_RAG_VS_ERROR_ID")
    vs_ids = [vid for vid in (design_vs_id, error_vs_id) if vid]
    use_file_search = bool(vs_ids) and _should_use_file_search()
    if _should_use_file_search() and not vs_ids and os.environ.get('DSPH_DEBUG') == '1':
        print('fixer: vector store ids missing; using legacy retriever')

    ctx = ""
    filters = {}
    if use_file_search:
        combined_text = f"{prev_xml}\n{error_msg}"
        filters = build_metadata_filter(combined_text)
    elif is_rag_enabled():
        retr = error_retriever()
        if retr:
            query = (error_msg or "")[:2000]
            docs = retr.get_relevant_documents(query)
            ctx = _assemble_context(docs)

    diagnostics = error_msg or ""

    if prompt_template:
        # Template is provided for user rejection flow
        user_content = prompt_template.format(user_feedback=diagnostics, last_xml=prev_xml, ctx=ctx)
    else:
        # Default flow for automated error fixing
        user_content = (
            "[Task] Review the previous DualSPHysics XML and the diagnostics, then craft a clear fix plan for the generator so it can produce an improved XML in the next iteration.\n"
            "[Output] Explain the root cause, list concrete changes, and provide actionable editing instructions. Do NOT output any XML.\n"
            f"[Previous XML]\n{prev_xml}\n"
            f"[Diagnostics]\n{diagnostics}\n"
            f"[Reference Materials]\n{ctx}\n"
        )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_content},
    ]
    model = get_model_name()
    reasoning = get_reasoning_config()

    llm_kwargs = {}
    if use_file_search and vs_ids:
        llm_kwargs['file_search_vs_ids'] = vs_ids
        if filters:
            llm_kwargs['metadata_filter'] = filters
        if os.environ.get('DSPH_DEBUG') == '1':
            print(f"fixer: file_search filters={filters} vs_ids={vs_ids}")

    out = llm_call(messages, model=model, reasoning=reasoning, **llm_kwargs)
    if use_file_search:
        persist_sources('fixer')
    return out.strip()
