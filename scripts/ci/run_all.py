#!/usr/bin/env python3
"""Unified CI entry point for DualSPHysics UI stack."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_APP_DIR = REPO_ROOT / "ui" / "app"
NPM_EXECUTABLE = "npm.cmd" if os.name == "nt" else "npm"


class StepFailed(RuntimeError):
    """Raised when a CI step fails."""


def _format_cmd(cmd: Sequence[str]) -> str:
    return " ".join(cmd)


def run_step(name: str, cmd: Sequence[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run a command and raise if it fails."""

    print(f"\n=== {name} ===")
    print(f"$ {_format_cmd(cmd)}")
    sys.stdout.flush()
    completed = subprocess.run(cmd, cwd=cwd, env=env, shell=False)
    if completed.returncode != 0:
        raise StepFailed(f"{name} failed with exit code {completed.returncode}")


def ensure_commands(names: Iterable[str]) -> None:
    for name in names:
        if shutil.which(name) is None:
            raise StepFailed(f"Required command '{name}' is not available on PATH")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all UI pipeline quality checks")
    parser.add_argument("--skip-mvp", action="store_true", help="Skip MVP smoke test (requires OPENAI credentials)")
    parser.add_argument("--skip-backend", action="store_true", help="Skip Python backend tests")
    parser.add_argument("--skip-ruff", action="store_true", help="Skip Ruff lint step")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip all frontend lint/build/test steps")
    parser.add_argument("--npm-ci", action="store_true", help="Run npm ci before frontend tasks")
    parser.add_argument("--mvp-runner", default=str(REPO_ROOT / "docs" / "ui_integration" / "mvp_reference_runner.py"), help="Path to MVP runner script")
    args = parser.parse_args()

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")

    try:
        if not args.skip_mvp:
            missing = [var for var in ("OPENAI_API_KEY", "OPENAI_RAG_VS_DESIGN_ID") if not env.get(var)]
            if missing:
                raise StepFailed(
                    "Missing required environment variables for MVP smoke test: " + ", ".join(missing) +
                    ". Set them or re-run with --skip-mvp."
                )

            run_step(
                "MVP smoke test",
                [sys.executable, args.mvp_runner],
                cwd=REPO_ROOT,
                env=env,
            )

        if not args.skip_backend:
            run_step(
                "UI backend tests",
                [sys.executable, "-m", "pytest", "tests/ui_backend", "-q"],
                cwd=REPO_ROOT,
                env=env,
            )

        if not args.skip_ruff:
            ensure_commands(["ruff"])
            run_step(
                "UI backend lint (ruff)",
                ["ruff", "check", "ui_backend", "tests/ui_backend"],
                cwd=REPO_ROOT,
                env=env,
            )

        if not args.skip_frontend:
            ensure_commands([NPM_EXECUTABLE])
            if args.npm_ci:
                run_step("npm ci", [NPM_EXECUTABLE, "ci"], cwd=UI_APP_DIR, env=env)

            run_step("Frontend lint", [NPM_EXECUTABLE, "run", "lint"], cwd=UI_APP_DIR, env=env)
            run_step("Frontend format check", [NPM_EXECUTABLE, "run", "format"], cwd=UI_APP_DIR, env=env)
            run_step("Frontend build", [NPM_EXECUTABLE, "run", "build"], cwd=UI_APP_DIR, env=env)
            run_step("Frontend tests", [NPM_EXECUTABLE, "run", "test"], cwd=UI_APP_DIR, env=env)

    except StepFailed as exc:
        print(f"\nERROR: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        print(f"\nERROR: Command {exc.cmd} failed with exit code {exc.returncode}")
        return exc.returncode

    print("\nAll steps completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





