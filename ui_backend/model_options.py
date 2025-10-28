"""Shared model configuration for UI-triggered MVP runs."""

from __future__ import annotations

from typing import Iterable

# Allowed GPT models exposed to the UI for per-run selection.
ALLOWED_MODELS: tuple[str, ...] = (
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-5",
)

# Default model the UI should preselect when no explicit choice is made.
DEFAULT_MODEL: str = ALLOWED_MODELS[0]


def is_supported(model_name: str | None) -> bool:
    """Return True when the provided model is in the allow-list."""

    if not model_name:
        return False
    normalized = model_name.strip()
    return normalized in ALLOWED_MODELS


def coerce_model(model_name: str | None, *, fallback: str | None = None) -> str | None:
    """Return a valid model name or fallback when unsupported."""

    if model_name and is_supported(model_name):
        return model_name.strip()
    return fallback


def choices() -> Iterable[str]:
    """Expose available models for other modules (e.g. docs/tests)."""

    return ALLOWED_MODELS
