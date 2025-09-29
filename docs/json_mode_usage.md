# JSON Mode (Structured Outputs) for AutoXML

This document explains how to enforce JSON output from the OpenAI generator and ensure it conforms to the contract consumed by `AutoXml_script/generate_xml.py`.

What this enables
- The LLM is constrained by a strict JSON Schema so it must return a valid JSON object.
- The result is normalized and validated, then transformed to DualSPHysics XML that passes GenCase.

Prerequisites
- Provider: OpenAI (Responses API). Set environment variables:
  - `LLM_PROVIDER=openai`
  - `OPENAI_API_KEY=YOUR_KEY`
- Files:
  - Schema: `docs/auto_xml_jsonschema.json` (Strictness S1, requires full constants set)
  - Contract prompt: `prompts/auto_xml_contract.md`

Enable JSON Mode
- Required env flags:
  - `GENERATOR_JSON_MODE=1`
  - Optional:
    - `GENERATOR_PROMPT_PATH_JSON=prompts/auto_xml_contract.md`
    - `GENERATOR_JSON_SCHEMA_PATH=docs/auto_xml_jsonschema.json`

How it works end-to-end
1) Prompting
   - `chains/generator.py` detects `GENERATOR_JSON_MODE=1` and uses a JSON-only instruction: 
     “Return exactly one JSON object; no comments, no code fences.”
   - It loads the contract prompt from `prompts/auto_xml_contract.md`.

2) Structured Outputs
   - `llm/client.py` passes:
     ```
     response_format = {
       "type": "json_schema",
       "json_schema": {
         "name": "auto_xml_config",
         "schema": (contents of docs/auto_xml_jsonschema.json),
         "strict": true
       }
     }
     ```
   - This requires the model to emit JSON matching the schema.

3) Normalization & Validation
   - `chains/json_normalizer.py` maps generator JSON into canonical form.
   - Alias supported: `geometry.commands.lists[].items` (preferred) is accepted, normalized from legacy `commands`.
   - `AutoXml_script/generate_xml.py` validates domain and command order. Fallback for `geometry.definition` is applied when only `geometry.dp` and `geometry.domain.min/max` are present.

4) XML Generation
   - The normalized config is passed into `generate_case_xml()` to produce validated XML.

Schema highlights (docs/auto_xml_jsonschema.json)
- Top-level keys (exact): `constants`, `mkconfig`, `geometry`, `casedef_extra`, `execution`
- Constants: requires full official set (e.g., `gravity`, `rhop0`, `gamma`, `_hdp`, `cflnumber`, etc.)
- Geometry:
  - `definition` requires `dp`, `pointmin`, `pointmax`
  - `commands` requires `mainlist`; optional `lists[].name` + `lists[].items`
  - Commands enumerated via `oneOf` (runlist, setactive, setshapemode, setdrawmode, setmk*, layers, shapeout, resetdraw, drawbox, fillbox) with child requirements for draw/fill
- Execution:
  - `parameters` is an object map (scalars, vectors, or generic node/attrs)

Minimal valid template
See the “Minimal valid template” at the end of `docs/auto_xml_jsonschema.json` or the reference example JSON in `prompts/auto_xml_contract.md`.

Notes
- If you switch to OpenRouter, Structured Outputs are not available; JSON Mode still improves outcomes through the prompt and normalizer, but enforcement is best with OpenAI Responses API.
- Tests: `pytest -q` should pass (roundtrip and generator pipeline tests).
