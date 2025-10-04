#!/usr/bin/env python3
"""
Minimal Viable Prototype: Direct OpenAI File Search Two-Stage Workflow

This demonstrates the simplest possible two-agent workflow:
1. Agent 1: Use OpenAI file_search to find reference files
2. Agent 2: Use those references to generate config with strict JSON schema
3. Generate XML and optionally execute

Usage:
    python scripts/mvp_direct_file_search.py
    python scripts/mvp_direct_file_search.py --query "Create 2D dambreak"
    python scripts/mvp_direct_file_search.py --pause-after-agent1  # Inspect Agent 1 output
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Repository locations and configurable limits for reference loading
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAX_REFERENCE_FILES = int(os.environ.get("AGENT2_MAX_REFERENCE_FILES", "1"))
DEFAULT_MAX_REFERENCE_CHARS = int(os.environ.get("AGENT2_REFERENCE_MAX_CHARS", "6000"))


def print_header(title: str):
    """Print a prominent header."""
    print(f"\n{'=' * 80}")
    print(f"{title:^80}")
    print(f"{'=' * 80}\n")


def print_step(step_num: int, total: int, description: str):
    """Print a step indicator."""
    print(f"\n[Step {step_num}/{total}] {description}")
    print('-' * 80)


def _resolve_reference_path(source_path: str) -> Optional[Path]:
    """Resolve a retrieved reference filename to a local path."""
    if not source_path:
        return None

    candidate_paths: List[Path] = []
    path_obj = Path(source_path)
    if path_obj.is_absolute():
        candidate_paths.append(path_obj)
    else:
        candidate_paths.append(REPO_ROOT / path_obj)
        candidate_paths.append(REPO_ROOT / "AutoXml_script" / "config_library" / path_obj.name)
        candidate_paths.append(REPO_ROOT / "logs" / "mvp" / path_obj.name)

    seen: set[Path] = set()
    for candidate in candidate_paths:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
    return None


def _prepare_reference_documents(
    agent1_output: Dict[str, Any],
    *,
    max_files: int = DEFAULT_MAX_REFERENCE_FILES,
    max_chars: int = DEFAULT_MAX_REFERENCE_CHARS,
) -> List[Dict[str, Any]]:
    """Load local JSON references for Agent 2 consumption."""

    references = agent1_output.get("references") or []
    rerank_details = agent1_output.get("reference_rerank", {}).get("details") or []
    detail_by_rank = {
        detail.get("new_rank"): detail
        for detail in rerank_details
        if isinstance(detail, dict) and detail.get("new_rank") is not None
    }

    documents: List[Dict[str, Any]] = []
    for rank, ref in enumerate(references[:max_files]):
        attrs = ref.get("attributes") or {}
        source_path = attrs.get("source_path") or ref.get("filename")
        resolved = _resolve_reference_path(str(source_path) if source_path is not None else "")
        if resolved is None:
            print(f"Warning: could not resolve reference file for Agent 2: {source_path}")
            continue

        try:
            full_text = resolved.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"Warning: failed to read reference file {resolved}: {exc}")
            continue

        prompt_excerpt = full_text
        truncated = False
        if len(prompt_excerpt) > max_chars:
            prompt_excerpt = prompt_excerpt[:max_chars]
            truncated = True

        original_index = detail_by_rank.get(rank, {}).get("original_index", rank)

        documents.append(
            {
                "filename": ref.get("filename") or resolved.name,
                "path": str(resolved),
                "reference_index": original_index,
                "prompt_excerpt": prompt_excerpt,
                "full_text": full_text,
                "truncated": truncated,
            }
        )

    return documents


def _format_reference_documents(documents: List[Dict[str, Any]]) -> str:
    """Return a formatted string describing reference documents."""
    lines = ["REFERENCE DOCUMENTS:"]
    if not documents:
        lines.append("(no local documents resolved; rely on analysis text)")
        return "\n".join(lines)

    for doc in documents:
        header = f"### {doc.get('filename', 'unknown')} (index {doc.get('reference_index', '?')})"
        excerpt = doc.get("prompt_excerpt", "")
        lines.extend([header, "<json>", excerpt, "</json>", ""])
    return "\n".join(lines).rstrip()


def _reorder_sources_by_analysis_text(
    sources: List[Dict[str, Any]], analysis_text: str
) -> Optional[Tuple[List[int], List[Dict[str, Any]], List[Dict[str, Any]]]]:
    """Attempt to reorder sources based on their appearance in the first LLM analysis."""
    if not sources or not analysis_text:
        return None

    analysis_lower = analysis_text.lower()
    indexed_positions: List[Tuple[int, int]] = []
    for idx, src in enumerate(sources):
        attr = src.get("attributes") or {}
        candidates = [
            src.get("filename"),
            attr.get("filename"),
            attr.get("source_path"),
        ]
        best_pos: Optional[int] = None
        for candidate in candidates:
            if not candidate:
                continue
            candidate_str = str(candidate).strip()
            if not candidate_str:
                continue
            pos = analysis_lower.find(candidate_str.lower())
            if pos != -1 and (best_pos is None or pos < best_pos):
                best_pos = pos
        indexed_positions.append((idx, best_pos if best_pos is not None else -1))

    hits = [item for item in indexed_positions if item[1] >= 0]
    if not hits:
        return None

    ordered_indices = [idx for idx, _ in sorted(hits, key=lambda item: (item[1], item[0]))]
    missing_indices = [idx for idx, pos in indexed_positions if pos < 0 and idx not in ordered_indices]
    ordered_indices.extend(missing_indices)

    reordered_sources = [sources[i] for i in ordered_indices]

    details: List[Dict[str, Any]] = []
    for new_rank, original_idx in enumerate(ordered_indices):
        src = sources[original_idx]
        attr = src.get("attributes") or {}
        filename = src.get("filename") or attr.get("filename") or attr.get("source_path")
        details.append(
            {
                "new_rank": new_rank,
                "original_index": original_idx,
                "filename": filename,
                "reason": "Ordered by first LLM analysis listing.",
                "retention": "",
                "modification": "",
            }
        )

    return ordered_indices, reordered_sources, details


def agent_1_file_search(user_query: str, vector_store_id: str) -> Dict[str, Any]:
    """
    Agent 1: Use OpenAI file_search to retrieve relevant examples

    Returns:
        Dictionary with:
        - query: Original user query
        - references: List of reference files found (lightweight metadata only)
        - instructions: How Agent 2 should use these references
    """
    from rag.openai_file_search import response_with_file_search, get_last_run_info

    print_header("AGENT 1: REFERENCE FINDER (OpenAI File Search)")

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    reasoning = None
    if "gpt-5" in model.lower() or "o1" in model.lower() or "o3" in model.lower():
        reasoning_str = os.environ.get("OPENAI_REASONING")
        if reasoning_str:
            import json as json_module
            reasoning = json_module.loads(reasoning_str)

    print(f"Query: {user_query}")
    print(f"Model: {model}")
    print(f"Vector Store: {vector_store_id}\n")

    print_step(1, 3, "Searching vector store for relevant examples...")

    message_content = f"""Find the most relevant DualSPHysics configuration examples for this request:

