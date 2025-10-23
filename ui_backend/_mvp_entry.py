from __future__ import annotations

import os
import sys
from pathlib import Path as RealPath
from typing import Iterable


def _ensure_utf8() -> None:
    """Ensure stdout/stderr prefer UTF-8 on Windows consoles."""

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):  # pragma: no branch - attribute guard
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                continue


def _build_redirect_path(repo_root: RealPath, redirect_root: RealPath):
    """Return a patched Path callable that redirects logs/mvp writes."""

    redirect_root = redirect_root.resolve()
    redirect_root.mkdir(parents=True, exist_ok=True)
    base_abs = (repo_root / "logs" / "mvp").resolve()

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
                rel = path_obj.resolve().relative_to(base_abs)
                return redirect_root / rel
            except ValueError:
                pass

        return path_obj

    return patched_path


def _run(argv: list[str]) -> int:
    repo_root = RealPath(os.environ.get("MVP_REPO_ROOT", RealPath(__file__).resolve().parents[1]))
    redirect_env = os.environ.get("MVP_REDIRECT_ROOT")
    if redirect_env:
        redirect_root = RealPath(redirect_env)
    else:
        redirect_root = repo_root / "logs" / "mvp" / "_ui_backend_run"

    _ensure_utf8()

    sys.path.insert(0, str(repo_root))
    import scripts.mvp_direct_file_search as mvp_script

    patched_path = _build_redirect_path(repo_root, redirect_root)
    mvp_script.Path = patched_path  # type: ignore[attr-defined]

    original_argv = sys.argv
    try:
        sys.argv = [str(mvp_script.__file__ or "mvp_direct_file_search.py"), *argv]
        result = mvp_script.main()
        return int(result or 0)
    finally:
        sys.argv = original_argv


def main() -> int:
    return _run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())



