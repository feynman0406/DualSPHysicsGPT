# Workflow: Integrating New Example XML Cases

Follow this workflow whenever a new DualSPHysics example XML is added or materially changed so the case stays annotated, JSON-aligned, and searchable through the OpenAI vector store. The steps below embed all annotation guidelines—no external doc required.

## 1. Annotate the XML Source
1. Open the XML under `AutoXml_script/` (e.g., `AutoXml_script/CaseMyExample_Def.xml`).
2. Skim geometry, motions, floatings, special blocks, gauges, and solver settings so you can describe what makes the case unique (waves, mDBC, Chrono, damping zones, external STL, etc.).
3. Insert **one** plain-English sentence immediately after the XML declaration using this structure:
   ```xml
   <?xml version="1.0" encoding="UTF-8" ?>
   <!-- Wave run-up case: piston basin feeding STL slope and armor blocks with surface gauges. -->
   <case>
   ```
   - Keep it to one (two max) sentences.
   - Mention only the intent and standout configuration; avoid listing every asset.
   - Do not remove existing header comments (e.g., `<!-- Case name: ... -->`).
4. Leave the rest of the XML untouched—no reformatting, no attribute reordering.
5. Sanity check placement:
   ```bash
   Get-Content AutoXml_script/CaseMyExample_Def.xml -TotalCount 5
   ```

## 2. Regenerate the Config-Library JSON
1. Ensure Python deps are available (`pip install -r requirements.txt` if needed).
2. Convert the annotated XML to JSON:
   ```bash
   python AutoXml_script/xml_to_json.py AutoXml_script/CaseMyExample_Def.xml AutoXml_script/config_library/CaseMyExample_Def.json
   ```
3. Re-run this conversion whenever you tweak the XML so the JSON remains canonical.
4. Confirm the `case_comments` block exists at the top of the JSON:
   ```bash
   Get-Content AutoXml_script/config_library/CaseMyExample_Def.json -TotalCount 10
   ```

## 3. Validate the Roundtrip (strongly recommended)
1. Run the fidelity suite:
   ```bash
   python -m pytest tests/test_xml_roundtrip.py -q
   ```
2. Fix any failures before proceeding:
   - Comment mismatch → revisit step 1.
   - Attribute drift → ensure parser/generator hasn’t been modified unexpectedly.
   - Structural mismatch → inspect the regenerated XML (see `generated_cases_roundtrip/` if produced).
3. Only continue once the test reports `1 passed`.

## 4. Refresh the Design Vector Store (RAG ingestion)
1. Set `OPENAI_API_KEY` in the current shell (`setx` or `$env:... = "<key>"`).
2. Find the store ID in `rag/vector_stores.json` under `"design"`.
3. (Optional) Purge the store if you want a clean slate:
   ```bash
   python -m scripts.manage_openai_file_search purge --vector-store-id <VS_ID>
   ```
4. Upload the entire config library so every JSON is indexed:
   ```bash
   python -m scripts.manage_openai_file_search upload --vector-store-id <VS_ID> --dir AutoXml_script/config_library
   ```
5. Watch for HTTP errors or skipped files and rerun if needed.
6. If the upload rotates the store ID, verify `.env` and `rag/vector_stores.json` now contain the correct `OPENAI_RAG_VS_DESIGN_ID`.

## 5. Final Review & Commit
- `git status -sb` should list the annotated XMLs, their JSON counterparts, any supporting code updates, and docs like this one.
- Never commit `.env` secrets; keep them local.
- Mention the ingestion in your commit/PR notes (e.g., “Annotated CaseX, regenerated JSON, uploaded config_library to vs_xxx”).
- Point future agents to this workflow plus the stored vector ID if they need to re-run ingestion.

Following this detailed sequence keeps every new example case annotated, convertible, validated, and discoverable.
