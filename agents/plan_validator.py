"""Plan JSON validator with structured error reporting."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, NamedTuple, Sequence

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    Draft7Validator = None  # type: ignore[assignment,misc]

from agents.config import PlanningAgentSettings

LOGGER = logging.getLogger(__name__)


class ValidationIssue(NamedTuple):
    """Structured validation issue."""

    path: Sequence[str | int]
    message: str
    code: str
    severity: str = "error"
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": list(self.path),
            "message": self.message,
            "code": self.code,
            "severity": self.severity,
            "hint": self.hint,
        }

    def __str__(self) -> str:
        """Format issue as human-readable string."""
        path_str = ".".join(str(p) for p in self.path) if self.path else "root"
        base = f"[{self.severity.upper()}] {path_str}: {self.message} (code: {self.code})"
        if self.hint:
            base += f"\n  Hint: {self.hint}"
        return base


class ValidationResult(NamedTuple):
    """Result of validation with issues."""

    valid: bool
    issues: list[ValidationIssue]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@lru_cache(maxsize=1)
def load_plan_schema() -> dict[str, Any]:
    """Load and cache the Plan JSON schema."""
    schema_path = Path(__file__).parent.parent / "schemas" / "planning_agent_schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Plan schema not found at {schema_path}")
    
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _jsonschema_error_to_issue(error: Any) -> ValidationIssue:
    """Convert jsonschema validation error to ValidationIssue."""
    path = list(error.absolute_path) if hasattr(error, "absolute_path") else []
    message = error.message if hasattr(error, "message") else str(error)
    
    # Try to extract a more specific code from the error
    code = "schema-violation"
    if hasattr(error, "validator"):
        code = f"schema-{error.validator}"
    
    return ValidationIssue(
        path=path,
        message=message,
        code=code,
        severity="error",
        hint="Check the schema requirements for this field",
    )


def _validate_against_schema(plan: Mapping[str, Any]) -> list[ValidationIssue]:
    """Validate plan against JSON Schema."""
    if jsonschema is None or Draft7Validator is None:
        LOGGER.warning("jsonschema not installed, skipping schema validation")
        return []
    
    issues: list[ValidationIssue] = []
    schema = load_plan_schema()
    
    validator = Draft7Validator(schema)
    for error in validator.iter_errors(plan):
        issues.append(_jsonschema_error_to_issue(error))
    
    return issues


def _validate_custom_rules(plan: Mapping[str, Any], settings: PlanningAgentSettings) -> list[ValidationIssue]:
    """Apply custom validation rules beyond JSON Schema."""
    issues: list[ValidationIssue] = []
    
    # Check curated_examples quote lengths
    curated = plan.get("curated_examples", [])
    if not isinstance(curated, list):
        return issues
    
    for i, example in enumerate(curated):
        if not isinstance(example, dict):
            continue
        
        spans = example.get("spans", [])
        if not isinstance(spans, list):
            continue
        
        # Check span count per example
        if len(spans) > 6:
            issues.append(
                ValidationIssue(
                    path=["curated_examples", i, "spans"],
                    message=f"Too many spans ({len(spans)}), maximum is 6",
                    code="too-many-spans",
                    severity="error",
                    hint="Reduce the number of quote spans or split into multiple examples",
                )
            )
        
        for j, span in enumerate(spans):
            if not isinstance(span, dict):
                continue
            
            quote = span.get("quote", "")
            if not isinstance(quote, str):
                continue
            
            # Check quote length against settings
            if len(quote) > settings.max_quote_length:
                issues.append(
                    ValidationIssue(
                        path=["curated_examples", i, "spans", j, "quote"],
                        message=f"Quote too long ({len(quote)} chars), max is {settings.max_quote_length}",
                        code="quote-too-long",
                        severity="error",
                        hint=f"Truncate quote or adjust PLANNING_MAX_QUOTE_LENGTH (current: {settings.max_quote_length})",
                    )
                )
        
        # Check filename uniqueness recommendation (warning only)
        filename = example.get("filename")
        if filename:
            same_file_count = sum(
                1 for ex in curated 
                if isinstance(ex, dict) and ex.get("filename") == filename
            )
            if same_file_count > 3:
                issues.append(
                    ValidationIssue(
                        path=["curated_examples", i, "filename"],
                        message=f"Filename '{filename}' appears {same_file_count} times (>3)",
                        code="low-diversity",
                        severity="warning",
                        hint="Consider using examples from different files for better coverage",
                    )
                )
    
    # Check total curated_examples count
    if len(curated) > settings.max_examples:
        issues.append(
            ValidationIssue(
                path=["curated_examples"],
                message=f"Too many examples ({len(curated)}), max is {settings.max_examples}",
                code="too-many-examples",
                severity="error",
                hint=f"Reduce examples or adjust PLANNING_MAX_CURATED_EXAMPLES (current: {settings.max_examples})",
            )
        )
    
    # Check schema_guidance for TODO placeholder
    schema_guidance = plan.get("schema_guidance", "")
    if isinstance(schema_guidance, str):
        if "<<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>>" not in schema_guidance and len(schema_guidance) < 50:
            issues.append(
                ValidationIssue(
                    path=["schema_guidance"],
                    message="schema_guidance appears incomplete or missing TODO placeholder",
                    code="incomplete-guidance",
                    severity="warning",
                    hint="Include <<SCHEMA_GUIDANCE_TODO_BY_SCHEMA_AGENT>> placeholder with structured TODO sections",
                )
            )
    
    # Check for required fields mentioned in spec
    required_fields = ["query", "curated_examples", "schema_guidance"]
    for field in required_fields:
        if field not in plan:
            issues.append(
                ValidationIssue(
                    path=[field],
                    message=f"Required field '{field}' is missing",
                    code="missing-required",
                    severity="error",
                    hint="Ensure all required fields are present in the plan",
                )
            )
    
    return issues


def validate_plan_json(
    plan: Mapping[str, Any],
    settings: PlanningAgentSettings | None = None,
) -> ValidationResult:
    """
    Validate a Plan JSON against schema and custom rules.
    
    Args:
        plan: The plan dictionary to validate
        settings: Planning agent settings (loads defaults if None)
    
    Returns:
        ValidationResult with valid flag and list of issues
    """
    if settings is None:
        from agents.config import load_planning_settings
        settings = load_planning_settings()
    
    issues: list[ValidationIssue] = []
    
    # Validate against JSON Schema
    schema_issues = _validate_against_schema(plan)
    issues.extend(schema_issues)
    
    # Apply custom rules
    custom_issues = _validate_custom_rules(plan, settings)
    issues.extend(custom_issues)
    
    # Deduplicate issues by (path, code)
    seen: set[tuple[tuple[str | int, ...], str]] = set()
    unique_issues: list[ValidationIssue] = []
    for issue in issues:
        key = (tuple(issue.path), issue.code)
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)
    
    # Sort issues: errors first, then by path
    def sort_key(issue: ValidationIssue) -> tuple[int, str]:
        severity_order = {"error": 0, "warning": 1, "info": 2}
        path_str = ".".join(str(p) for p in issue.path)
        return (severity_order.get(issue.severity, 3), path_str)
    
    unique_issues.sort(key=sort_key)
    
    # Valid only if no errors
    has_errors = any(issue.severity == "error" for issue in unique_issues)
    valid = not has_errors
    
    return ValidationResult(valid=valid, issues=unique_issues)


__all__ = ["ValidationIssue", "ValidationResult", "validate_plan_json", "load_plan_schema"]
