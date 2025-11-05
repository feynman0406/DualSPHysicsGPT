from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.mvp_direct_file_search import _collect_runtime_dependencies
from tools import exec as exec_tools


def test_geometry_assets_are_copied_into_external_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    geom_dir = tmp_path / "assets"
    geom_dir.mkdir()
    asset = geom_dir / "rotor.vtk"
    asset.write_text("vtk placeholder", encoding="utf-8")

    monkeypatch.setattr(exec_tools, "ASSET_SEARCH_DIRS", [geom_dir])
    monkeypatch.setenv("MVP_RUN_ID", "RUN-TEST-GEOMETRY")

    xml_text = """<?xml version='1.0' encoding='UTF-8'?>\n<case>\n  <casedef>\n    <geometry>\n      <commands>\n        <mainlist>\n          <drawfilevtk file=\"rotor.vtk\"/>\n        </mainlist>\n      </commands>\n    </geometry>\n  </casedef>\n</case>\n"""

    output_dir = tmp_path / "run"
    output_dir.mkdir()

    normalization = SimpleNamespace(config={}, dependency_files=[])

    manifest = _collect_runtime_dependencies(
        normalization=normalization,
        xml_text=xml_text,
        output_dir=output_dir,
        external_stl=None,
    )

    manifest_path = output_dir / "dependency_manifest.json"
    assert manifest_path.exists()
    assert manifest.get("run_id") == "RUN-TEST-GEOMETRY"
    assert manifest.get("warnings") == []

    files = manifest.get("files") or []
    assert files
    geometry_entry = next(item for item in files if item.get("path") == "rotor.vtk")
    assert geometry_entry.get("status") == "copied"
    assert geometry_entry.get("source") == "xml"
    assert geometry_entry.get("purpose") == "Geometry asset referenced in XML"
    copied_path = output_dir / Path(geometry_entry.get("copied_path"))
    assert copied_path.exists()
    assert copied_path.read_text(encoding="utf-8") == "vtk placeholder"
