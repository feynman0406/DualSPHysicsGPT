"""Command-line interface for DualSPHysicsGPT."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from controller.loop import run_pipeline, review
from sessions.store import session_dir
from chains.generator import reload_use_rag as reload_generator_rag
from chains.fixer import reload_use_rag as reload_fixer_rag
from rag.retrievers import reset_cached_retrievers
from rag import retrievers as rag_ret

try:  # Prefer the authoritative list from the exec module.
    from tools.exec import DUALSPHYSICS_BINARIES
except Exception:  # pragma: no cover - fallback for import cycles during bootstrapping.
    DUALSPHYSICS_BINARIES = (
        "GenCase_win64.exe",
        "DualSPHysics5.4CPU_win64.exe",
        "DualSPHysics5.4_win64.exe",
        "BoundaryVTK_win64.exe",
        "PartVTK_win64.exe",
        "PartVTKOut_win64.exe",
        "MeasureTool_win64.exe",
        "ComputeForces_win64.exe",
        "IsoSurface_win64.exe",
        "FlowTool_win64.exe",
        "FloatingInfo_win64.exe",
        "TracerParts_win64.exe",
    )


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        reload_generator_rag()
        reload_fixer_rag()
        reset_cached_retrievers()
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

    reload_generator_rag()
    reload_fixer_rag()
    reset_cached_retrievers()


def apply_common_flags(args: argparse.Namespace) -> None:
    if getattr(args, "max_iters", None) is not None:
        os.environ["MAX_ITERS"] = str(args.max_iters)
    if getattr(args, "bin_dir", None):
        os.environ["DSPH_BIN_DIR"] = args.bin_dir
    if getattr(args, "workdir", None):
        os.environ["DSPH_WORKDIR"] = args.workdir
    if getattr(args, "use_existing_batch", None):
        os.environ["USE_EXISTING_BATCH"] = "1"
        os.environ["DSPH_BATCH_PATH"] = args.use_existing_batch
    if getattr(args, "direct_exec", False):
        os.environ["USE_DIRECT_EXEC"] = "1"
    gpu_flag = getattr(args, "gpu_flag", None)
    if gpu_flag is not None:
        os.environ["DSPH_USE_GPU"] = "1" if gpu_flag else "0"
    if getattr(args, "rag_index_dir", None):
        os.environ["IDX_DIR"] = args.rag_index_dir
    if getattr(args, "rag_top_k", None) is not None:
        os.environ["TOP_K"] = str(args.rag_top_k)
    if getattr(args, "rag_provider", None):
        os.environ["EMBEDDING_PROVIDER"] = args.rag_provider
    if getattr(args, "validate_only", False):
        os.environ["RUN_GENCASE"] = "1"
        os.environ["RUN_SOLVER"] = "0"
        os.environ["RUN_POST"] = "0"
    reset_cached_retrievers()


def cmd_run(args: argparse.Namespace) -> int:
    load_env(args.env)
    apply_common_flags(args)
    print(f"Starting run: {args.request}")
    result = run_pipeline(args.request)
    session_id = result.get("session_id", "<unknown>")
    status = result.get("status", "<unknown>")
    print(f"session: {session_id}")
    print(f"status: {status}")
    try:
        artifacts = session_dir(session_id)
        print(f"artifacts: {artifacts}")
        workdir_txt = artifacts / "workdir.txt"
        if workdir_txt.exists():
            workdir = workdir_txt.read_text(encoding="utf-8").strip()
            if workdir:
                print(f"workdir: {workdir}")
    except Exception:
        pass
    return 0 if status and not status.startswith("fail") else 2


def cmd_review(args: argparse.Namespace) -> int:
    load_env(args.env)
    apply_common_flags(args)
    result = review(args.session_id, args.decision, args.feedback)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _read_text(path: Path) -> str:
    if not path.exists():
        return "<missing>"
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        return f"<error reading {path}: {exc}>"


def cmd_show(args: argparse.Namespace) -> int:
    load_env(args.env)
    apply_common_flags(args)
    path = session_dir(args.session_id)
    print(f"session: {args.session_id}")
    print(f"path: {path}")
    print(f"request:\n{_read_text(path / 'request.txt')}")
    print(f"last_xml:\n{_read_text(path / 'last_xml.xml')}")
    print(f"diagnostics:\n{_read_text(path / 'diagnostics.txt')}")
    print(f"fix_plan:\n{_read_text(path / 'fix_plan.md')}")
    print(f"workdir:\n{_read_text(path / 'workdir.txt')}")
    print(f"history:\n{_read_text(path / 'history.json')}")
    return 0


def _print_doc(doc, show_content: bool, idx: int, *, max_chars: int | None = 500) -> None:
    try:
        meta = getattr(doc, "metadata", {}) or {}
        source = meta.get("source", "")
        corpus = meta.get("corpus", "")
        chunk = meta.get("chunk", None)
        total = meta.get("num_chunks", None)
        header = f"  [{idx}] source={source} corpus={corpus}"
        if chunk is not None and total is not None:
            header += f" chunk={chunk+1}/{total}"
        print(header)
        if show_content:
            content = (getattr(doc, "page_content", "") or "").strip()
            if max_chars is not None and len(content) > max_chars:
                preview = content[:max_chars] + "..."
            else:
                preview = content
            print("      " + preview.replace("\n", "\n      "))
    except Exception as exc:
        print(f"  [!] failed to render document: {exc}")


def cmd_rag(args: argparse.Namespace) -> int:
    """Probe retrievers with an ad-hoc query without running simulations."""
    load_env(args.env)
    apply_common_flags(args)

    which = (args.index or "both").lower()
    top_k = int(args.k or os.environ.get("TOP_K", "3"))
    show_content = bool(args.show_content)
    max_chars = None if args.full_content else 500

    def _run(name: str, get_retriever):
        try:
            retr = get_retriever(k=top_k)
        except Exception as exc:
            print(f"[!!] failed to initialise retriever '{name}': {exc}")
            return
        if not retr:
            print(f"[!!] retriever '{name}' not available (missing index or config)")
            return
        print(f"[OK] querying '{name}' (k={top_k})")
        try:
            docs = retr.get_relevant_documents(args.query)
        except Exception as exc:
            print(f"[!!] retrieval error for '{name}': {exc}")
            return
        if not docs:
            print(f"[--] no results for '{name}'")
            return
        for i, d in enumerate(docs, 1):
            _print_doc(d, show_content, i, max_chars=max_chars)

    if which in ("design", "both"):
        _run("design", rag_ret.design_retriever)
    if which in ("error", "both"):
        _run("error", rag_ret.error_retriever)
    return 0


def _detect_gpu() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return False, "nvidia-smi not found"
    except Exception as exc:  # pragma: no cover - defensive.
        return False, str(exc)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
        return False, msg or f"exit code {proc.returncode}"
    return True, (proc.stdout or "GPU detected").strip()


def cmd_check(args: argparse.Namespace) -> int:
    load_env(args.env)
    apply_common_flags(args)
    bin_dir_value = os.environ.get("DSPH_BIN_DIR")
    if not bin_dir_value:
        print("DSPH_BIN_DIR not set")
        return 1
    bin_dir = Path(bin_dir_value).expanduser()
    ok = True
    if not bin_dir.exists():
        print(f"[!!] Missing bin directory: {bin_dir}")
        ok = False
    else:
        missing = [exe for exe in DUALSPHYSICS_BINARIES if not (bin_dir / exe).exists()]
        if missing:
            ok = False
            print(f"[!!] Missing executables in {bin_dir}:")
            for exe in missing:
                print(f" - {exe}")
        else:
            print(f"[OK] Executables present in {bin_dir}")
    gpu_requested = os.environ.get("DSPH_USE_GPU") == "1"
    has_gpu, gpu_msg = _detect_gpu()
    summary = gpu_msg.splitlines()[0] if gpu_msg else gpu_msg
    if gpu_requested:
        if has_gpu:
            print(f"[OK] GPU ready: {summary}")
        else:
            print(f"[!!] GPU requested but unavailable: {summary}")
            ok = False
    else:
        tag = "[OK]" if has_gpu else "[info]"
        print(f"{tag} GPU check: {summary}")
    return 0 if ok else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dsph", description="DualSPHysicsGPT CLI")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env", default=".env", help="Path to environment file (default: .env)")
    common.add_argument("--max-iters", type=int, dest="max_iters", help="Override MAX_ITERS for the controller loop")
    common.add_argument("--gpu", dest="gpu_flag", action="store_const", const=True, help="Run with GPU binaries (DSPH_USE_GPU=1)")
    common.add_argument("--cpu", dest="gpu_flag", action="store_const", const=False, help="Force CPU mode (DSPH_USE_GPU=0)")
    common.add_argument("--bin", dest="bin_dir", help="Override DSPH_BIN_DIR")
    common.add_argument("--workdir", dest="workdir", help="Override DSPH_WORKDIR for new runs")
    common.add_argument("--use-existing-batch", dest="use_existing_batch", help="Execute an existing batch file (.bat path)")
    common.add_argument("--direct-exec", dest="direct_exec", action="store_true", help="Invoke binaries directly instead of headless batch")
    common.add_argument("--validate-only", dest="validate_only", action="store_true", help="Run GenCase only (skip solver/post)")
    common.add_argument("--rag-index-dir", dest="rag_index_dir", help="Override retrieval index directory (IDX_DIR)")
    common.add_argument("--rag-top-k", dest="rag_top_k", type=int, help="Set retrieval top-k value (TOP_K)")
    common.add_argument("--rag-provider", dest="rag_provider", help="Override embedding provider (EMBEDDING_PROVIDER)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", parents=[common], help="Run a new simulation request")
    p_run.add_argument("request", help="User request text")
    p_run.set_defaults(func=cmd_run)

    p_review = sub.add_parser("review", parents=[common], help="Submit review decision")
    p_review.add_argument("session_id", help="Session identifier")
    p_review.add_argument("decision", choices=["accept", "reject"], help="Decision outcome")
    p_review.add_argument("--feedback", default=None, help="Optional feedback when rejecting")
    p_review.set_defaults(func=cmd_review)

    p_show = sub.add_parser("show", parents=[common], help="Show session artifacts")
    p_show.add_argument("session_id", help="Session identifier")
    p_show.set_defaults(func=cmd_show)

    p_check = sub.add_parser("check", parents=[common], help="Validate binary configuration")
    p_check.set_defaults(func=cmd_check)

    p_rag = sub.add_parser("rag", parents=[common], help="Query RAG indexes without running simulations")
    p_rag.add_argument("--query", required=True, help="Query text to search for relevant documents")
    p_rag.add_argument("--index", choices=["design", "error", "both"], default="both", help="Which retriever to query")
    p_rag.add_argument("--k", type=int, default=None, help="Top-K to retrieve (defaults to TOP_K or 3)")
    p_rag.add_argument("--show-content", action="store_true", help="Print content for each retrieved document")
    p_rag.add_argument("--full-content", action="store_true", help="Show entire content instead of 500-char preview")
    p_rag.set_defaults(func=cmd_rag)

    return parser


def main(argv: Any = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())









