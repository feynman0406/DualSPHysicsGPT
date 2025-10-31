# Agent 1 Prompt Request (Reference Curator)

## Purpose
Guide ChatGPT to draft the production prompt for the Stage 1 retrieval agent that selects DualSPHysics reference configurations and writes hand-off guidance for Agent 2.

## Context
- Dual-agent pipeline: Stage 1 retrieves references; Stage 2 emits strict-schema configuration JSON.
- Stage 1 operates over OpenAI `file_search` results (filenames, scores, snippet text, metadata).
- Stage 2 must keep the configuration structure intact, so Stage 1 needs to emphasise minimal necessary edits while still mandating accurate geometry and water-volume updates requested by the user.

## Responsibilities the resulting prompt must cover
1. Interpret the user query and repository metadata to rank and pick the best 2-3 references.
2. Summarise for each reference why it fits, what elements must be changed, and what should remain verbatim.
3. Highlight geometry shape and water-body definitions as mandatory modification areas whenever the user query requires them; these cannot be skipped even under the minimal-change principle.
4. Flag missing data or conflicts explicitly rather than inventing values.
5. Emit a machine-readable JSON payload that Agent 2 can consume (per-reference guidance plus global directives and open issues).
6. When external STL metadata is provided, instruct Agent 2 to replace placeholder STL filenames (External.stl, Duck.stl, etc.) with the user-supplied name in both `<list>` and `<mainlist>` blocks and warn if the path is missing.

## Constraints and principles
- Minimal-change: preserve algorithms, block ordering, optional sections, and defaults unless the user request or retrieved evidence demands alteration.
- Critical exception: geometry layout and water body parameters must be updated to match the target scenario, even if this means altering dimensions, fill commands, or fluid definitions.
- For 2D configurations, emphasise that `geometry.definition.pointmin.y` and `pointmax.y` staying at `0` already enables 2D mode; `fillbox` and related commands must still keep a non-zero `size.y` (e.g., multiples of `#Dp`) so initial particles exist.
- Fluid fillbox guardrails: instruct Agent 2 that every `<setmkfluid>/<fillbox>` must keep `<modefill>void</modefill>`, keep the origin inside the fluid volume bounds (`point.axis <= fillbox.axis <= point.axis + size.axis`), and in 2D force `fillbox.y` to equal the geometry plane (`pointmin.y == pointmax.y == fillbox.y`).
- Cite source files or snippets when possible so later review can trace decisions.
- Keep guidance concise (target under 6000 characters) yet unambiguous.

## Inputs available to Agent 1 (for inclusion in the final prompt)
- User query text.
- `file_search` matches (filename, score, snippet text, metadata such as mk counts).
- Historical defaults known from the repository (for example gravity, mkconfig counts).

## Deliverable to request from ChatGPT
Ask ChatGPT to produce:
- A system prompt for Agent 1.
- A user message template (with placeholders) that the orchestrator will fill at runtime.
- A JSON output schema or example detailing keys such as `selected_references`, `required_changes`, `preserve_sections`, `warnings`.
- Guardrail notes (for example refusal policy, when to emit missing-fields warnings).
Return everything in Markdown with distinct headings per component.

## Tone and style expectations for the generated prompt
- Technical, engineering-focused language.
- Clear bullet lists and numbered steps.
- No marketing tone; focus on decision rules and reproducibility.

## Review checklist to include in ChatGPT's response
- Confirm the prompt forces geometry and water adjustments when needed.
- Confirm it forbids unnecessary structural edits.
- Confirm the JSON keys are fully enumerated.

## Ready-to-send ChatGPT request
```
You are ChatGPT acting as a prompt engineer. I need you to craft the production prompt for "Agent 1 (Reference Curator)" in a DualSPHysics two-stage pipeline. This agent reads user queries and OpenAI file_search results, picks 2-3 reference configuration files, and outputs machine-readable guidance for a downstream schema agent.

Please read the specification below and deliver:
1. The final system prompt text.
2. A user message template with placeholders for {user_query}, {file_search_matches}, etc.
3. A JSON output schema or example describing the structure Agent 1 must emit (include per-reference fields for why_selected, required_changes, preserve_sections, citations, and a global action list).
4. Guardrails and review checklist.

Specification:
- Minimal-change principle for the overall configuration, except geometry shapes and water-body definitions, which must ALWAYS be updated to match the requested scenario.
- Agent 1 must highlight geometry and water edits as mandatory when adapting references.
- Agent 1 must cite sources or snippets when available and flag unknown values instead of hallucinating.
- Guidance must stay under 6000 characters while remaining precise.
- Style: engineering-focused, with clear bullet lists and numbered steps.

Format your response in Markdown with headings for each requested component. Ensure the review checklist explicitly confirms geometry and water handling, minimal-change enforcement, and JSON field coverage.
```



