from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .models import ErrorInfo


@dataclass(frozen=True)
class _ErrorPattern:
    """Match rule for translating process output into friendly messaging."""

    token: str
    message: str
    hint: Optional[str] = None

    def matches(self, haystack: str) -> bool:
        return self.token.lower() in haystack.lower()


_ERROR_PATTERNS: Iterable[_ErrorPattern] = (
    _ErrorPattern(
        token="missing required environment variables",
        message="Required MVP environment variables are missing",
        hint="Ensure OPENAI_API_KEY and OPENAI_RAG_VS_DESIGN_ID are set before running.",
    ),
    _ErrorPattern(
        token="httpx",
        message="HTTP client reported an error during OpenAI request",
        hint="Check network connectivity and OpenAI service availability.",
    ),
    _ErrorPattern(
        token="openai",
        message="OpenAI API returned an error",
        hint="Review the logs for specific API response details.",
    ),
)


def interpret_process_failure(exit_code: int, combined_output: str) -> ErrorInfo:
    """Return a user-friendly error based on exit code and output."""

    normalized = combined_output.strip()
    for pattern in _ERROR_PATTERNS:
        if pattern.matches(normalized):
            return ErrorInfo(message=pattern.message, details=normalized, hint=pattern.hint)

    if exit_code == 0:
        return ErrorInfo(message="Process reported success", details=normalized)

    if exit_code < 0:
        return ErrorInfo(
            message="Process terminated by signal",
            details=normalized or f"Process exited with signal {-exit_code}",
            hint="Inspect system logs for the signal source.",
        )

    return ErrorInfo(
        message="MVP pipeline failed with an unknown error",
        details=normalized or f"Process exited with code {exit_code}",
        hint="Review the log output for clues or rerun with DEBUG logging.",
    )
