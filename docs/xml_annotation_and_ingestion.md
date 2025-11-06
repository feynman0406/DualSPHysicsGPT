# XML Annotation & Vector Store Ingestion Playbook

This guide captures the exact workflow future agents must follow whenever new DualSPHysics example XML files are added to the repository. Follow every step in order so that the examples stay self-documented and discoverable through the OpenAI vector store used by the RAG pipeline.

---

## 1. Scope
- Applies to *all* newly introduced example XML files (e.g. files placed in `AutoXml_script/`, `data/design_corpus/`, or other tutorial/example folders).
- The goal is to (a) add a short human-readable description at the very top of each XML file and (b) ingest the updated files into the DualSPHysics design vector store once the descriptions are in place.

## 2. Preparation Checklist
1. Confirm you are on a clean branch and aware of any uncommitted work (`git status`).
2. Ensure Python dependencies are installed (`pip install -r requirements.txt`).
3. Export or define the OpenAI credentials required by the ingestion script:
   ```bash
   setx OPENAI_API_KEY "<your-key>"          # Windows PowerShell
   # or
   export OPENAI_API_KEY="<your-key>"        # bash / WSL
   ```
4. (Optional but recommended) Refresh knowledge of existing annotations by opening a few XML files already annotated in `AutoXml_script/`.

## 3. Annotating the XML Example
For each new XML file:

1. **Inspect the scenario**
   - Read enough of the XML to understand the geometry, motions, gauges, solver settings, and any distinguishing features (e.g. mDBC usage, Chrono coupling, damping zones).
   - If the case references external assets (`*.dat`, `*.stl`, etc.), mention them only if they are central to the scenario (avoid listing every asset).

2. **Draft the summary comment**
   - One sentence (two maximum) written in plain English.
   - Capture the case intent, the high-level setup, and any unique solver options.
   - Avoid verbose metadata or restating the filename.
   - Example style:
     ```xml
     <!-- Wave run-up case: piston basin feeding STL slope and armor blocks with extensive surface-level gauges to monitor overtopping. -->
     ```

3. **Insert the comment correctly**
   - Locate the XML declaration line (`<?xml version=...?>`).
   - Insert the summary comment **immediately after** the declaration (or after an existing `<?xml ...?>` line if a header comment precedes the declaration).
   - Leave existing header comments intact (e.g. `<!-- Case name: ... -->`).
   - Do **not** reformat or regenerate the remaining XML.

4. **Recommended implementation pattern**
   - Use a short helper script (Python or your editor) that inserts a comment only when it is missing.
   - Ensure the helper never rewrites content below the inserted line.

5. **Verify formatting**
   - Use `sed -n '1,6p <file>` or your editor to confirm the comment placement.
   - `git diff <file>` should show only the inserted comment line.

## 4. Synchronising the Design Corpus
The ingestion script sweeps the XML files located under `data/design_corpus/`. Make sure the newly annotated example is present there before ingestion.

1. If the canonical source is in another folder (e.g. `AutoXml_script/`), copy or sync it:
   ```bash
   # WSL / bash example
   cp AutoXml_script/NewCase_Def.xml data/design_corpus/

   # Windows PowerShell example
   Copy-Item "AutoXml_script\NewCase_Def.xml" "data\design_corpus\"
   ```
2. Keep filenames unique. If an older version exists in `data/design_corpus/`, update it in place rather than creating duplicates.
3. Stage/commit the updated design corpus file together with the source file so the repo history stays aligned.

## 5. Ingesting into the OpenAI Vector Store
Run the official ingestion script **after** all descriptions are in place and the design corpus is up to date.

1. Execute the script from the repo root:
   ```bash
   python scripts/ingest_design_corpus.py
   ```
2. The script will:
   - Sanitize XML, convert each file to JSON, and upload to the `DualSPHysics-Design` vector store.
   - Re-use or create the vector store ID and update both `.env` and `rag/vector_stores.json`.
   - Print a summary that includes counts of converted/uploaded files. Review the output for failures.
3. On completion:
   - Confirm `.env` now contains the correct `OPENAI_RAG_VS_DESIGN_ID` (the script updates it automatically).
   - Inspect `rag/vector_stores.json` to verify the `design` entry matches the new store ID.
   - Optionally run a quick retrieval smoke test (see `docs/MVP_USAGE.md`) if ingestion introduced many new cases.

## 6. Post-Task Checklist
- `git status` should show only the intended XML and corpus updates plus any doc changes.
- Review diffs to ensure each XML gained exactly one descriptive comment line.
- If ingestion touched `.env`, avoid committing your personal API key—strip secrets before pushing.
- Document noteworthy deviations (e.g. cases requiring more context) in commit messages or supplementary docs.

## 7. Asking a Future Agent to Execute This Workflow
When handing off to a future Codex (or other) agent, reference this playbook explicitly:
> "Please follow `docs/xml_annotation_and_ingestion.md` to annotate the new XML cases and refresh the design vector store."

Pointing agents to this file guarantees consistent summaries in the XML files and keeps the retrieval corpus synchronized with repository changes.

---

**Quick Reference**
1. Add summary comment after `<?xml ...?>`.
2. Sync the annotated XML into `data/design_corpus/`.
3. Run `python scripts/ingest_design_corpus.py` (requires `OPENAI_API_KEY`).
4. Verify diffs and vector store metadata.
