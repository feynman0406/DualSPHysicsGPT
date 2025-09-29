"""Generate XML roundtrip outputs for all Case*.xml files."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import sys


def _bootstrap_imports() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_bootstrap_imports()

from AutoXml_script.xml_to_json import parse_case_xml
from AutoXml_script.generate_xml import generate_case_xml


def collect_case_files(root: Path) -> List[Path]:
    cases = sorted(root.glob("Case*.xml"))
    default_case = root / "case.xml"
    if default_case.exists():
        cases = [path for path in cases if path != default_case]
        cases.insert(0, default_case)
    return cases


def generate_all(case_files: List[Path], output_dir: Path) -> List[Tuple[str, str, str | None]]:
    results: List[Tuple[str, str, str | None]] = []
    output_dir.mkdir(exist_ok=True, parents=True)

    for case_path in case_files:
        try:
            xml_text = case_path.read_text(encoding="utf-8")
            config = parse_case_xml(xml_text)
            new_xml = generate_case_xml(config, pretty=True)
            output_path = output_dir / case_path.name
            output_path.write_text(new_xml, encoding="utf-8")
            results.append((case_path.name, "ok", None))
        except Exception as exc:  # pragma: no cover - diagnostic output
            results.append((case_path.name, "error", str(exc)))
    return results


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "AutoXml_script"
    output_dir = source_root / "generated_cases_roundtrip"

    case_files = collect_case_files(source_root)
    if not case_files:
        print("No Case*.xml files found.")
        return 1

    results = generate_all(case_files, output_dir)
    success = 0
    for name, status, message in results:
        if status == "ok":
            success += 1
            print(f"[OK]   {name}")
        else:
            print(f"[FAIL] {name}: {message}")

    print(f"\nGenerated {success}/{len(results)} files into {output_dir}.")
    return 0 if success == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
