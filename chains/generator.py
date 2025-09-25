import os
from typing import Optional, Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.documents import Document
from rag.retrievers import design_retriever
from chains.rag_utils import (
    use_openai_file_search,
    build_metadata_filter,
    persist_sources,
    get_last_run_info,
)
from llm.client import llm_call, get_model_name, get_reasoning_config

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "GPT-5-THINKING")

def _rag_flag_from_env() -> bool:
    return os.environ.get("USE_RAG", "0") == "1"


_USE_RAG = _rag_flag_from_env()


def _should_use_file_search() -> bool:
    """Return True when OpenAI File Search backend should handle retrieval."""
    return is_rag_enabled() and use_openai_file_search()


def is_rag_enabled() -> bool:
    """Return the cached RAG toggle flag."""
    return _USE_RAG


def reload_use_rag() -> bool:
    """Refresh the cached RAG toggle from the current environment."""
    global _USE_RAG
    _USE_RAG = _rag_flag_from_env()
    return _USE_RAG


PROMPT_PATH = os.environ.get("GENERATOR_PROMPT_PATH", "prompts/generator_system_prompt.md")  # optional custom instructions


def _read(path: str) -> str:
    return open(path, "r", encoding="utf-8", errors="ignore").read() if os.path.exists(path) else ""


def extract_xml(text: str) -> Optional[str]:
    import re

    match = re.search(r"<case[\s\S]*?</case>", text, re.IGNORECASE)
    return match.group(0) if match else None


def sanitize_newvarcte(xml: str) -> str:
    """
    Post-sanitizer: convert any <newvarcte name="X" value="Y" .../> into
    attribute-style <newvarcte ... X="Y" .../>. Idempotent for already-correct tags.
    Supports both single and double quotes for safety. Preserves other attributes and
    whether the tag is self-closing.
    """
    import re

    pattern = re.compile(r'<newvarcte\b([^>]*)>', flags=re.IGNORECASE)

    def repl(m: re.Match) -> str:
        attrs = m.group(1) or ""
        # Keep whether the tag was self-closing ("/>")
        selfclosing = attrs.rstrip().endswith("/")
        attrs_core = attrs.rstrip().rstrip("/")
        # Find name="..." and value="..." (support single/double quotes)
        name_m = re.search(r'\bname\s*=\s*([\'"])([^\'"]+)\1', attrs_core, flags=re.IGNORECASE)
        value_m = re.search(r'\bvalue\s*=\s*([\'"])([^\'"]+)\1', attrs_core, flags=re.IGNORECASE)
        if not (name_m and value_m):
            end = "/>" if selfclosing else ">"
            attrs_core_stripped = attrs_core.strip()
            attrs_str = (" " + attrs_core_stripped) if attrs_core_stripped else ""
            return f'<newvarcte{attrs_str}{end}'
        var_name = name_m.group(2)
        var_value = value_m.group(2)
        # Remove the name/value attributes from the attribute list
        attrs_core2 = re.sub(r'\s*\bname\s*=\s*([\'"])[^\'"]+\1', "", attrs_core, flags=re.IGNORECASE)
        attrs_core2 = re.sub(r'\s*\bvalue\s*=\s*([\'"])[^\'"]+\1', "", attrs_core2, flags=re.IGNORECASE)
        attrs_core2 = attrs_core2.strip()
        # Rebuild
        rebuilt = ""
        if attrs_core2:
            rebuilt = " " + attrs_core2
        rebuilt += f' {var_name}="{var_value}"'
        end = "/>" if selfclosing else ">"
        return f"<newvarcte{rebuilt}{end}"

    return pattern.sub(repl, xml or "")


def _assemble_context(docs) -> str:
    parts = []
    for doc in docs:
        parts.append(f"[{doc.metadata.get('source', '')}] {doc.page_content}")
    return "\n\n".join(parts)


def _to_openai_messages(msgs: List) -> List[Dict[str, str]]:
    """Convert LangChain BaseMessage -> OpenAI/JSON payload."""
    out: List[Dict[str, str]] = []
    for msg in msgs:
        if isinstance(msg, SystemMessage):
            role = "system"
        elif isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        else:
            role = getattr(msg, "role", "user")
        out.append({"role": role, "content": msg.content})
    return out




def _maybe_load_tokenizer(model: str):
    try:
        import tiktoken  # type: ignore
    except ImportError:
        return None
    encoder = None
    if model:
        try:
            encoder = tiktoken.encoding_for_model(model)
        except Exception:
            encoder = None
    if encoder is None:
        try:
            encoder = tiktoken.get_encoding('cl100k_base')
        except Exception:
            return None
    return encoder


def _count_chars_tokens(text: str, encoder):
    content = text or ''
    chars = len(content)
    tokens = None
    if encoder:
        try:
            tokens = len(encoder.encode(content))
        except Exception:
            tokens = None
    return chars, tokens


