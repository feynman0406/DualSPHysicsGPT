"""Quote extraction utilities for Planning Agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

LOGGER = logging.getLogger(__name__)


class QuoteExtractor:
    """Extracts relevant quotes from JSON/XML files for Plan JSON."""

    def __init__(self, max_quote_length: int = 400, max_quotes_per_file: int = 3):
        """
        Initialize quote extractor.

        Args:
            max_quote_length: Maximum length of each quote
            max_quotes_per_file: Maximum number of quotes per file
        """
        self.max_quote_length = max_quote_length
        self.max_quotes_per_file = max_quotes_per_file

    def extract_quotes(
        self,
        file_path: Path,
        user_query: str,
        score_rationale: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract relevant quotes from a file.

        Args:
            file_path: Path to the file
            user_query: User's query
            score_rationale: Scoring rationale with adjustments

        Returns:
            List of quote dictionaries with keys: quote, start, end
        """
        try:
            if file_path.suffix.lower() == ".json":
                return self._extract_from_json(file_path, user_query, score_rationale)
            elif file_path.suffix.lower() == ".xml":
                return self._extract_from_xml(file_path, user_query, score_rationale)
            else:
                LOGGER.warning(f"Unsupported file type for quote extraction: {file_path}")
                return []
        except Exception as exc:
            LOGGER.error(f"Failed to extract quotes from {file_path}: {exc}")
            return []

    def _extract_from_json(
        self,
        path: Path,
        user_query: str,
        score_rationale: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Extract quotes from JSON file."""
        with path.open("r", encoding="utf-8") as f:
            content = f.read()
        
        data = json.loads(content)
        quotes = []
        
        # Extract key sections based on score rationale
        adjustments = score_rationale.get("adjustments", [])
        
        # Priority sections based on what needs adjustment
        sections_to_extract = self._identify_priority_sections(data, adjustments, user_query)
        
        for section_path, section_data in sections_to_extract[:self.max_quotes_per_file]:
            quote_text = json.dumps(section_data, indent=2, ensure_ascii=False)
            
            # Truncate if too long
            if len(quote_text) > self.max_quote_length:
                quote_text = quote_text[:self.max_quote_length - 3] + "..."
            
            # Find position in original content (approximate)
            start_pos = content.find(quote_text[:50]) if len(quote_text) >= 50 else -1
            end_pos = start_pos + len(quote_text) if start_pos >= 0 else -1
            
            quotes.append({
                "quote": quote_text,
                "start": start_pos if start_pos >= 0 else None,
                "end": end_pos if end_pos >= 0 else None,
            })
        
        return quotes

    def _extract_from_xml(
        self,
        path: Path,
        user_query: str,
        score_rationale: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Extract quotes from XML file."""
        with path.open("r", encoding="utf-8") as f:
            content = f.read()
        
        quotes = []
        
        # Extract key XML sections
        # For simplicity, extract based on common tags
        sections_to_find = self._identify_xml_tags_to_extract(user_query, score_rationale)
        
        for tag in sections_to_find[:self.max_quotes_per_file]:
            # Find tag in content
            start_tag = f"<{tag}"
            end_tag = f"</{tag}>"
            
            start_idx = content.find(start_tag)
            if start_idx < 0:
                continue
            
            # Find the matching end tag (simplified - doesn't handle nesting)
            end_idx = content.find(end_tag, start_idx)
            if end_idx < 0:
                continue
            
            end_idx += len(end_tag)
            quote_text = content[start_idx:end_idx]
            
            # Truncate if too long
            if len(quote_text) > self.max_quote_length:
                quote_text = quote_text[:self.max_quote_length - 3] + "..."
                end_idx = start_idx + len(quote_text)
            
            quotes.append({
                "quote": quote_text,
                "start": start_idx,
                "end": end_idx,
            })
        
        return quotes

    def _identify_priority_sections(
        self,
        data: Dict[str, Any],
        adjustments: List[str],
        user_query: str,
    ) -> List[tuple[str, Any]]:
        """Identify priority sections to extract from JSON."""
        sections = []
        query_lower = user_query.lower()
        
        # Navigate to case if exists
        case_data = data.get("case", data)
        
        # Priority 1: Geometry (if mentioned in adjustments or query)
        if any("geometry" in adj.lower() for adj in adjustments) or "geometry" in query_lower:
            if "geometry" in case_data:
                sections.append(("geometry", case_data["geometry"]))
        
        # Priority 2: Execution parameters
        if any("execution" in adj.lower() for adj in adjustments) or "execution" in query_lower:
            if "execution" in case_data:
                sections.append(("execution", case_data["execution"]))
        
        # Priority 3: Properties/Boundaries
        if any("boundary" in adj.lower() or "property" in adj.lower() for adj in adjustments):
            if "properties" in case_data:
                sections.append(("properties", case_data["properties"]))
        
        # Priority 4: Floatings (if relevant)
        if "floating" in query_lower:
            if "floatings" in case_data:
                sections.append(("floatings", case_data["floatings"]))
        
        # Priority 5: Commands (general fallback)
        if "commands" in case_data and not sections:
            sections.append(("commands", case_data["commands"]))
        
        return sections

    def _identify_xml_tags_to_extract(
        self,
        user_query: str,
        score_rationale: Dict[str, Any],
    ) -> List[str]:
        """Identify XML tags to extract based on query and scoring."""
        tags = []
        query_lower = user_query.lower()
        adjustments = score_rationale.get("adjustments", [])
        
        # Common important tags in DualSPHysics XML
        if any("geometry" in adj.lower() for adj in adjustments) or "geometry" in query_lower:
            tags.extend(["geometry", "mainlist", "commands"])
        
        if any("execution" in adj.lower() for adj in adjustments) or "execution" in query_lower:
            tags.extend(["execution", "parameters", "special"])
        
        if any("boundary" in adj.lower() for adj in adjustments):
            tags.extend(["properties", "links"])
        
        if "floating" in query_lower:
            tags.append("floatings")
        
        # Default important tags
        if not tags:
            tags = ["execution", "geometry", "properties"]
        
        return tags


__all__ = ["QuoteExtractor"]
