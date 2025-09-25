
#!/usr/bin/env python
"""
Ingests the DualSPHysics design corpus into an OpenAI vector store.

This script handles the full end-to-end process:
1.  Finds all .xml files in the data/design_corpus directory.
2.  Performs in-memory sanitization to fix common XML formatting errors.
    - Escapes special characters ('&', '<', '>') in "comment" attributes.
    - Wraps the content of <setshapemode> tags in CDATA if they contain '|'.
3.  Converts the sanitized XML content to JSON format.
4.  Uploads ONLY the generated JSON data to the 'DualSPHysics-Design'
    OpenAI vector store, as the API does not support .xml files directly.
5.  Updates the local .env and rag/vector_stores.json files with the
    vector store ID.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

# --- Pre-computation Setup ---
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import xmltodict
    from rag.openai_file_search import (
        _client,
        _existing_keys,
        _normalize_metadata,
        _upload_file_path,
        create_or_get_vector_store,
    )
except ImportError as e:
    print(f"Missing required dependencies: {e}. Please run 'pip install -r requirements.txt'")
    sys.exit(1)


# --- Configuration ---
DEFAULT_ROOT = REPO_ROOT / "data" / "design_corpus"
DEFAULT_STORE_NAME = "DualSPHysics-Design"
REGISTRY_PATH = REPO_ROOT / "rag" / "vector_stores.json"
ENV_PATH = REPO_ROOT / ".env"


# --- Metadata Classification Logic (from original ingest script) ---
_CASE_PATTERNS = [
    ("solitarywave", "solitary_wave"), ("waverunup", "wave_runup"), ("wavemaker", "wavemaker"),
    ("piston", "wavemaker"), ("flap", "wavemaker"), ("wavesfrcylinder", "flow_around_object"),
    ("wave", "wave"), ("dambreak", "dambreak"), ("floating", "floating_body"), ("fsi", "floating_body"),
    ("movingsquare", "moving_body"), ("turekhron", "moving_body"), ("flowfrcylinder", "flow_around_object"),
    ("poiseuille", "channel_flow"), ("sloshing", "sloshing"), ("pump", "pump"), ("rollingtank", "rolling_tank"),
    ("duckling", "duckling"), ("bathymetry", "bathymetry"), ("damping", "damping"), ("periodicity", "periodicity"),
    ("bowling", "bowling"), ("solids", "solids"),
]
_FEATURE_PATTERNS = [
    ("mdbc", "mDBC"), ("dbc", "DBC"), ("chrono", "Chrono"),
    ("ns", "Non-Newtonian"), ("fs", "FS"), ("fsi", "FSI"),
]

def _classify_features(path: Path) -> list[str]:
    name = path.name.lower().replace(".xml.json", "").replace(".xml", "")
    features = [label for needle, label in _FEATURE_PATTERNS if needle in name]
    return sorted(list(set(features)))

def _classify_case(path: Path) -> str:
    name = path.name.lower().replace(".xml.json", "").replace(".xml", "")
    for needle, label in _CASE_PATTERNS:
        if needle in name:
            return label
    return "generic"

def _classify_dim(path: Path) -> str:
    name = path.name.lower().replace(".xml.json", "").replace(".xml", "")
    if "2d" in name: return "2D"
    if "3d" in name: return "3D"
    return "na"

def _design_metadata(path: Path) -> Dict[str, Any]:
    case_type = _classify_case(path)
    dim = _classify_dim(path)
    features = _classify_features(path)
    metadata = {
        "corpus": "design", "case_type": case_type, "dim": dim,
        "features": features, "lang": "en", "file_ext": "json",
    }
    parts = []
    if dim != "na": parts.append(dim)
    if case_type: parts.append(case_type.replace("_", " "))
    hint = f"{' '.join(parts)} example case ({path.name.replace('.xml.json', '').replace('.xml', '')})" if parts else None
    return {"metadata": metadata, "hint": hint}


# --- Utility Functions ---
def _update_registry(registry_path: Path, key: str, value: str):
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    registry[key] = value
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

def _update_env_var(env_path: Path, key: str, value: str):
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    if not any(line.strip().startswith(f"{key}=") for line in lines):
        lines.append(f"{key}={value}")
    else:
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                break
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- Core Logic ---
def main():
    load_dotenv()
    root = DEFAULT_ROOT.resolve()
    if not root.exists():
        raise SystemExit(f"Corpus directory not found: {root}")

    store_id = create_or_get_vector_store(DEFAULT_STORE_NAME)
    client = _client()
    existing = _existing_keys(client, store_id)
    
    xml_files = list(root.rglob("*.xml"))
    print(f"Found {len(xml_files)} XML files to process.")
    
    converted_count = 0
    uploaded_count = 0
    failed_conversion_count = 0
    
    temp_json_paths = []

    # Step 1: Convert all XML files to JSON in a temporary location
    for xml_path in xml_files:
        temp_json_path = xml_path.with_suffix(".xml.json")
        try:
            with open(xml_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Perform in-memory sanitization
            comment_blocks = re.findall(r'(comment="[^"]*")', content)
            for block in comment_blocks:
                sanitized_block = block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                content = content.replace(block, sanitized_block)
            content = re.sub(r'(<setshapemode>)([^<]*\|[^<]*)(</setshapemode>)', r'\1<![CDATA[\2]]>\3', content)
            prolog_idx = content.find("<?xml")
            if prolog_idx > 0: content = content[prolog_idx:]

            data_dict = xmltodict.parse(content)
            json_data = json.dumps(data_dict, indent=4)
            
            with open(temp_json_path, 'w', encoding='utf-8') as json_file:
                json_file.write(json_data)
            
            temp_json_paths.append(temp_json_path)
            converted_count += 1
        except Exception as e:
            print(f"Skipping failed conversion of {xml_path.name}: {e}")
            failed_conversion_count += 1
            if temp_json_path.exists():
                temp_json_path.unlink() # Clean up failed partial file

    print(f"\nSuccessfully converted {converted_count} files to JSON. {failed_conversion_count} failed.")

    # Step 2: Ingest the temporary JSON files
    print(f"\n--- Ingesting {len(temp_json_paths)} JSON files ---")
    for path in sorted(temp_json_paths):
        normalized = _normalize_metadata(path, _design_metadata, root)
        if normalized.skip:
            continue
            
        key = (normalized.metadata.get("source_path", "").replace(".json", ""), normalized.metadata.get("sha256", ""))
        if key[0] and key[1] and key in existing:
            continue

        try:
            _upload_file_path(client, store_id, path, normalized.metadata)
            uploaded_count += 1
            print(f"Uploaded: {path.name}")
        except Exception as e:
            print(f"Failed to upload {path.name}: {e}")

    print(f"\n--- Ingestion complete. Uploaded {uploaded_count} new files. ---")

    # Step 3: Update config files
    _update_registry(REGISTRY_PATH, "design", store_id)
    _update_env_var(ENV_PATH, "OPENAI_RAG_VS_DESIGN_ID", store_id)
    print(f"\nVector store '{DEFAULT_STORE_NAME}' ready: {store_id}")
    print(f"Registry updated at {REGISTRY_PATH}")
    print(f".env updated with OPENAI_RAG_VS_DESIGN_ID={store_id}")
    
    # Step 4: Clean up temporary JSON files
    print("\n--- Cleaning up temporary JSON files ---")
    for f in temp_json_paths:
        try:
            if f.exists():
                f.unlink()
        except OSError as e:
            print(f"Error removing {f}: {e}")
    print("Cleanup complete.")

if __name__ == "__main__":
    main()

