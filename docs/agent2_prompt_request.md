# Agent 2 Prompt Request (Strict Schema Generator)

## Purpose
Equip ChatGPT to draft the production prompt for the Stage 2 agent that converts Agent 1 guidance into strict-schema DualSPHysics configuration JSON.

## Context
- Stage 2 receives the user query, Agent 1's JSON instructions, and the strict schema (`schemas/dualsphysics_config_schema.json`).
- It must preserve the original structural blueprint of the reference cases while applying mandatory geometry and water-body changes indicated by Agent 1 and the user.
- Output must be valid JSON conforming exactly to the schema (strict mode) so OpenAI structured-output validation passes.

## Responsibilities the resulting prompt must enforce
1. Parse Agent 1's ranked references, required changes, and preserve-as-is directives.
2. Honour minimal-change principle: only modify what Agent 1 marks as required or what the user query explicitly demands.
3. Treat geometry layout (domain dimensions, shapes, fluid fills) and water-body definition as mandatory update zones; failure to apply them is unacceptable even if other sections stay intact.
4. Populate every required schema field; use null or defaults only when explicitly allowed and noted.
5. Validate consistency (e.g., mkconfig counts vs. geometry commands) and surface unresolved issues in warnings if schema allows.

## Constraints and principles
- Strict schema: no extra keys, types must match (numbers, booleans as specified).
- Maintain ordering and structure mirroring references (e.g., geometry command order) unless geometry edits necessitate targeted replacements.
- Avoid inventing unsupported physics features; follow Agent 1's instructions or state missing data.
- Keep responses concise but explicit about any assumptions.

## Inputs supplied at runtime (mention in the prompt)
- User query text.
- Agent 1 JSON with fields like `selected_references`, `required_changes`, `preserve_sections`, `warnings`.
- The JSON schema (inline or referenced) loaded before generation.

## Deliverable to request from ChatGPT
Ask ChatGPT to return:
- A system prompt for Agent 2 emphasising strict-schema compliance and minimal-change with geometry and water priorities.
- A user message template that nests the user query, schema summary or identifier, and Agent 1 instructions.
- A checklist or inference procedure describing how Agent 2 should apply geometry and water edits, honour preserve directives, and validate mkconfig or geometry consistency before emitting JSON.
- Optional fallback or warning policy when required data is missing.
Format output in Markdown with clear section headings.

## Tone and style expectations for the generated prompt
- Technical, deterministic language.
- Step-by-step lists where possible (for example the order of operations before JSON emission).
- Explicit mention of geometry and water handling priority.

## Review checklist to include in ChatGPT's response
- Confirms geometry and water-body modifications are mandatory and prioritised.
- Confirms minimal-change rule for non-mandatory sections.
- Confirms strict schema validation and error handling steps.

## Ready-to-send ChatGPT request
```
You are ChatGPT acting as a prompt engineer. I need you to craft the production prompt for "Agent 2 (Strict Schema Generator)" in a DualSPHysics pipeline. This agent receives the user query, JSON instructions from Agent 1, and a strict JSON schema, and must output a configuration JSON that matches the schema exactly.

Please deliver:
1. The final system prompt.
2. A user message template with placeholders for {user_query}, {agent1_guidance_json}, and {schema_name}.
3. A step-by-step checklist that the agent should follow before emitting JSON (apply geometry/water edits, respect preserve directives, validate mkconfig counts, etc.).
4. Guardrails or fallback/warning instructions when data is insufficient.

Specification:
- Minimal-change principle, but geometry shape and water-body definition from the user or Agent 1 are mandatory changes.
- Strict adherence to `schemas/dualsphysics_config_schema.json` (no extra keys; correct types).
- Use Agent 1's `required_changes` to drive edits; keep other sections exactly as instructed.
- Emit warnings or TODO notes only in designated schema fields (or explain how to handle if none exist).
- Style: engineering-focused, concise, reproducible.

Format your response in Markdown with separate sections for system prompt, user template, checklist, and guardrails. Ensure the checklist explicitly calls out geometry and water handling, minimal-change enforcement, and schema validation.
```
