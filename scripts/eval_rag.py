#!/usr/bin/env python
"""Simple Recall@5 evaluation harness for OpenAI File Search RAG."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from chains.rag_utils import build_metadata_filter

DEFAULT_REGISTRY = Path("rag/vector_stores.json")


@dataclass
class EvalCase:
    label: str
    vector_store_id: str
    query: str
    expected: List[str]
    metadata_filter: Optional[Dict[str, str]] = None


def _build_filter_payload(metadata: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if not metadata:
        return None
    filters = []
    for key, value in metadata.items():
        if value is None:
            continue
        filters.append({"type": "eq", "key": key, "value": value})
    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"type": "and", "filters": filters}


def _top_filenames(page) -> List[str]:
    names: List[str] = []
    for item in page:
        name = getattr(item, "filename", None)
        if name:
            names.append(name)
    return names


def evaluate_case(client: OpenAI, case: EvalCase, max_results: int = 5) -> Dict[str, object]:
    metadata = case.metadata_filter or build_metadata_filter(case.query)
    filter_payload = _build_filter_payload(metadata)
    page = client.beta.vector_stores.search(
        case.vector_store_id,
        query=case.query,
        filters=filter_payload,
        max_num_results=max_results,
        rewrite_query=True,
    )
    filenames = _top_filenames(page)
    expected_set = {name.lower() for name in case.expected}
    hits = [name for name in filenames if name.lower() in expected_set]
    recall = len(hits) / len(case.expected) if case.expected else 0.0
    return {
        "label": case.label,
        "retrieved": filenames,
        "hits": hits,
        "recall": recall,
    }


def build_default_cases(design_vs_id: Optional[str], error_vs_id: Optional[str]) -> List[EvalCase]:
    cases: List[EvalCase] = []
    if design_vs_id:
        cases.append(
            EvalCase(
                label="design_dambreak_2d",
                vector_store_id=design_vs_id,
                query="2D dambreak validation example with thin column",
                expected=["CaseDambreakVal2D_Def.xml", "CaseDambreak_Def.xml"],
                metadata_filter={"case_type": "dambreak", "dim": "2D"},
            )
        )
        cases.append(
            EvalCase(
                label="design_wavemaker",
                vector_store_id=design_vs_id,
                query="wavemaker flap beach setup",
                expected=["CaseFlapBeach_REG_Def.xml", "CaseWavemaker_Def.xml"],
                metadata_filter={"case_type": "wavemaker"},
            )
        )
    if error_vs_id:
        cases.append(
            EvalCase(
                label="error_logs",
                vector_store_id=error_vs_id,
                query="solver divergence in dambreak run",
                expected=["error_example.md"],
                metadata_filter={"case_type": "dambreak"},
            )
        )
    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate vector-store recall")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY, help="Path to vector store registry JSON")
    parser.add_argument("--threshold", type=float, default=0.8, help="Minimum Recall@5 required to pass")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()

    registry: Dict[str, str] = {}
    if args.registry.exists():
        try:
            registry = json.loads(args.registry.read_text(encoding="utf-8"))
        except Exception:
            registry = {}

    design_vs_id = os.environ.get("OPENAI_RAG_VS_DESIGN_ID") or registry.get("design")
    error_vs_id = os.environ.get("OPENAI_RAG_VS_ERROR_ID") or registry.get("error")

    cases = build_default_cases(design_vs_id or None, error_vs_id or None)
    if not cases:
        print("No evaluation cases available. Ensure vector store ids are configured.")
        raise SystemExit(1)

    client = OpenAI()

    results = [evaluate_case(client, case) for case in cases]
    total_hits = sum(len(result["hits"]) for result in results)
    total_expected = sum(len(case.expected) for case in cases)
    overall_recall = total_hits / total_expected if total_expected else 0.0

    print("label\trecall\thits\tretrieved")
    for result in results:
        print(
            f"{result['label']}\t{result['recall']:.2f}\t"
            f"{', '.join(result['hits']) or '-'}\t{', '.join(result['retrieved']) or '-'}"
        )

    print(f"Overall Recall@5: {overall_recall:.2f}")
    if overall_recall < args.threshold:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
