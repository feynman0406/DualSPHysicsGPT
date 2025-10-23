#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${LOG_DIR:-logs/ui_regression}"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
LOG_FILE="$LOG_DIR/full_regression_${TIMESTAMP}.log"

echo "[run_full_regression] writing log to $LOG_FILE"

SKIP_MVP=0
EXTRA_ARGS=()

while (($# > 0)); do
  case "$1" in
    --skip-mvp)
      SKIP_MVP=1
      shift
      ;;
    --help|-h)
      cat <<'USAGE'
Usage: scripts/run_full_regression.sh [--skip-mvp]

Runs the canonical governance regression suite:
  1. MVP smoke run via docs/ui_integration/mvp_reference_runner.py
  2. Backend pytest suite (tests/ui_backend)
  3. Frontend lint/build/test commands scoped to ui/app

Outputs are tee'd into $LOG_FILE and the script exits on the first failure.
Use --skip-mvp when OpenAI credentials are unavailable.
USAGE
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

run() {
  local label="$1"
  shift
  printf '\n=== %s ===\n' "$label" | tee -a "$LOG_FILE"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}

if [[ $SKIP_MVP -eq 0 ]]; then
  if [[ -z "${OPENAI_API_KEY:-}" || -z "${OPENAI_RAG_VS_DESIGN_ID:-}" ]]; then
    echo "Missing OPENAI_API_KEY or OPENAI_RAG_VS_DESIGN_ID; rerun with credentials or pass --skip-mvp" | tee -a "$LOG_FILE"
    exit 1
  fi
  run "MVP smoke" python docs/ui_integration/mvp_reference_runner.py "${EXTRA_ARGS[@]}"
else
  echo "--skip-mvp enabled; skipping MVP smoke run" | tee -a "$LOG_FILE"
fi

run "Backend pytest" python -m pytest tests/ui_backend -q
run "Backend lint (ruff)" ruff check ui_backend tests/ui_backend
run "Frontend lint" npm --prefix ui/app run lint
run "Frontend build" npm --prefix ui/app run build
run "Frontend tests" npm --prefix ui/app run test

printf '\nAll regression steps completed\n' | tee -a "$LOG_FILE"