def _log_prompt_metrics(lc_messages: List, docs: List, ctx: str, model: str) -> None:
    if os.environ.get("DSPH_DEBUG") != "1":
        return
    print("\n=== generator: prompt_metrics ===")
    encoder = _maybe_load_tokenizer(model)
    total_chars = 0
    total_tokens = 0
    tokens_available = encoder is not None
    for idx, msg in enumerate(lc_messages):
        content = getattr(msg, "content", "") or ""
        chars, tokens = _count_chars_tokens(content, encoder)
        total_chars += chars
        role = msg.__class__.__name__
        token_str = ""
        if tokens is not None:
            total_tokens += tokens
            token_str = f", tokens={tokens}"
        else:
            tokens_available = False
        print(f"[{idx}] {role}: chars={chars}{token_str}")
    total_line = f"total_chars={total_chars}"
    if tokens_available:
        total_line += f", total_tokens={total_tokens}"
    print(total_line)
    rag_docs = list(docs or [])
    print(f"rag_docs={len(rag_docs)}")
    if rag_docs:
        rag_total_chars = 0
        rag_total_tokens = 0
        rag_tokens_available = encoder is not None
        for idx, doc in enumerate(rag_docs):
            content = getattr(doc, "page_content", "") or ""
            chars, tokens = _count_chars_tokens(content, encoder)
            rag_total_chars += chars
            if tokens is not None:
                rag_total_tokens += tokens
            else:
                rag_tokens_available = False
            metadata = getattr(doc, "metadata", {}) or {}
            source = ""
            if isinstance(metadata, dict):
                source = str(metadata.get("source", ""))
            token_str = f", tokens={tokens}" if tokens is not None else ""
            print(f"  doc[{idx}]: chars={chars}, source={source}{token_str}")
        summary = f"rag_total_chars={rag_total_chars}"
        if rag_tokens_available:
            summary += f", rag_total_tokens={rag_total_tokens}"
        print(summary)
    ctx_chars, ctx_tokens = _count_chars_tokens(ctx or "", encoder)
    ctx_line = f"ctx_chars={ctx_chars}"
    if ctx_tokens is not None:
        ctx_line += f", ctx_tokens={ctx_tokens}"
    print(ctx_line)
    print("=== generator: prompt_metrics end ===\n")

def generator_chain(user_query: str, *, freeze_retrieval: bool = False, frozen_docs: Optional[List[Document]] = None) -> Dict[str, Any]:
    sys_prompt = _read(PROMPT_PATH)

    design_vs_id = os.environ.get("OPENAI_RAG_VS_DESIGN_ID")
    use_file_search = bool(design_vs_id) and _should_use_file_search()
    if freeze_retrieval:
        use_file_search = False
    if _should_use_file_search() and not design_vs_id and os.environ.get('DSPH_DEBUG') == '1':
        print('generator: OPENAI_RAG_VS_DESIGN_ID missing; using legacy retriever')

    docs: List = []
    ctx = ""
    filters: Dict[str, str] = {}
    if freeze_retrieval:
        if frozen_docs:
            docs = list(frozen_docs)
            ctx = _assemble_context(docs)
    elif use_file_search:
        filters = build_metadata_filter(user_query)
    elif is_rag_enabled():
        retr = design_retriever()
        if retr:
            query_for_rag = user_query
            # If the prompt is very long (like a fix prompt), just use the first few lines for retrieval
            if len(query_for_rag) > 1000:
                query_for_rag = query_for_rag[:1000]
            docs = retr.get_relevant_documents(query_for_rag)
            ctx = _assemble_context(docs)

    # Heuristic to check if this is a detailed prompt from the controller loop
    is_detailed_prompt = "(Fix iteration" in user_query or "(User rejection)" in user_query

    human_content = ""
    freeze_prefix = "FreezeRetrieval=true\n" if freeze_retrieval else ""
    if is_detailed_prompt:
        # For detailed prompts, append the references directly
        human_content = f"{freeze_prefix}{user_query}\n[References]\n{ctx}\n"
    else:
        # For simple queries, use the standard template
        human_content = (
            f"{freeze_prefix}"
            "[Task] Based on the user's requirements and available references, generate a complete DualSPHysics Case_Def.xml.\n"
            "[Constraints] Output exactly one <case>...</case> XML block with no commentary, YAML, or code fences.\n"
            f"[User Requirements]\n{user_query}\n"
            f"[References]\n{ctx}\n"
        )

    lc_messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=human_content),
    ]
    messages = _to_openai_messages(lc_messages)
    model = get_model_name()
    reasoning = get_reasoning_config()
    debug_enabled = os.environ.get('DSPH_DEBUG') == '1'
    if debug_enabled:
        _log_prompt_metrics(lc_messages, docs, ctx, model)

    llm_kwargs = {}
    if use_file_search and design_vs_id:
        llm_kwargs['file_search_vs_ids'] = [design_vs_id]
        if filters:
            llm_kwargs['metadata_filter'] = filters
        if debug_enabled:
            print(f"generator: file_search filters={filters} vs_ids={[design_vs_id]}")

    out = llm_call(messages, model=model, reasoning=reasoning, **llm_kwargs)
    if use_file_search:
        run_info = get_last_run_info()
        if run_info:
            fs_sources = run_info.get("sources", [])
            # Convert the raw dict sources into Document-like objects for consistency.
            # Prefer 'text' (snippet) then 'content'. Use filename as source when available.
            docs = [
                Document(
                    page_content=s.get("text", s.get("content", "")),
                    metadata={"source": (s.get("filename") or s.get("file_id") or "unknown")},
                )
                for s in fs_sources
            ]
        persist_sources('generator')
        if debug_enabled:
            print("\n=== generator: post_file_search_metrics ===")
            _log_prompt_metrics(lc_messages, docs, ctx, model)
    xml = extract_xml(out) or out  # fallback when the model emits plain XML

    if debug_enabled:
        print("\n=== generator: lc_messages ===")
        for msg in lc_messages:
            role = msg.__class__.__name__
            print(f"[{role}]\n{msg.content}\n")

        print("=== generator: raw_out ===")
        print(out)

        print("=== generator: extracted_xml ===")
        print(xml)
        print("=== generator: end ===\n")

    # Post-sanitize to ensure attribute-style variables in <predefinition>/<newvarcte>
    xml = sanitize_newvarcte(xml)
    return {"xml": xml, "sources": docs}