{user_query}

List the reference files you found and explain:
1. Which example files are most relevant
2. What key parameters/structures should be used from each
3. What modifications are needed for this specific request

For each candidate reference returned by file_search:
- State whether it matches the user's constraints (e.g., dimensionality, physics, boundary methods).
- Keep the references you deem relevant and explain how to adapt them.
- If a candidate is not relevant, mention it briefly and explain why you are discarding it."""

    messages = [
        {
            "role": "system",
            "content": "You are a DualSPHysics expert. Analyze the user's request and find relevant configuration examples from the vector store. Review each candidate returned by file_search, decide whether it satisfies the user's constraints, keep the relevant ones, and briefly justify any you discard. Explain what you found and how it should be adapted.",
        },
        {
            "role": "user",
            "content": message_content,
        },
    ]

    assistant_message = response_with_file_search(
        messages=messages,
        model=model,
        vector_store_ids=[vector_store_id],
        reasoning=reasoning,
        temperature=None,
    )

    run_info = get_last_run_info()
    sources = run_info.get("sources", []) if run_info else []

    print(f"File search complete - found {len(sources)} sources\n")

    print_step(2, 3, "Analyzing references...")
    print(assistant_message)

    print_step(3, 3, "Preparing instructions for Agent 2...")

    rerank_method = "analysis_text"
    rerank_indices: List[int] = []
    rerank_details: List[Dict[str, Any]] = []
    reorder_result = _reorder_sources_by_analysis_text(sources, assistant_message)
    if reorder_result:
        rerank_indices, sources, rerank_details = reorder_result
    else:
        rerank_method = "vector_store"
        rerank_indices = list(range(len(sources)))

    sanitized_sources: List[Dict[str, Any]] = []
    for src in sources:
        sanitized_entry: Dict[str, Any] = {
            "vector_store_id": src.get("vector_store_id"),
            "file_id": src.get("file_id"),
            "filename": src.get("filename"),
            "score": src.get("score"),
            "attributes": src.get("attributes"),
        }
        if src.get("search_call_id") is not None:
            sanitized_entry["search_call_id"] = src.get("search_call_id")
        sanitized_sources.append({k: v for k, v in sanitized_entry.items() if v is not None})

    result = {
        "query": user_query,
        "references": sanitized_sources,
        "reference_rerank": {
            "method": rerank_method,
            "indices": rerank_indices,
            "details": rerank_details,
        },
        "analysis": assistant_message,
        "instructions_for_agent2": (
            "Use the referenced configuration files as templates. "
            "Extract relevant parameters and structures. "
            "Modify geometry and parameters according to the user's specific requirements. "
            "Ensure all required schema fields are populated."
        ),
    }

    output_dir = Path("logs/mvp")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "agent1_output.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n  Agent 1 complete")
    print(f"  - References found: {len(sources)}")
    print(f"  - Output saved to: logs/mvp/agent1_output.json")

    return result


def agent_2_generate_config(agent1_output: Dict[str, Any], schema_path: Path) -> Dict[str, Any]:
    """Agent 2: Use references from Agent 1 to generate strict JSON config."""
    from openai import OpenAI

    print_header("AGENT 2: CONFIG GENERATOR (Strict JSON Schema)")

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    reference_documents = _prepare_reference_documents(agent1_output)
    if reference_documents:
        print(f"Loaded {len(reference_documents)} local reference file(s) for Agent 2.")
    else:
        print("No local reference files could be resolved for Agent 2 input.")

    output_dir = Path("logs/mvp")
    output_dir.mkdir(parents=True, exist_ok=True)
    agent2_input_payload = dict(agent1_output)
    agent2_input_payload["reference_documents"] = reference_documents
    agent2_input_path = output_dir / "agent2_input.json"
    with open(agent2_input_path, "w", encoding="utf-8") as f:
        json.dump(agent2_input_payload, f, indent=2, ensure_ascii=False)
    print(f"Input payload saved to: {agent2_input_path}")

    print_step(1, 3, "Loading DualSPHysics JSON schema...")
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    def add_additional_properties(obj: Any):
        if isinstance(obj, dict):
            if obj.get("type") == "object" or "properties" in obj:
                if "additionalProperties" not in obj:
                    obj["additionalProperties"] = False
            for value in obj.values():
                add_additional_properties(value)
        elif isinstance(obj, list):
            for item in obj:
                add_additional_properties(item)

    add_additional_properties(schema)
    print(f"Schema loaded: {schema_path.name}")

    print_step(2, 3, "Building prompt from Agent 1 references...")

    references_text = agent1_output.get("analysis", "")
    instructions = agent1_output.get("instructions_for_agent2", "")
    reference_docs_section = _format_reference_documents(reference_documents)

    prompt = f"""Generate a complete DualSPHysics configuration JSON based on the following:

