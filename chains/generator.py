import json
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    from langchain_core.documents import Document
except ImportError:  # pragma: no cover - lightweight stubs for test environments
    class _BaseMessage:
        def __init__(self, content: str):
            self.content = content

    class SystemMessage(_BaseMessage):
        pass

    class HumanMessage(_BaseMessage):
        pass

    class AIMessage(_BaseMessage):
        pass

    class Document(dict):
        """Minimal Document stub replicating .page_content/.metadata attributes."""

        def __init__(self, page_content: str = "", metadata: Optional[Dict[str, Any]] = None):
            super().__init__()
            self.page_content = page_content
            self.metadata = metadata or {}
from AutoXml_script.generate_xml import generate_case_xml, validate_case_tree
from chains.json_normalizer import normalize_case_config, NormalizationResult
from chains.mdbc_normals import enforce_mdbc_normals
from external_stl import get_external_stl_context
try:
    from rag.retrievers import design_retriever
except Exception:  # pragma: no cover - optional dependency for tests
    def design_retriever():
        return None

try:
    from chains.rag_utils import (
        use_openai_file_search,
        build_metadata_filter,
        persist_sources,
        get_last_run_info,
    )
except Exception:  # pragma: no cover - optional dependency for tests
    def use_openai_file_search() -> bool:  # type: ignore[override]
        return False

    def build_metadata_filter(*_args, **_kwargs) -> Dict[str, Any]:  # type: ignore[override]
        return {}

    def persist_sources(*_args, **_kwargs) -> None:  # type: ignore[override]
        return None

    def get_last_run_info() -> Optional[Dict[str, Any]]:  # type: ignore[override]
        return None

from llm.client import llm_call, get_model_name, get_reasoning_config, get_openai_client

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "GPT-5-THINKING")

# Two-stage RAG + Planning Agent flags
def _use_two_stage_rag() -> bool:
    """Check if two-stage RAG with Planning Agent is enabled."""
    return (
        os.environ.get("USE_TWO_STAGE_RAG_SCHEMA", "0") == "1" and
        os.environ.get("USE_RAG_PLANNING_AGENT", "0") == "1"
    )

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

# Schema loading and caching
_SCHEMA_CACHE: Optional[Dict[str, Any]] = None
SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "dualsphysics_config_schema.json"


def _load_json_schema() -> Dict[str, Any]:
    """Load and cache the GOS JSON schema."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        _SCHEMA_CACHE = json.load(f)
    
    return _SCHEMA_CACHE


def _read(path: str) -> str:
    return open(path, "r", encoding="utf-8", errors="ignore").read() if os.path.exists(path) else ""


def extract_xml(text: str) -> Optional[str]:
    match = re.search(r"<case[\s\S]*?</case>", text, re.IGNORECASE)
    return match.group(0) if match else None


def _extract_json_snippet(text: str) -> Optional[str]:
    """Best-effort extraction of the first JSON object embedded in text."""
    text = text.strip()
    if not text:
        return None
    # Attempt direct load first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Look for fenced code block
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if fence_match:
        candidate = fence_match.group(1)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Fallback: grab substring between first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            return None
    return None


def _parse_generator_config(output_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Return (config, structured_meta) if JSON payload is found."""
    snippet = _extract_json_snippet(output_text)
    if not snippet:
        return None, None
    try:
        parsed = json.loads(snippet)
    except json.JSONDecodeError:
        return None, None

    if isinstance(parsed, dict) and "config" in parsed and isinstance(parsed["config"], dict):
        meta = dict(parsed)
        config = meta.pop("config")
        return config, meta

    if isinstance(parsed, dict):
        return parsed, None

    return None, None


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


def _format_external_stl_note(ctx: Dict[str, str]) -> str:
    filename = (
        ctx.get("stored_filename")
        or ctx.get("original_filename")
        or ctx.get("stored_relative_path")
        or ctx.get("stored_path")
        or ctx.get("source_path")
        or "external_geometry.stl"
    )
    stored_rel = ctx.get("stored_relative_path") or ctx.get("stored_path")
    source_path = ctx.get("source_path")
    details: List[str] = []
    if filename:
        details.append(
            f"External STL provided: replace any placeholder STL references with {filename} while keeping other content unchanged."
        )
    if stored_rel:
        details.append(f"Stored location: {stored_rel}")
    elif source_path:
        details.append(f"Original upload: {source_path}")
    if not details:
        details.append(
            "External STL provided: replace any placeholder STL references with the uploaded filename."
        )
    return "\n".join(details)



