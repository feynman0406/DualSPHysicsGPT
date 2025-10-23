#!/usr/bin/env python3
"""Helper to capture MVP pipeline output under logs/mvp/reference_run.

This wrapper preserves read-only areas by redirecting any Path("logs/mvp" ...)
invocations inside scripts.mvp_direct_file_search to the writable
logs/mvp/reference_run/ tree and records console output to mvp_run.log.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path as RealPath
from typing import Callable, Iterable, Tuple


def _ensure_utf8() -> None:
    """Ensure stdout/stderr prefer UTF-8 on Windows consoles."""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        # Some wrapped streams (e.g., when already redirected) do not support reconfigure.
        pass


def _build_redirect_path(repo_root: RealPath) -> Tuple[Callable[..., RealPath], RealPath]:
    """Return a patched Path callable and the redirect root directory."""

    redirect_root = (repo_root / "logs" / "mvp" / "reference_run").resolve()
    redirect_root.mkdir(parents=True, exist_ok=True)
    base_abs = (repo_root / "logs" / "mvp").resolve()

    # Common relative spellings observed across the MVP script and potential callers.
    relative_bases: Iterable[RealPath] = (
        RealPath("logs") / "mvp",
        RealPath("logs/mvp"),
        RealPath("logs\\mvp"),
    )

    def patched_path(*args, **kwargs):
        path_obj = RealPath(*args, **kwargs)

        for base in relative_bases:
            try:
                rel = path_obj.relative_to(base)
                return redirect_root / rel
            except ValueError:
                continue

        if path_obj.is_absolute():
            try:
                rel = path_obj.relative_to(base_abs)
                return redirect_root / rel
            except ValueError:
                pass

        return path_obj

    return patched_path, redirect_root


class _TeeStream:
    """Minimal tee stream that mirrors writes to a log file."""

    def __init__(self, stream, log_handle):
        self._stream = stream
        self._log = log_handle
        self.encoding = getattr(stream, "encoding", "utf-8")

    def write(self, data):
        self._stream.write(data)
        self._log.write(data)

    def flush(self):
        self._stream.flush()
        self._log.flush()

    def isatty(self):
        return self._stream.isatty()

    def fileno(self):
        return self._stream.fileno()

    def __getattr__(self, name):  # pragma: no cover - defer to underlying stream
        return getattr(self._stream, name)


def main() -> int:
    repo_root = RealPath(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

    _ensure_utf8()

    patched_path, redirect_root = _build_redirect_path(repo_root)
    log_path = redirect_root / "mvp_run.log"

    import scripts.mvp_direct_file_search as mvp_script  # noqa: WPS433 (runtime import)

    # Substitute the module-level Path reference after import.
    mvp_script.Path = patched_path  # type: ignore[attr-defined]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_handle:
        original_stdout, original_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout = _TeeStream(original_stdout, log_handle)
            sys.stderr = _TeeStream(original_stderr, log_handle)
            return mvp_script.main()
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            sys.stdout, sys.stderr = original_stdout, original_stderr


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
