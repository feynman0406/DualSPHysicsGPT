from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from AutoXml_script.xml_to_json import parse_case_file

XML_DIR = ROOT / "AutoXml_script"
OUTPUT_DIR = XML_DIR / "config_library"


def regenerate() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    xml_files = sorted(XML_DIR.glob("Case*.xml"))
    if not xml_files:
        raise SystemExit("No Case*.xml files found to convert.")

    for xml_path in xml_files:
        config = parse_case_file(xml_path)
        output_path = OUTPUT_DIR / (xml_path.stem + ".json")
        output_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        relative = output_path.relative_to(ROOT)
        print(f"Wrote {relative}")

    print(f"Generated {len(xml_files)} configuration files.")


if __name__ == "__main__":
    regenerate()
