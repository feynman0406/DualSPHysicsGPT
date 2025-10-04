"""RAG Planning Agent - Stage 1 of two-stage pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.config import load_planning_settings
from agents.example_scorer import ExampleScorer
from agents.logging_utils import log_stage
from agents.plan_validator import validate_plan_json
from agents.quote_extractor import QuoteExtractor
from rag.openai_file_search import get_file_id_to_name_map, get_last_run_info

LOGGER = logging.getLogger(__name__)


class PlanningAgent:
    """Planning Agent for RAG + Planning stage."""

    def __init__(self, config_library_path: Optional[Path] = None):
        """
        Initialize Planning Agent.

        Args:
            config_library_path: Path to config library (default: AutoXml_script/config_library)
        """
        self.settings = load_planning_settings()
        self.config_library = config_library_path or Path("AutoXml_script/config_library")
        self.scorer = ExampleScorer()
        self.quote_extractor = QuoteExtractor(
            max_quote_length=self.settings.max_quote_length,
            max_quotes_per_file=3,
        )

    def run_planning_agent(
        self,
        user_query: str,
        vector_store_ids: List[str],
        metadata_filter: Optional[Dict[str, Any]] = None,
        retry_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for Planning Agent.

        Args:
            user_query: User's original query
            vector_store_ids: OpenAI vector store IDs to search
            metadata_filter: Metadata filter for retrieval
            retry_context: Context from previous failed attempt (if retrying)

        Returns:
            Plan JSON dictionary
        """
        log_stage("PLANNING_AGENT_START", {"query_length": len(user_query)})

        try:
            # Retrieve and parse search results (assumes file_search already called)
            search_info = get_last_run_info()
            if not search_info:
                raise RuntimeError("No search results available. Call file_search first.")

            # Parse retrieved files
            sources = search_info.get("sources", [])
            if not sources or (len(sources) == 1 and sources[0].get("note") == "no_source_matched"):
                LOGGER.warning("No sources matched retrieval filters")
                return self._build_empty_plan(user_query, metadata_filter, search_info)

            # Score and select curated examples
            curated_examples, primary_info = self._select_curated_examples(sources, user_query)

            # Extract parameters from examples
            extracted_params = self._extract_parameters(curated_examples)

            # Detect coverage
            coverage = self._detect_coverage(curated_examples, metadata_filter)

            # Detect missing params and conflicts
            missing_params, conflicts = self._detect_gaps_and_conflicts(
                extracted_params, coverage, user_query
            )

            # Generate schema guidance placeholder
            schema_guidance = self._generate_schema_guidance(
                missing_params, conflicts, extracted_params, retry_context, primary_info
            )

            # Build Plan JSON
            plan_json = self._build_plan_json(
                query=user_query,
                metadata_filter=metadata_filter,
                curated_examples=curated_examples,
                extracted_params=extracted_params,
                coverage=coverage,
                missing_params=missing_params,
                conflicts=conflicts,
                schema_guidance=schema_guidance,
                search_info=search_info,
            )

            # Validate Plan JSON
            is_valid, errors = validate_plan_json(plan_json)
            if not is_valid:
                LOGGER.error(f"Plan JSON validation failed: {errors}")
                # Try to fix common issues
                plan_json = self._fix_plan_json(plan_json, errors)

            # Persist Plan JSON
            self._persist_plan_json(plan_json, primary_info)

            log_stage("PLANNING_AGENT_COMPLETE", {
                "curated_count": len(curated_examples),
                "extracted_params": len(extracted_params),
                "missing_params": len(missing_params),
            })

            return plan_json

        except Exception as exc:
            LOGGER.error(f"Planning Agent failed: {exc}", exc_info=True)
            raise

    def _select_curated_examples(
        self,
        sources: List[Dict[str, Any]],
        user_query: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Select and score top examples and primary reference metadata."""
        scored_examples: List[Dict[str, Any]] = []

        # Build file ID to name mapping
        vector_store_ids = {src.get("vector_store_id") for src in sources if src.get("vector_store_id")}
        file_id_map = {}
        for vs_id in vector_store_ids:
            if vs_id:
                file_id_map.update(get_file_id_to_name_map(vs_id))

        for idx, source in enumerate(sources[: self.settings.max_examples]):
            file_id = source.get("file_id")
            filename = source.get("filename", "")

            # Try to resolve full path
            source_path = file_id_map.get(file_id, filename) if file_id else filename
            file_path = self.config_library / Path(source_path).name

            if not file_path.exists():
                # Try without extension change
                file_path = self.config_library / source_path

            if not file_path.exists():
                LOGGER.warning(f"File not found in config library: {source_path}")
                continue

            # Score the example
            aggregate_score, score_rationale = self.scorer.score_example(
                file_path, user_query, source.get("attributes", {})
            )

            # Extract quotes
            quotes = self.quote_extractor.extract_quotes(file_path, user_query, score_rationale)

            # Build curated example entry
            example = {
                "file_id": file_id,
                "filename": source_path,
                "rank": idx + 1,
                "score": source.get("score"),
                "rationale": self._format_rationale(score_rationale, aggregate_score),
                "spans": quotes,
            }

            scored_examples.append(
                {
                    "aggregate": aggregate_score,
                    "example": example,
                    "score_meta": score_rationale,
                    "file_path": str(file_path),
                    "attributes": source.get("attributes", {}),
                }
            )

        # Sort by aggregate score (descending) and take top examples
        scored_examples.sort(key=lambda item: item["aggregate"], reverse=True)
        curated = [item["example"] for item in scored_examples[: self.settings.max_examples]]

        primary_payload: Optional[Dict[str, Any]] = None
        if scored_examples:
            top = scored_examples[0]
            primary_payload = {
                "aggregate": top["aggregate"],
                "score_meta": top["score_meta"],
                "file_path": top["file_path"],
                "filename": top["example"].get("filename", ""),
                "attributes": top.get("attributes", {}),
            }

        return curated, primary_payload

    def _format_rationale(self, score_rationale: Dict[str, Any], aggregate_score: float) -> str:
        """Compose a concise rationale string with score summary."""
        summary = (
            f"Aggregate={aggregate_score:.2f} "
            f"(Alg={score_rationale.get('algorithm_score', 'n/a')}, "
            f"Geo={score_rationale.get('geometry_score', 'n/a')}, "
            f"Bnd={score_rationale.get('boundary_score', 'n/a')}, "
            f"Exec={score_rationale.get('execution_score', 'n/a')})"
        )
        rationale_text = score_rationale.get("rationale", "")
        adjustments = score_rationale.get("adjustments") or []
        adjustment_text = ""
        if adjustments:
            adjustment_text = "Adjustments: " + '; '.join(adjustments[:3])
        parts = [summary]
        if rationale_text:
            parts.append(rationale_text)
        if adjustment_text:
            parts.append(adjustment_text)
        return ' | '.join(part for part in parts if part)

    def _extract_parameters(self, curated_examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract parameters from curated examples."""
        params = []
        seen_params = set()

        for example in curated_examples:
            filename = example.get("filename", "")
            file_path = self.config_library / Path(filename).name

            if not file_path.exists():
                continue

            try:
                # Load the file and extract key parameters
                if file_path.suffix.lower() == ".json":
                    with file_path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Extract common parameters
                    case_data = data.get("case", {})
                    
                    # Execution parameters
                    if "execution" in case_data:
                        exec_data = case_data["execution"]
                        for key in ["parameters", "special"]:
                            if key in exec_data and isinstance(exec_data[key], dict):
                                for param_name, param_value in exec_data[key].items():
                                    param_key = f"execution.{key}.{param_name}"
                                    if param_key not in seen_params:
                                        params.append({
                                            "name": param_key,
                                            "value": param_value,
                                            "unit": None,
                                            "source": filename,
                                        })
                                        seen_params.add(param_key)

            except Exception as exc:
                LOGGER.warning(f"Failed to extract params from {filename}: {exc}")

        return params[:64]  # Limit to schema max

    def _detect_coverage(
        self,
        curated_examples: List[Dict[str, Any]],
        metadata_filter: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Detect coverage of case_type, dim, features."""
        coverage = {
            "case_type": metadata_filter.get("case_type") if metadata_filter else None,
            "dim": metadata_filter.get("dim") if metadata_filter else None,
            "features": [],
        }

        # Collect features from examples
        features_set = set()
        for example in curated_examples:
            filename = example.get("filename", "")
            if "mDBC" in filename or "mdbc" in filename.lower():
                features_set.add("mDBC")
            if "floating" in filename.lower():
                features_set.add("floating")
            if "wave" in filename.lower():
                features_set.add("waves")
            if "damping" in filename.lower():
                features_set.add("damping")

        coverage["features"] = sorted(features_set)[:16]  # Limit to schema max

        return coverage

    def _detect_gaps_and_conflicts(
        self,
        extracted_params: List[Dict[str, Any]],
        coverage: Dict[str, Any],
        user_query: str,
    ) -> tuple[List[str], List[str]]:
        """Detect missing parameters and conflicts."""
        missing = []
        conflicts = []

        # Check for required execution parameters
        param_names = {p["name"] for p in extracted_params}
        
        required_params = [
            "execution.parameters.StepAlgorithm",
            "execution.parameters.VerletSteps",
            "execution.parameters.Kernel",
            "execution.parameters.ViscoTreatment",
            "execution.parameters.Visco",
            "execution.parameters.ViscoBoundFactor",
            "execution.parameters.DensityDT",
            "execution.parameters.Shifting",
            "execution.parameters.RigidAlgorithm",
            "execution.parameters.TimeMax",
            "execution.parameters.TimeOut",
            "execution.parameters.PartsOutMax",
            "execution.parameters.CoefficientH",
        ]

        for req_param in required_params:
            if req_param not in param_names:
                missing.append(req_param)

        # Check for dimension conflicts
        if coverage.get("dim"):
            query_lower = user_query.lower()
            if ("2d" in query_lower or "2-d" in query_lower) and coverage["dim"] != "2D":
                conflicts.append(f"Query suggests 2D but examples are {coverage['dim']}")
            elif ("3d" in query_lower or "3-d" in query_lower) and coverage["dim"] != "3D":
                conflicts.append(f"Query suggests 3D but examples are {coverage['dim']}")

        return missing[:64], conflicts[:32]  # Limit to schema max

    def _generate_schema_guidance(
        self,
        missing_params: List[str],
        conflicts: List[str],
        extracted_params: List[Dict[str, Any]],
        retry_context: Optional[Dict[str, Any]],
        primary_info: Optional[Dict[str, Any]],
    ) -> str:
        """Generate schema guidance placeholder with primary reference directives."""
        lines = ["<<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>", ""]

        if primary_info:
            score_meta = primary_info.get("score_meta", {})
            aggregate = float(primary_info.get("aggregate", 0.0) or 0.0)
            filename = Path(primary_info.get("filename", "")).name
            adjustments = score_meta.get("adjustments") or []
            classification = "close match" if aggregate >= 4.0 else "partial match"
            if aggregate < 3.2:
                classification = "low similarity"

            lines.append("[primary_reference]")
            lines.append(
                f"- Template: {filename or 'unknown'} (aggregate={aggregate:.2f}, Alg={score_meta.get('algorithm_score', 'n/a')}, Geo={score_meta.get('geometry_score', 'n/a')})"
            )
            lines.append(
                f"- Classification: {classification}; copy geometry/algorithm blocks verbatim before edits"
            )

            if extracted_params:
                override_names = ', '.join(param["name"] for param in extracted_params[:6])
                lines.append(f"- Apply numeric overrides only for: {override_names}")

            if adjustments:
                lines.append(f"- Review adjustments: {'; '.join(adjustments[:3])}")

            if aggregate < 3.2:
                lines.append("- Despite low similarity, clone structure to prevent schema drift and validate manually")

            lines.append("")

        # Required fields
        if missing_params:
            lines.append("[required_fields]")
            for param in missing_params[:10]:  # Top 10 most important
                lines.append(f"- {param} needs to be specified")
            lines.append("")

        # Assumptions
        lines.append("[assumptions]")
        if primary_info:
            lines.append("- Keep geometry and algorithm layout identical to the primary template when filling JSON")
        lines.append("- If no boundary specified, maintain mkbound=0")
        lines.append("- Use extracted parameters as defaults where available")
        if extracted_params:
            lines.append(f"- {len(extracted_params)} parameters extracted from examples")
        lines.append("")

        # Open questions
        lines.append("[open_questions]")
        if conflicts:
            lines.append(f"- Resolve conflicts: {'; '.join(conflicts[:3])}")
        lines.append("- Verify geometry dimensions match user requirements")
        lines.append("- Confirm execution timemax and timeout values")
        lines.append("")

        # Retry feedback (if retrying)
        if retry_context:
            attempt = retry_context.get("attempt", 1)
            feedback = retry_context.get("stage2_feedback", "")
            lines.append(f"[retry_{attempt}]")
            lines.append(f"Previous attempt failed: {feedback}")
            lines.append("Actions taken: Enhanced parameter extraction")
            lines.append("")

        return '\n'.join(lines)

    def _build_plan_json(
        self,
        query: str,
        metadata_filter: Optional[Dict[str, Any]],
        curated_examples: List[Dict[str, Any]],
        extracted_params: List[Dict[str, Any]],
        coverage: Dict[str, Any],
        missing_params: List[str],
        conflicts: List[str],
        schema_guidance: str,
        search_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the Plan JSON."""
        # Build citations from curated examples
        citations = []
        for example in curated_examples:
            for idx, span in enumerate(example.get("spans", [])):
                citations.append({
                    "file_id": example.get("file_id"),
                    "filename": example.get("filename", ""),
                    "span_index": idx,
                    "quote": span.get("quote", ""),
                })

        plan = {
            "query": query[:4000],  # Limit to schema max
            "metadata_filter": metadata_filter,
            "curated_examples": curated_examples,
            "coverage": coverage,
            "extracted_params": extracted_params,
            "missing_params": missing_params,
            "conflicts": conflicts,
            "schema_guidance": schema_guidance[:4000],  # Limit to schema max
            "citations": citations[:24],  # Limit to schema max
        }

        return plan

    def _build_empty_plan(
        self,
        query: str,
        metadata_filter: Optional[Dict[str, Any]],
        search_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build an empty plan when no sources matched."""
        return {
            "query": query[:4000],
            "metadata_filter": metadata_filter,
            "curated_examples": [],
            "coverage": {
                "case_type": None,
                "dim": None,
                "features": [],
            },
            "extracted_params": [],
            "missing_params": ["All parameters - no sources matched"],
            "conflicts": [],
            "schema_guidance": (
                "<<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>\n\n"
                "[required_fields]\n"
                "- All fields need to be specified from scratch\n\n"
                "[assumptions]\n"
                "- No retrieval results, generate conservative defaults\n\n"
                "[open_questions]\n"
                "- Confirm all user requirements since no examples available\n"
            ),
            "citations": [],
        }

    def _fix_plan_json(self, plan: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
        """Attempt to fix common validation errors."""
        # Truncate long strings
        if "query" in plan and len(plan["query"]) > 4000:
            plan["query"] = plan["query"][:4000]
        if "schema_guidance" in plan and len(plan["schema_guidance"]) > 4000:
            plan["schema_guidance"] = plan["schema_guidance"][:4000]
        
        # Limit array sizes
        if "curated_examples" in plan and len(plan["curated_examples"]) > 12:
            plan["curated_examples"] = plan["curated_examples"][:12]
        if "extracted_params" in plan and len(plan["extracted_params"]) > 64:
            plan["extracted_params"] = plan["extracted_params"][:64]
        if "missing_params" in plan and len(plan["missing_params"]) > 64:
            plan["missing_params"] = plan["missing_params"][:64]
        if "conflicts" in plan and len(plan["conflicts"]) > 32:
            plan["conflicts"] = plan["conflicts"][:32]
        if "citations" in plan and len(plan["citations"]) > 24:
            plan["citations"] = plan["citations"][:24]

        return plan

    def _persist_plan_json(
        self,
        plan: Dict[str, Any],
        primary_info: Optional[Dict[str, Any]],
    ) -> None:
        """Persist Plan JSON to logs/last_run/planning_plan.json."""
        log_dir = Path("logs/last_run")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Add metadata
        enriched_plan = dict(plan)
        enriched_plan["_metadata"] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "completed",
            "attempt": 1,
            "plan_completion_rate": self._compute_completion_rate(plan),
        }

        if primary_info:
            score_meta = primary_info.get("score_meta", {})
            enriched_plan["_metadata"]["primary_reference"] = {
                "filename": Path(primary_info.get("filename", "")).name,
                "aggregate": round(float(primary_info.get("aggregate", 0.0) or 0.0), 2),
                "algorithm_score": score_meta.get("algorithm_score"),
                "geometry_score": score_meta.get("geometry_score"),
                "boundary_score": score_meta.get("boundary_score"),
                "execution_score": score_meta.get("execution_score"),
            }

        output_path = log_dir / "planning_plan.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(enriched_plan, f, indent=2, ensure_ascii=False)

        LOGGER.info(f"Plan JSON persisted to {output_path}")

    def _compute_completion_rate(self, plan: Dict[str, Any]) -> float:
        """Compute plan completion rate (filled fields / required fields)."""
        required_fields = 13  # From schema: StepAlgorithm, VerletSteps, Kernel, etc.
        filled_fields = len(plan.get("extracted_params", []))
        
        rate = filled_fields / required_fields if required_fields > 0 else 0.0
        return round(min(1.0, rate), 2)


def run_planning_agent(
    user_query: str,
    vector_store_ids: List[str],
    metadata_filter: Optional[Dict[str, Any]] = None,
    retry_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to run Planning Agent.

    Args:
        user_query: User's query
        vector_store_ids: OpenAI vector store IDs
        metadata_filter: Metadata filter for retrieval
        retry_context: Retry context from previous failure

    Returns:
        Plan JSON dictionary
    """
    agent = PlanningAgent()
    return agent.run_planning_agent(user_query, vector_store_ids, metadata_filter, retry_context)


__all__ = ["PlanningAgent", "run_planning_agent"]