USER REQUEST:
{agent1_output['query']}

REFERENCE ANALYSIS (from Agent 1):
{references_text}

{reference_docs_section}

INSTRUCTIONS:
{instructions}

REQUIREMENTS:
1. Output ONLY valid JSON matching the provided schema
2. Use the reference files as structural templates
3. Adapt parameters to match the user's specific request
4. Ensure all required fields are present
5. Maintain consistency in units and dimensions

Generate the configuration JSON now:"""

    print(f"Prompt built ({len(prompt)} chars)\n")

    print_step(3, 3, "Generating config with strict schema enforcement...")

    api_params: Dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a DualSPHysics configuration generator. Output only valid JSON that strictly conforms to the provided schema.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "dualsphysics_config",
                "strict": True,
                "schema": schema,
            },
        },
    }
    if not any(x in model.lower() for x in ["gpt-5", "o1", "o3"]):
        api_params["temperature"] = 0.0

    response = client.chat.completions.create(**api_params)
    config_json = json.loads(response.choices[0].message.content)

    print(f"Config generated ({len(config_json)} top-level keys)")

    with open(output_dir / "agent2_config.json", "w", encoding="utf-8") as f:
        json.dump(config_json, f, indent=2, ensure_ascii=False)

    print(f"Agent 2 complete")
    print(f"  - Output saved to: logs/mvp/agent2_config.json")

    return config_json


def generate_xml_and_execute(config_json: Dict[str, Any], execute: bool = False):
    """Generate XML from config and optionally execute GenCase."""
    from AutoXml_script.generate_xml import generate_case_xml
    from chains.json_normalizer import normalize_case_config

    print_header("XML GENERATION & EXECUTION")

    print_step(1, 3 if execute else 2, "Normalizing config...")
    normalization = normalize_case_config(config_json)
    config = normalization.config

    if normalization.warnings:
        print(f"Normalization warnings: {len(normalization.warnings)}")
        for warning in normalization.warnings[:3]:
            print(f"  - {warning}")
    else:
        print("No normalization warnings")

    print_step(2, 3 if execute else 2, "Generating XML...")
    xml = generate_case_xml(config)

    output_dir = Path("logs/mvp")
    xml_path = output_dir / "generated_case.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"XML generated ({len(xml)} chars)")
    print(f"  - Saved to: {xml_path}")

    if execute:
        print_step(3, 3, "Executing GenCase...")
        try:
            from tools.exec import run_gencase
            run_gencase(str(xml_path), output_dir="logs/mvp/case_out")
            print("GenCase execution complete")
            print("  - Output directory: logs/mvp/case_out")
        except Exception as exc:
            print(f"GenCase execution failed: {exc}")

    return xml


def main():
    parser = argparse.ArgumentParser(description="MVP: Direct OpenAI File Search Two-Stage Workflow")
    parser.add_argument(
        "--query",
        default="Create a 2D dambreak simulation with water height 2 meters",
        help="User query",
    )
    parser.add_argument(
        "--pause-after-agent1",
        action="store_true",
        help="Pause after Agent 1 for inspection",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute GenCase on generated XML",
    )
    args = parser.parse_args()

    print_header("ENVIRONMENT CHECK")
    required_vars = ["OPENAI_API_KEY", "OPENAI_RAG_VS_DESIGN_ID"]
    missing = [v for v in required_vars if not os.environ.get(v)]

    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("\nPlease set:")
        for var in missing:
            print(f"  export {var}=your_value_here")
        return 1

    vector_store_id = os.environ["OPENAI_RAG_VS_DESIGN_ID"]
    print(f"OPENAI_API_KEY: {'*' * 20}")
    print(f"OPENAI_RAG_VS_DESIGN_ID: {vector_store_id[:20]}...")
    print(f"OPENAI_MODEL: {os.environ.get('OPENAI_MODEL', 'gpt-4o')}")

    try:
        agent1_output = agent_1_file_search(args.query, vector_store_id)

        if args.pause_after_agent1:
            print_header("PAUSED AFTER AGENT 1")
            print("Review the output at: logs/mvp/agent1_output.json")
            print("Press Enter to continue to Agent 2, or Ctrl+C to exit...")
            input()

        schema_path = Path("schemas/dualsphysics_config_schema.json")
        config_json = agent_2_generate_config(agent1_output, schema_path)

        generate_xml_and_execute(config_json, execute=args.execute)

        print_header("SUCCESS!")
        print("Generated files:")
        print("  1. logs/mvp/agent1_output.json     - Agent 1 references & analysis")
        print("  2. logs/mvp/agent2_config.json     - Agent 2 generated config")
        print("  3. logs/mvp/generated_case.xml     - Final XML output")
        if args.execute:
            print("  4. logs/mvp/case_out/              - GenCase execution results")

        print("\nWorkflow complete!")
        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as exc:
        print(f"\n\n ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
