# UI Contribution Checklist

Every UI-focused pull request must complete the following steps before review. Copy this checklist
into the PR description and tick each item as you finish it.

1. **Baseline protection**
   - [ ] Confirm no files listed in `docs/ui_integration/baseline_manifest.md` were modified.
   - [ ] Ensure MVP directories (eg `AutoXml_script/`, `prompts/`, `rag/`) remain untouched.
2. **Change manifest & documentation**
   - [ ] Update `docs/ui_integration/progress_log.md` with the phase, rationale, and governance notes.
   - [ ] Record new work items or decisions in `docs/ui_integration/backlog.md` or related governance docs.
3. **Code quality gates**
   - [ ] Run `scripts/run_full_regression.sh` (or `.bat` on Windows) and ensure it exits successfully.
   - [ ] For Python-only changes: run `python -m pytest tests/ui_backend -q` and `ruff check ui_backend tests/ui_backend` as spot verification.
   - [ ] For frontend changes: run `npm run lint`, `npm run build`, and `npm run test`.
   - [ ] Capture command outputs (or summaries) in the PR discussion for reviewer reference.
4. **Configuration & secrets hygiene**
   - [ ] Confirm no secrets, tokens, or `.env` values are added to commits or logs.
   - [ ] Update deployment or rollback documentation if operational procedures change.
5. **Review readiness**
   - [ ] Link relevant tickets and design assets (wireframes, state matrices).
   - [ ] Note any deliberate follow-ups or known gaps so reviewers understand residual risk.

Skipping any step requires explicit approval from the governance lead.