def _validate_xml_or_raise(xml: str) -> None:
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"Fallback XML is not well-formed: {exc}") from exc

    errors = list(validate_case_tree(root))

    # Additional guard: when Boundary=2 (mDBC) is requested the XML must include normals.
    boundary = None
    for param in root.findall('.//parameter'):
        key = (param.get('key') or '').strip().lower()
        if key == 'boundary':
            boundary = (param.get('value') or (param.text or '')).strip().lower()
            break
    if boundary in {'2', 'mdbc'}:
        has_normals = root.find('.//normals') is not None
        if not has_normals:
            errors.append('Boundary=2 requires a <normals> section')

    if errors:
        raise ValueError("Fallback XML failed validation: " + '; '.join(errors))

def _assemble_context(docs) -> str:
    parts = []
    for doc in docs:
        parts.append(f"[{doc.metadata.get('source', '')}] {doc.page_content}")
    return "\n\n".join(parts)


def _source_to_document(source: Dict[str, Any]) -> Document:
    """Convert a retrieval source entry into a LangChain Document with snippets."""
    metadata_field = source.get("metadata")
    metadata: Dict[str, Any] = dict(metadata_field) if isinstance(metadata_field, dict) else {}
    legacy_attrs = source.get("attributes")
    if isinstance(legacy_attrs, dict):
        for key, value in legacy_attrs.items():
            metadata.setdefault(key, value)
    file_id = source.get("file_id")
    if file_id and "file_id" not in metadata:
        metadata["file_id"] = file_id
    filename = source.get("filename")
    if filename and "filename" not in metadata:
        metadata["filename"] = filename
    score = source.get("score")
    if score is not None and "score" not in metadata:
        metadata["score"] = score
    vector_store_id = source.get("vector_store_id")
    if vector_store_id and "vector_store_id" not in metadata:
        metadata["vector_store_id"] = vector_store_id
    snippets = source.get("snippets")
    snippet_text = ""
    if isinstance(snippets, list) and snippets:
        cleaned = [str(snippet).strip() for snippet in snippets if isinstance(snippet, str)]
        snippet_text = "\n\n".join(cleaned)
        metadata.setdefault("snippets", cleaned)
    fallback_text = source.get("text") or source.get("content") or ""
    page_content = snippet_text or fallback_text
    existing_source = metadata.get("source")
    label = existing_source or metadata.get("source_path") or metadata.get("filename") or filename or file_id or "unknown"
    metadata["source"] = label
    return Document(page_content=page_content, metadata=metadata)


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


