## Summary
Provide a concise description of the UI/back-end governance changes and link to related issues or backlog items.

## Testing & Quality Gates
- [ ] `scripts/run_full_regression.sh` / `.bat`
- [ ] Additional backend checks (`python -m pytest tests/ui_backend -q`, `ruff check`) if applicable
- [ ] Frontend checks (`npm run lint`, `npm run build`, `npm run test`) if applicable
- [ ] Manual validation notes (screenshots, telemetry exports)

Paste condensed command output or pointers for each box you check.

## Baseline Protection
- [ ] Confirmed no files listed in `docs/ui_integration/baseline_manifest.md` were modified.
- [ ] MVP directories (AutoXml_script/, prompts/, rag/, etc.) untouched.
- [ ] Contribution checklist (`docs/ui_integration/contribution_checklist.md`) completed.

## Documentation
List updates to `progress_log.md`, `backlog.md`, deployment/runbooks, or explain why none were required.

## Follow-up Work
Call out deferred tasks, risks, or telemetry gaps that should move into the backlog.
