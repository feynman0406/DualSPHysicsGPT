"""Smoke-test the JSON config library by generating XML and optionally running DualSPHysics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AutoXml_script.generate_xml import generate_case_xml
from chains.json_normalizer import normalize_case_config
from chains.mdbc_normals import enforce_mdbc_normals
from tools.exec import run_dualsphysics


DEFAULT_CONFIG_DIR = Path("AutoXml_script/config_library")
DEFAULT_OUTPUT_DIR = Path("AutoXml_script/generated_cases_direct")
DEFAULT_RESULTS_NAME = "results.json"


def _load_config(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON config '{path}': {exc}") from exc


def _write_xml(output_dir: Path, config_path: Path, xml_text: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = output_dir / (config_path.stem + ".xml")
    xml_path.write_text(xml_text, encoding="utf-8")
    return xml_path


def smoke_test_configs(config_dir: Path, output_dir: Path, *, run_solver: bool) -> List[Dict[str, Any]]:
    if not config_dir.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")

    results: List[Dict[str, Any]] = []
    for config_path in sorted(config_dir.glob("*.json")):
        record: Dict[str, Any] = {
            "config": str(config_path),
        }
        try:
            config = _load_config(config_path)
            normalization = normalize_case_config(config)
            config_normalized = enforce_mdbc_normals(normalization.config)
            xml_text = generate_case_xml(config_normalized)
            xml_path = _write_xml(output_dir, config_path, xml_text)
            record["xml"] = str(xml_path)
            if run_solver:
                try:
                    solver_result = run_dualsphysics(xml_text)
                except Exception as exc:  # pylint: disable=broad-except
                    record["solver_status"] = "error"
                    record["solver_error"] = str(exc)
                else:
                    record["solver_status"] = solver_result.get("status", "unknown")
                    record["solver_result"] = solver_result
                    for key in ("warnings", "assets_requested", "assets_copied", "copy_mode", "xml_path", "workdir"):
                        value = solver_result.get(key)
                        if value is None:
                            continue
                        if key == "warnings":
                            dest = record.setdefault("warnings", [])
                            if isinstance(value, list):
                                dest.extend(value)
                            else:
                                dest.append(value)
                        else:
                            record[key] = value
        except Exception as exc:  # pylint: disable=broad-except
            record["error"] = str(exc)
        stdout_text = ""
        solver_result = record.get("solver_result")
        if isinstance(solver_result, dict):
            stdout_text += solver_result.get("stdout", "") or ""
        record_stdout = record.get("stdout")
        if isinstance(record_stdout, str):
            stdout_text += record_stdout
        if "*** WARNING" in stdout_text:
            record["warning"] = True
            if record.get("solver_status") == "success":
                record["solver_status"] = "warning"
        results.append(record)
    return results


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate XML from JSON config library and optionally run DualSPHysics.")
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR, help="Directory containing JSON configs")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory to write generated XML files")
    parser.add_argument("--skip-solver", action="store_true", help="Skip running DualSPHysics solver harness")
    parser.add_argument("--results", type=Path, default=None, help="Optional path to write results summary JSON")
    args = parser.parse_args(argv)

    results = smoke_test_configs(args.config_dir, args.output_dir, run_solver=not args.skip_solver)
    for record in results:
        config_name = Path(record["config"]).name
        status = record.get("solver_status", "skipped" if args.skip_solver else record.get("error", "ok"))
        print(f"{config_name}: {status}")
        if record.get("error"):
            print(f"  error: {record['error']}")
        if record.get("solver_error"):
            print(f"  solver_error: {record['solver_error']}")

    results_path: Path | None = args.results
    if results_path is None and args.output_dir == DEFAULT_OUTPUT_DIR:
        results_path = args.output_dir / DEFAULT_RESULTS_NAME

    if results_path is not None:
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