def _two_stage_workflow(user_query: str) -> Dict[str, Any]:
    """
    Execute two-stage RAG + Planning Agent workflow.
    
    Stage 1: Planning Agent - retrieves, scores, and curates examples
    Stage 2: Schema Agent - generates config JSON with strict schema
    
    Args:
        user_query: User's query
        
    Returns:
        Dict with xml, config, sources, and metadata
    """
    debug_enabled = os.environ.get('DSPH_DEBUG') == '1'
    if debug_enabled:
        print("\n=== Two-Stage Workflow: START ===")
    
    # Import agents
    try:
        from agents.planning_agent import run_planning_agent
        from agents.schema_agent import run_schema_agent
        from rag.openai_file_search import response_with_file_search
    except ImportError as e:
        raise RuntimeError(f"Failed to import two-stage workflow components: {e}")
    
    # Get vector store ID
    design_vs_id = os.environ.get("OPENAI_RAG_VS_DESIGN_ID")
    if not design_vs_id:
        raise RuntimeError("OPENAI_RAG_VS_DESIGN_ID required for two-stage workflow")
    
    # Build metadata filter
    metadata_filter = build_metadata_filter(user_query)
    
    if debug_enabled:
        print(f"Metadata filter: {metadata_filter}")
    
    # Stage 0: File search retrieval (required before Planning Agent)
    model = get_model_name()
    external_stl_ctx = get_external_stl_context()
    external_stl_block = _format_external_stl_note(external_stl_ctx) if external_stl_ctx else ""
    base_query = user_query.rstrip("\r\n")
    agent_query = base_query if base_query else user_query
    if external_stl_block:
        agent_query = f"{base_query}\n{external_stl_block}" if base_query else external_stl_block
    messages = [
        {"role": "system", "content": "You are a DualSPHysics configuration expert."},
        {"role": "user", "content": f"Find relevant examples for this request:\n{agent_query}"}
    ]
    try:
        _ = response_with_file_search(
            messages=messages,
            model=model,
            vector_store_ids=[design_vs_id],
            metadata_filter=metadata_filter,
            max_output_tokens=14000,
            query_rewrite=True,
            temperature=0.0,
        )
    except Exception as exc:
        if debug_enabled:
            print(f"File search failed: {exc}")
        raise

    if debug_enabled:
        print("=== Stage 1: Planning Agent ===")

    # Stage 1: Planning Agent
    try:
        plan_json = run_planning_agent(
            user_query=agent_query,
            vector_store_ids=[design_vs_id],
            metadata_filter=metadata_filter,
            retry_context=None,
        )
    except Exception as exc:
        if debug_enabled:
            print(f"Planning Agent failed: {exc}")
        raise RuntimeError(f"Planning Agent failed: {exc}") from exc

    if debug_enabled:
        print(f"Plan JSON generated: {len(plan_json.get('curated_examples', []))} examples")

    # Stage 2: Schema Agent
    if debug_enabled:
        print("=== Stage 2: Schema Agent ===")

    try:
        schema = _load_json_schema()
        llm_client = get_openai_client()

        config_json = run_schema_agent(
            plan_json=plan_json,
            user_query=agent_query,
            schema=schema,
            llm_client=llm_client,
            model=model,
            temperature=0.0,
        )
    except Exception as exc:
        if debug_enabled:
            print(f"Schema Agent failed: {exc}")
        raise RuntimeError(f"Schema Agent failed: {exc}") from exc

    if debug_enabled:
        print("Config JSON generated successfully")

    
    # Normalize, enforce mDBC normals, and generate XML
    try:
        normalization = normalize_case_config(config_json)
        config_normalized = enforce_mdbc_normals(normalization.config)
        xml = generate_case_xml(config_normalized)
        config_json = config_normalized
    except Exception as exc:
        raise RuntimeError(f"Failed to generate XML from config: {exc}") from exc
    
    # Post-sanitize
    xml = sanitize_newvarcte(xml)
    
    # Build sources from Plan JSON citations
    docs = []
    for citation in plan_json.get("citations", []):
        docs.append(Document(
            page_content=citation.get("quote", ""),
            metadata={"source": citation.get("filename", "unknown")},
        ))
    
    # Persist sources
    persist_sources('generator')
    
    if debug_enabled:
        print("=== Two-Stage Workflow: COMPLETE ===\n")
    
    result: Dict[str, Any] = {
        "xml": xml,
        "config": config_json,
        "sources": docs,
        "structured_meta": {
            "workflow": "two_stage_rag_planning",
            "plan_completion_rate": plan_json.get("_metadata", {}).get("plan_completion_rate", 0.0),
            "curated_examples_count": len(plan_json.get("curated_examples", [])),
        },
    }
    
    if normalization.warnings:
        result["warnings"] = normalization.warnings
    
    return result


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
    # Check if two-stage RAG + Planning Agent workflow is enabled
    if _use_two_stage_rag() and not freeze_retrieval:
        try:
            return _two_stage_workflow(user_query)
        except Exception as exc:
            debug_enabled = os.environ.get('DSPH_DEBUG') == '1'
            if debug_enabled:
                print(f"Two-stage workflow failed: {exc}, falling back to single-stage")
            # Fall through to single-stage workflow
    
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

    external_stl_ctx = get_external_stl_context()
    external_stl_block = _format_external_stl_note(external_stl_ctx) if external_stl_ctx else ""
    user_requirements_text = user_query.rstrip("\r\n")
    if external_stl_block:
        if user_requirements_text:
            user_requirements_text = f"{user_requirements_text}\n{external_stl_block}"
        else:
            user_requirements_text = external_stl_block

    # Heuristic to check if this is a detailed prompt from the controller loop
    is_detailed_prompt = "(Fix iteration" in user_query or "(User rejection)" in user_query

    human_content = ""
    freeze_prefix = "FreezeRetrieval=true\n" if freeze_retrieval else ""
    if is_detailed_prompt:
        # For detailed prompts, append the references directly
        detailed_body = user_requirements_text + ("\n" if user_requirements_text else "")
        human_content = f"{freeze_prefix}{detailed_body}[References]\n{ctx}\n"

    else:
        # For simple queries, use the standard template
        human_content = (
            f"{freeze_prefix}"
            "[Task] Based on the user's requirements and available references, generate a complete DualSPHysics Case_Def.xml.\n"
            "[Constraints] Output exactly one <case>...</case> XML block with no commentary, YAML, or code fences.\n"
            f"[User Requirements]\n{user_requirements_text}\n"
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
    
    # Add JSON schema enforcement if enabled
    use_schema = os.environ.get("DSPH_USE_JSON_SCHEMA", "0") == "1"
    strict_mode = os.environ.get("DSPH_STRICT_JSON_SCHEMA", "0") == "1"
    forbid_xml_fallback = os.environ.get("DSPH_FORBID_XML_FALLBACK", "0") == "1"
    
    if use_schema:
        try:
            schema = _load_json_schema()
            llm_kwargs['json_schema'] = schema
            llm_kwargs['strict'] = strict_mode
            if debug_enabled:
                print(f"generator: using JSON schema with strict={strict_mode}")
        except Exception as e:
            if strict_mode:
                raise RuntimeError(f"Failed to load JSON schema in strict mode: {e}") from e
            elif debug_enabled:
                print(f"generator: schema loading failed (non-strict): {e}")

    out = llm_call(messages, model=model, reasoning=reasoning, **llm_kwargs)
    if use_file_search:
        run_info = get_last_run_info()
        if run_info:
            fs_sources = run_info.get("sources", [])
            docs = [_source_to_document(s) for s in fs_sources]
        persist_sources('generator')
        if debug_enabled:
            print("\n=== generator: post_file_search_metrics ===")
            _log_prompt_metrics(lc_messages, docs, ctx, model)
    config_payload, structured_meta = _parse_generator_config(out)
    xml: Optional[str] = None
    if config_payload is not None:
        normalization: Optional[NormalizationResult] = None
        try:
            normalization = normalize_case_config(config_payload)
            config_normalized = enforce_mdbc_normals(normalization.config)
            xml = generate_case_xml(config_normalized)
        except Exception as exc:
            raise ValueError(f"Generator JSON contract violated: {exc}") from exc
        else:
            config_payload = config_normalized
            if structured_meta is None:
                structured_meta = {}
            if normalization.warnings:
                structured_meta.setdefault("normalization_warnings", normalization.warnings)

    # Handle XML fallback based on mode
    if xml is None:
        if forbid_xml_fallback or (use_schema and strict_mode):
            error_msg = "Generator did not produce valid JSON config"
            if config_payload is None:
                error_msg += " (no JSON payload found in output)"
            else:
                error_msg += " (JSON found but XML generation failed)"
            raise ValueError(error_msg)
        # Fallback to extracting XML directly when not in strict mode
        xml = extract_xml(out) or out
        _validate_xml_or_raise(xml)

    if debug_enabled:
        print("\n=== generator: lc_messages ===")
        for msg in lc_messages:
            role = msg.__class__.__name__
            print(f"[{role}]\n{msg.content}\n")

        print("=== generator: raw_out ===")
        print(out)

        if config_payload is not None:
            print("=== generator: parsed_config ===")
            print(json.dumps(config_payload, indent=2, ensure_ascii=False))
        if structured_meta is not None:
            print("=== generator: structured_meta ===")
            print(json.dumps(structured_meta, indent=2, ensure_ascii=False))

        print("=== generator: extracted_xml ===")
        print(xml)
        print("=== generator: end ===\n")

    # Post-sanitize to ensure attribute-style variables in <predefinition>/<newvarcte>
    xml = sanitize_newvarcte(xml)
    result: Dict[str, Any] = {"xml": xml, "sources": docs}
    if config_payload is not None:
        result["config"] = config_payload
    if structured_meta is not None:
        result["structured_meta"] = structured_meta
    return result


