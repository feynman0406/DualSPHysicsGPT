"""Schema Agent - Stage 2 of two-stage pipeline."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agents.logging_utils import log_stage

LOGGER = logging.getLogger(__name__)


class SchemaAgent:
    """Schema Agent for generating strict JSON from Plan JSON."""

    def __init__(self, config_library_path: Optional[Path] = None):
        """Initialize Schema Agent."""
        self.config_library = config_library_path or Path("AutoXml_script/config_library")

    def run_schema_agent(
        self,
        plan_json: Dict[str, Any],
        user_query: str,
        schema: Dict[str, Any],
        llm_client: Any,
        model: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Generate config JSON from Plan JSON using strict JSON schema.

        Args:
            plan_json: Plan JSON from Planning Agent
            user_query: Original user query
            schema: DualSPHysics config schema
            llm_client: LLM client instance
            model: Model name to use
            temperature: Temperature for generation

        Returns:
            Generated config JSON
        """
        reference_context = self._prepare_reference_context(plan_json)
        log_stage(
            "SCHEMA_AGENT_START",
            {
                "plan_examples": len(plan_json.get("curated_examples", [])),
                "primary_reference": reference_context.get("filename"),
            },
        )

        try:
            # Build prompt from Plan JSON and reference template
            prompt = self._build_prompt(plan_json, user_query, reference_context)

            # Call LLM with strict JSON schema
            config_json = self._generate_with_strict_schema(
                prompt=prompt,
                schema=schema,
                llm_client=llm_client,
                model=model,
                temperature=temperature,
            )

            log_stage("SCHEMA_AGENT_COMPLETE", {"config_keys": len(config_json.keys())})

            return config_json

        except Exception as exc:
            LOGGER.error(f"Schema Agent failed: {exc}", exc_info=True)
            raise

    def _prepare_reference_context(self, plan_json: Dict[str, Any]) -> Dict[str, Any]:
        """Load the primary reference template and apply overrides."""
        context: Dict[str, Any] = {}
        curated = plan_json.get("curated_examples") or []
        if not curated:
            return context

        filename = curated[0].get("filename")
        if not filename:
            return context

        file_path = self.config_library / Path(filename).name
        if not file_path.exists():
            LOGGER.warning(f"Primary reference not found in config library: {file_path}")
            return context

        try:
            with file_path.open("r", encoding="utf-8") as f:
                template = json.load(f)
        except Exception as exc:
            LOGGER.warning(f"Failed to load primary reference {file_path}: {exc}")
            return context

        extracted_params = plan_json.get("extracted_params", [])
        draft_config, applied = self._apply_overrides(template, extracted_params)

        context.update(
            {
                "filename": Path(filename).name,
                "file_path": str(file_path),
                "template": template,
                "draft_config": draft_config,
                "applied_overrides": applied,
            }
        )
        return context

    def _apply_overrides(
        self,
        template: Dict[str, Any],
        extracted_params: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Apply extracted parameter overrides onto the template (non-destructive)."""
        draft = deepcopy(template)
        applied: List[str] = []

        for param in extracted_params:
            name = param.get("name")
            if not name:
                continue
            value = param.get("value")
            path_tokens = name.split(".")
            if self._set_nested_value(draft, ["case", *path_tokens], value):
                applied.append(name)
            elif self._set_nested_value(draft, path_tokens, value):
                applied.append(name)

        return draft, applied

    def _set_nested_value(self, data: Any, path: List[str], value: Any) -> bool:
        """Set a nested value if the path exists; returns True when applied."""
        current = data
        for key in path[:-1]:
            if isinstance(current, dict) and key in current:
                current = current[key]
                continue
            if isinstance(current, list):
                try:
                    index = int(key)
                except (TypeError, ValueError):
                    return False
                if index < 0 or index >= len(current):
                    return False
                current = current[index]
                continue
            return False

        last_key = path[-1]
        if isinstance(current, dict) and last_key in current:
            current[last_key] = value
            return True
        if isinstance(current, list):
            try:
                index = int(last_key)
            except (TypeError, ValueError):
                return False
            if 0 <= index < len(current):
                current[index] = value
                return True
        return False

    def _build_prompt(
        self,
        plan_json: Dict[str, Any],
        user_query: str,
        reference_context: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Build prompt messages from Plan JSON and reference context."""
        system_content = self._build_system_prompt()
        user_content = self._build_user_prompt(plan_json, user_query, reference_context)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        return messages

    def _build_system_prompt(self) -> str:
        """Build system prompt for Schema Agent."""
        return """You are a Schema Agent that generates DualSPHysics configuration JSON strictly following a provided JSON schema.

Your task:
1. Read the Plan JSON which contains curated examples, extracted parameters, and guidance
2. Use the evidence from Plan JSON to fill the required JSON schema
3. Follow the schema_guidance for handling missing fields
4. Output ONLY valid JSON that strictly conforms to the schema

Rules:
- Start from the provided Draft Config baseline and keep geometry/algorithm structure intact unless schema_guidance explicitly requires changes
- Use extracted_params as primary source of values
- Reference curated_examples for structure and patterns
- Follow schema_guidance for missing parameter strategies
- Maintain unit and dimension consistency
- Do not include extra keys not in schema
- Do not include any text outside the JSON
- If a parameter is missing and no guidance exists, use conservative defaults"""

    def _build_user_prompt(
        self,
        plan_json: Dict[str, Any],
        user_query: str,
        reference_context: Dict[str, Any],
    ) -> str:
        """Build user prompt from Plan JSON and reference context."""
        lines = [
            "# Task",
            "Generate a DualSPHysics configuration JSON based on the following Plan JSON, user requirements, and the provided reference baseline.",
            "",
            "# User Requirements",
            user_query,
            "",
            "# Plan JSON",
            json.dumps(plan_json, indent=2, ensure_ascii=False),
        ]

        if reference_context:
            lines.extend([
                "",
                "# Primary Reference",
                f"Filename: {reference_context.get('filename', 'unknown')}",
            ])
            if reference_context.get("applied_overrides"):
                overrides = ", ".join(reference_context["applied_overrides"][:12])
                lines.append(f"Applied overrides: {overrides}")

        if reference_context.get("draft_config") is not None:
            lines.extend([
                "",
                "# Draft Config (clone of primary reference with applied overrides)",
                json.dumps(reference_context["draft_config"], indent=2, ensure_ascii=False),
            ])

        lines.extend([
            "",
            "# Instructions",
            "1. Start from the Draft Config and keep existing structure/order unless schema_guidance mandates changes",
            "2. Apply extracted_params for parameter values and reconcile with user requirements",
            "3. Follow schema_guidance for missing fields",
            "4. Resolve any conflicts noted in the Plan with minimal structural edits",
            "5. Ensure all required schema fields are present",
            "6. Maintain consistency in units and dimensions",
            "7. Output only the finalized JSON that conforms to the strict schema",
            "",
            "Generate the configuration JSON now:",
        ])

        return "\n".join(lines)

    def _generate_with_strict_schema(
        self,
        prompt: List[Dict[str, str]],
        schema: Dict[str, Any],
        llm_client: Any,
        model: str,
        temperature: float,
    ) -> Dict[str, Any]:
        """Generate JSON with strict schema enforcement."""
        try:
            # Use the LLM client's JSON schema generation
            # This assumes the client has a method for strict JSON generation
            response = llm_client.chat.completions.create(
                model=model,
                messages=prompt,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "dualsphysics_config",
                        "strict": True,
                        "schema": schema,
                    },
                },
                temperature=temperature,
            )

            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("LLM returned empty content")

            config_json = json.loads(content)
            return config_json

        except json.JSONDecodeError as exc:
            LOGGER.error(f"Failed to parse LLM response as JSON: {exc}")
            raise
        except Exception as exc:
            LOGGER.error(f"LLM generation failed: {exc}")
            raise


def run_schema_agent(
    plan_json: Dict[str, Any],
    user_query: str,
    schema: Dict[str, Any],
    llm_client: Any,
    model: str,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """
    Convenience function to run Schema Agent.

    Args:
        plan_json: Plan JSON from Planning Agent
        user_query: Original user query
        schema: DualSPHysics config schema
        llm_client: LLM client instance
        model: Model name
        temperature: Temperature for generation

    Returns:
        Generated config JSON
    """
    agent = SchemaAgent()
    return agent.run_schema_agent(plan_json, user_query, schema, llm_client, model, temperature)


__all__ = ["SchemaAgent", "run_schema_agent"]
