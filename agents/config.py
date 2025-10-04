"""Configuration loader for Planning Agent settings."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Literal

LOGGER = logging.getLogger(__name__)

# Default values for planning agent configuration
DEFAULT_ENABLED = False
DEFAULT_MODE = "two-requests"
DEFAULT_MAX_EXAMPLES = 12
DEFAULT_MAX_QUOTE_LENGTH = 400
DEFAULT_SCHEMA_VERSION = "1.0"

# Valid choices
VALID_MODES = {"two-requests", "single-request"}


@dataclass(frozen=True)
class PlanningAgentSettings:
    """Immutable settings for the Planning Agent pipeline."""

    enabled: bool
    mode: Literal["two-requests", "single-request"]
    max_examples: int
    max_quote_length: int
    schema_version: str

    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if self.mode not in VALID_MODES:
            raise ValueError(f"Invalid mode: {self.mode}. Must be one of {VALID_MODES}")
        if self.max_examples <= 0:
            raise ValueError(f"max_examples must be positive, got {self.max_examples}")
        if self.max_quote_length <= 0:
            raise ValueError(f"max_quote_length must be positive, got {self.max_quote_length}")


def _get_env_bool(name: str, default: bool) -> bool:
    """Get boolean value from environment variable."""
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


def _get_env_int(name: str, default: int, min_value: int = 1, max_value: int | None = None) -> int:
    """Get integer value from environment variable with validation."""
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        result = int(value)
        if result < min_value:
            LOGGER.warning(
                "Environment variable %s=%d is below minimum %d, using default %d",
                name,
                result,
                min_value,
                default,
            )
            return default
        if max_value is not None and result > max_value:
            LOGGER.warning(
                "Environment variable %s=%d exceeds maximum %d, using default %d",
                name,
                result,
                max_value,
                default,
            )
            return default
        return result
    except ValueError:
        LOGGER.warning(
            "Environment variable %s=%s is not a valid integer, using default %d",
            name,
            value,
            default,
        )
        return default


def _get_env_choice(name: str, default: str, choices: set[str]) -> str:
    """Get string value from environment variable with validation against choices."""
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    if value not in choices:
        LOGGER.warning(
            "Environment variable %s=%s is not a valid choice (must be one of %s), using default %s",
            name,
            value,
            choices,
            default,
        )
        return default
    return value


def load_planning_settings() -> PlanningAgentSettings:
    """
    Load Planning Agent settings from environment variables.

    Environment Variables:
        USE_RAG_PLANNING_AGENT: Enable planning agent (default: "0")
        PLANNING_AGENT_MODE: Execution mode "two-requests" or "single-request" (default: "two-requests")
        PLANNING_MAX_CURATED_EXAMPLES: Max number of curated examples (default: 12)
        PLANNING_MAX_QUOTE_LENGTH: Max length of quote text (default: 400)
        PLANNING_SCHEMA_VERSION: Schema version (default: "1.0")

    Returns:
        PlanningAgentSettings: Immutable settings object
    """
    enabled = _get_env_bool("USE_RAG_PLANNING_AGENT", DEFAULT_ENABLED)
    mode = _get_env_choice("PLANNING_AGENT_MODE", DEFAULT_MODE, VALID_MODES)
    max_examples = _get_env_int("PLANNING_MAX_CURATED_EXAMPLES", DEFAULT_MAX_EXAMPLES, min_value=1, max_value=20)
    max_quote_length = _get_env_int("PLANNING_MAX_QUOTE_LENGTH", DEFAULT_MAX_QUOTE_LENGTH, min_value=100, max_value=1000)
    schema_version = os.environ.get("PLANNING_SCHEMA_VERSION", DEFAULT_SCHEMA_VERSION).strip() or DEFAULT_SCHEMA_VERSION

    settings = PlanningAgentSettings(
        enabled=enabled,
        mode=mode,  # type: ignore[arg-type]
        max_examples=max_examples,
        max_quote_length=max_quote_length,
        schema_version=schema_version,
    )

    LOGGER.info(
        "Planning Agent settings loaded: enabled=%s, mode=%s, max_examples=%d, max_quote_length=%d, schema_version=%s",
        settings.enabled,
        settings.mode,
        settings.max_examples,
        settings.max_quote_length,
        settings.schema_version,
    )

    return settings


__all__ = ["PlanningAgentSettings", "load_planning_settings"]
