"""XML/JSON example scoring for Planning Agent."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple

LOGGER = logging.getLogger(__name__)


class ExampleScorer:
    """Scores retrieved examples on 4 dimensions for Planning Agent."""

    def __init__(self):
        """Initialize the scorer."""
        pass

    def score_example(
        self,
        file_path: Path,
        user_query: str,
        metadata: Dict[str, Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Score an example file on 4 dimensions (1-5 scale).

        Args:
            file_path: Path to the example file (JSON or XML)
            user_query: User's query text
            metadata: File metadata from retrieval

        Returns:
            Tuple of (aggregate_score, rationale_dict) where rationale_dict contains:
                - algorithm_score: 1-5
                - geometry_score: 1-5
                - boundary_score: 1-5
                - execution_score: 1-5
                - rationale: str
                - adjustments: List[str]
        """
        try:
            if file_path.suffix.lower() == ".json":
                content = self._load_json(file_path)
            elif file_path.suffix.lower() == ".xml":
                content = self._load_xml(file_path)
            else:
                LOGGER.warning(f"Unsupported file type: {file_path}")
                return 1.0, self._default_rationale("Unsupported file type")

            scores = self._compute_scores(content, user_query, metadata)
            return scores["aggregate"], scores

        except Exception as exc:
            LOGGER.error(f"Failed to score {file_path}: {exc}")
            return 1.0, self._default_rationale(f"Scoring error: {exc}")

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load JSON file."""
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_xml(self, path: Path) -> Dict[str, Any]:
        """Load XML file and convert to dict-like structure."""
        tree = ET.parse(path)
        root = tree.getroot()
        return self._xml_to_dict(root)

    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary."""
        result: Dict[str, Any] = {}
        
        # Add attributes
        if element.attrib:
            result["@attributes"] = dict(element.attrib)
        
        # Add text content
        if element.text and element.text.strip():
            result["@text"] = element.text.strip()
        
        # Add children
        for child in element:
            child_dict = self._xml_to_dict(child)
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_dict)
            else:
                result[child.tag] = child_dict
        
        return result

    def _compute_scores(
        self,
        content: Dict[str, Any],
        user_query: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute 4-dimension scores."""
        query_lower = user_query.lower()
        
        # Extract key information from content
        case_info = self._extract_case_info(content)
        
        # Score Algorithm (workflow and main commands)
        algorithm_score = self._score_algorithm(case_info, query_lower, metadata)
        
        # Score Geometry (dimensions and fill)
        geometry_score = self._score_geometry(case_info, query_lower, metadata)
        
        # Score Boundary/Materials (mk, boundary conditions, floatings)
        boundary_score = self._score_boundary(case_info, query_lower, metadata)
        
        # Score Execution (parameters, gauges, timeout)
        execution_score = self._score_execution(case_info, query_lower, metadata)
        
        # Aggregate score (simple average)
        aggregate = (algorithm_score + geometry_score + boundary_score + execution_score) / 4.0
        
        # Generate rationale
        rationale_parts = []
        adjustments = []
        
        if algorithm_score >= 4:
            rationale_parts.append(f"Algorithm={algorithm_score:.1f} (can reuse directly)")
        elif algorithm_score >= 3:
            rationale_parts.append(f"Algorithm={algorithm_score:.1f} (minor adaptations needed)")
            adjustments.append("Review algorithm parameters")
        else:
            rationale_parts.append(f"Algorithm={algorithm_score:.1f} (significant changes required)")
            adjustments.append("Reconsider algorithm approach")
        
        if geometry_score >= 4:
            rationale_parts.append(f"Geometry={geometry_score:.1f} (dimensions match)")
        elif geometry_score >= 2:
            rationale_parts.append(f"Geometry={geometry_score:.1f} (need size adjustments)")
            adjustments.append(f"Adjust geometry dimensions based on query requirements")
        else:
            rationale_parts.append(f"Geometry={geometry_score:.1f} (substantial rework needed)")
            adjustments.append("Redesign geometry layout")
        
        if boundary_score >= 4:
            rationale_parts.append(f"Boundary={boundary_score:.1f} (conditions suitable)")
        elif boundary_score >= 2:
            rationale_parts.append(f"Boundary={boundary_score:.1f} (some adjustments)")
            adjustments.append("Review boundary conditions and mk values")
        else:
            rationale_parts.append(f"Boundary={boundary_score:.1f} (major changes)")
            adjustments.append("Reconfigure boundary setup")
        
        if execution_score >= 4:
            rationale_parts.append(f"Execution={execution_score:.1f} (parameters good)")
        elif execution_score >= 2:
            rationale_parts.append(f"Execution={execution_score:.1f} (tune parameters)")
            adjustments.append("Adjust timemax, dt, or other execution params")
        else:
            rationale_parts.append(f"Execution={execution_score:.1f} (rework needed)")
            adjustments.append("Reconfigure execution parameters")
        
        rationale = " | ".join(rationale_parts)
        
        return {
            "algorithm_score": round(algorithm_score, 1),
            "geometry_score": round(geometry_score, 1),
            "boundary_score": round(boundary_score, 1),
            "execution_score": round(execution_score, 1),
            "aggregate": round(aggregate, 2),
            "rationale": rationale,
            "adjustments": adjustments,
        }

    def _extract_case_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant case information from content."""
        info: Dict[str, Any] = {
            "has_geometry": False,
            "has_execution": False,
            "has_boundaries": False,
            "has_floatings": False,
            "case_type": None,
            "dim": None,
        }
        
        # Try to extract case information
        if "case" in content:
            case = content["case"]
            
            # Check for geometry
            if "geometry" in case or "commands" in case:
                info["has_geometry"] = True
            
            # Check for execution
            if "execution" in case:
                info["has_execution"] = True
            
            # Check for boundaries/properties
            if "properties" in case:
                info["has_boundaries"] = True
            
            # Check for floatings
            if "floatings" in case:
                info["has_floatings"] = True
            
            # Extract metadata if available
            if "@attributes" in case:
                attrs = case["@attributes"]
                info["case_type"] = attrs.get("type")
                info["dim"] = attrs.get("dim")
        
        return info

    def _score_algorithm(
        self,
        case_info: Dict[str, Any],
        query_lower: str,
        metadata: Dict[str, Any],
    ) -> float:
        """Score algorithm compatibility (1-5)."""
        score = 3.0  # Default: moderate fit
        
        # Check case type match
        case_type = metadata.get("case_type", "").lower()
        if case_type:
            if case_type in query_lower:
                score += 1.5
            elif any(kw in query_lower for kw in ["dambreak", "wavemaker", "sloshing"]):
                # Partial match
                if case_type in ["dambreak", "wavemaker", "sloshing"]:
                    score += 0.5
        
        # Check if has necessary components
        if case_info.get("has_execution"):
            score += 0.5
        
        return min(5.0, max(1.0, score))

    def _score_geometry(
        self,
        case_info: Dict[str, Any],
        query_lower: str,
        metadata: Dict[str, Any],
    ) -> float:
        """Score geometry compatibility (1-5)."""
        score = 3.0  # Default
        
        # Check dimension match
        dim = metadata.get("dim", "").upper()
        if dim:
            if ("2d" in query_lower or "2-d" in query_lower) and dim == "2D":
                score += 1.0
            elif ("3d" in query_lower or "3-d" in query_lower) and dim == "3D":
                score += 1.0
            elif dim in query_lower:
                score += 0.5
        
        # Check if has geometry
        if case_info.get("has_geometry"):
            score += 0.5
        
        return min(5.0, max(1.0, score))

    def _score_boundary(
        self,
        case_info: Dict[str, Any],
        query_lower: str,
        metadata: Dict[str, Any],
    ) -> float:
        """Score boundary/materials compatibility (1-5)."""
        score = 3.0  # Default
        
        # Check for boundary-related keywords
        boundary_keywords = ["boundary", "inlet", "outlet", "wall", "floating"]
        if any(kw in query_lower for kw in boundary_keywords):
            if case_info.get("has_boundaries"):
                score += 1.0
            if case_info.get("has_floatings") and "floating" in query_lower:
                score += 0.5
        
        # Check for mDBC
        if "mdbc" in query_lower:
            features = metadata.get("features", "").lower()
            if "mdbc" in features:
                score += 1.0
        
        return min(5.0, max(1.0, score))

    def _score_execution(
        self,
        case_info: Dict[str, Any],
        query_lower: str,
        metadata: Dict[str, Any],
    ) -> float:
        """Score execution parameters compatibility (1-5)."""
        score = 3.0  # Default
        
        # Check if has execution block
        if case_info.get("has_execution"):
            score += 1.0
        
        # Execution params are generally transferable
        # unless specific requirements mentioned
        if any(kw in query_lower for kw in ["timeout", "timemax", "dt", "timestep"]):
            score += 0.5
        
        return min(5.0, max(1.0, score))

    def _default_rationale(self, reason: str) -> Dict[str, Any]:
        """Return default rationale for errors."""
        return {
            "algorithm_score": 1.0,
            "geometry_score": 1.0,
            "boundary_score": 1.0,
            "execution_score": 1.0,
            "aggregate": 1.0,
            "rationale": reason,
            "adjustments": ["Unable to score this example"],
        }


__all__ = ["ExampleScorer"]
