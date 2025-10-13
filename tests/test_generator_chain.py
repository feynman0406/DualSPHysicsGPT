import json
import xml.etree.ElementTree as ET

import pytest

from chains import generator
from chains.mdbc_normals import DEFAULT_NORMALS_LIST_NAME, PLACEHOLDER_GEOMETRYFILE


def _disable_external_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generator, "_USE_RAG", False)
    monkeypatch.setenv("USE_RAG", "0")
    monkeypatch.setenv("DSPH_USE_JSON_SCHEMA", "0")
    monkeypatch.setenv("DSPH_STRICT_JSON_SCHEMA", "0")
    monkeypatch.setenv("DSPH_FORBID_XML_FALLBACK", "0")
    monkeypatch.setenv("USE_TWO_STAGE_RAG_SCHEMA", "0")
    monkeypatch.setenv("USE_RAG_PLANNING_AGENT", "0")
    monkeypatch.setenv("OPENAI_RAG_VS_DESIGN_ID", "")
    monkeypatch.setenv("DSPH_DEBUG", "0")
    monkeypatch.setattr(generator, "design_retriever", lambda: None)
    monkeypatch.setattr(generator, "persist_sources", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(generator, "get_last_run_info", lambda: None, raising=False)


def _parse_case_xml(xml_text: str) -> ET.Element:
    return ET.fromstring(xml_text)

def _first_effective_xml_child(parent: ET.Element) -> ET.Element | None:
    for child in list(parent):
        tag = child.tag if isinstance(child.tag, str) else None
        if not tag:
            continue
        if tag in {"comment", "newvarcte"}:
            continue
        return child
    return None


def test_generator_chain_rejects_wrapped_case_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_external_dependencies(monkeypatch)

    def fake_llm_call(*_args, **_kwargs) -> str:
        return '{"case": {"constants": {}}}'

    monkeypatch.setattr(generator, "llm_call", fake_llm_call)

    with pytest.raises(ValueError, match="Generator JSON contract violated"):
        generator.generator_chain("create a 2D dambreak")


def test_generator_chain_validates_fallback_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_external_dependencies(monkeypatch)

    bad_xml = """<case>\n  <casedef>\n    <constantsdef>\n      <gravity x=\"0\" y=\"0\" z=\"-9.81\"/>\n      <rhop0 value=\"1000\"/>\n    </constantsdef>\n    <mkconfig boundcount=\"1\" fluidcount=\"1\"/>\n    <geometry>\n      <definition dp=\"0.01\">\n        <pointmin x=\"0\" y=\"0\" z=\"0\"/>\n        <pointmax x=\"1\" y=\"0\" z=\"1\"/>\n      </definition>\n      <commands>\n        <mainlist>\n          <setmkbound mk=\"0\"/>\n        </mainlist>\n      </commands>\n    </geometry>\n  </casedef>\n  <execution>\n    <parameters>\n      <parameter key=\"Boundary\" value=\"2\"/>\n    </parameters>\n  </execution>\n</case>"""

    monkeypatch.setattr(generator, "llm_call", lambda *_args, **_kwargs: bad_xml)

    with pytest.raises(ValueError, match="Fallback XML failed validation"):
        generator.generator_chain("create a 2D dambreak")


def test_generator_chain_enforces_mdbc_normals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that mDBC normals are automatically enforced in generator chain."""
    _disable_external_dependencies(monkeypatch)

    # Create a minimal mDBC config (Boundary=2) WITHOUT normals section
    mdbc_config_without_normals = {
        "constants": {
            "gravity": {"x": "0", "y": "0", "z": "-9.81"},
            "rhop0": {"value": "1000"}
        },
        "mkconfig": {"boundcount": "11", "fluidcount": "1"},
        "geometry": {
            "definition": {
                "dp": "0.01",
                "pointmin": {"x": "0", "y": "0", "z": "0"},
                "pointmax": {"x": "1", "y": "0.1", "z": "0.5"}
            },
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {"type": "setmkbound", "attributes": {"mk": "10"}},
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "0.1", "z": "0.1"}}
                                ]
                            },
                            {"type": "setmkfluid", "attributes": {"mk": "0"}},
                            {
                                "type": "fillbox",
                                "attributes": {"x": "0.5", "y": "0.05", "z": "0.3"},
                                "children": [
                                    {"tag": "modefill", "text": "void"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0.1"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "0.1", "z": "0.3"}}
                                ]
                            },
                            {"type": "shapeout", "attributes": {"file": "hdp", "reset": True}}
                        ]
                    }
                ]
            }
            # NOTE: NO "normals" section
        },
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"},  # mDBC requires Boundary=2
                "TimeMax": {"value": "1.0"},
                "TimeOut": {"value": "0.1"}
            }
        }
    }

    def fake_llm_call(*_args, **_kwargs) -> str:
        return json.dumps(mdbc_config_without_normals)

    monkeypatch.setattr(generator, "llm_call", fake_llm_call)

    result = generator.generator_chain("create an mDBC case")

    # Verify the result contains XML
    assert "xml" in result
    xml_output = result["xml"]

    # Assert XML contains the required mDBC normals structures
    case_root = _parse_case_xml(xml_output)

    geometry_for_normals_lists = case_root.findall(f".//list[@name='{DEFAULT_NORMALS_LIST_NAME}']")
    assert geometry_for_normals_lists, "XML should contain GeometryForNormals list"
    assert len(geometry_for_normals_lists) == 1, "XML should contain exactly one GeometryForNormals list"

    runlists = case_root.findall(f".//runlist[@name='{DEFAULT_NORMALS_LIST_NAME}']")
    assert len(runlists) == 1, "XML should contain exactly one runlist for GeometryForNormals"

    mainlist_elem = case_root.find(".//mainlist")
    assert mainlist_elem is not None, "XML should include mainlist"
    first_effective = _first_effective_xml_child(mainlist_elem)
    assert first_effective is not None, "Mainlist should contain executable commands"
    assert first_effective.tag == "runlist", "GeometryForNormals runlist must be the first command"
    assert first_effective.get("name") == DEFAULT_NORMALS_LIST_NAME

    normals_elem = case_root.find(".//normals")
    assert normals_elem is not None, "XML should contain normals section"

    norgeometry_elem = normals_elem.find("norgeometry")
    assert norgeometry_elem is not None, "XML should contain norgeometry configuration"

    geometryfile_elem = norgeometry_elem.find("geometryfile")
    assert geometryfile_elem is not None, "XML should contain geometryfile in normals"
    assert geometryfile_elem.attrib.get("file") == PLACEHOLDER_GEOMETRYFILE, "geometryfile should use placeholder"
    assert norgeometry_elem.find("distanceh") is not None, \
        "XML should contain distanceh in normals"
    assert norgeometry_elem.find("svshapes") is not None, \
        "XML should contain svshapes in normals"

    # Verify config was modified
    assert "config" in result
    final_config = result["config"]
    assert "geometry" in final_config
    assert "normals" in final_config["geometry"],         "Config should have normals section added"
    geometry_normals = final_config["geometry"]["normals"]["norgeometry"]
    assert geometry_normals["geometryfile"]["file"] == PLACEHOLDER_GEOMETRYFILE
    top_level_normals = final_config["normals"]["norgeometry"]
    assert top_level_normals["geometryfile"]["file"] == PLACEHOLDER_GEOMETRYFILE



    # Verify metadata flag was set
    if "structured_meta" in final_config:
        assert final_config["structured_meta"].get("mdbc_normals_auto_added") is True, \
            "Metadata should indicate normals were auto-added"


def test_generator_chain_preserves_existing_mdbc_normals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that generator chain preserves existing normals in mDBC configs."""
    _disable_external_dependencies(monkeypatch)

    # Create a complete mDBC config WITH normals section
    mdbc_config_with_normals = {
        "constants": {
            "gravity": {"x": "0", "y": "0", "z": "-9.81"},
            "rhop0": {"value": "1000"}
        },
        "mkconfig": {"boundcount": "11", "fluidcount": "1"},
        "geometry": {
            "definition": {
                "dp": "0.01",
                "pointmin": {"x": "0", "y": "0", "z": "0"},
                "pointmax": {"x": "1", "y": "0.1", "z": "0.5"}
            },
            "commands": {
                "children": [
                    {
                        "tag": "list",
                        "attributes": {"name": "GeometryForNormals"},
                        "children": [
                            {"type": "setactive", "attributes": {"drawpoints": "0", "drawshapes": "1"}},
                            {"type": "setshapemode", "text": "actual | bound"},
                            {"type": "setmkbound", "attributes": {"mk": "10"}},
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "0.1", "z": "0.1"}}
                                ]
                            },
                            {"type": "shapeout", "attributes": {"file": "hdp"}},
                            {"type": "resetdraw"}
                        ]
                    },
                    {
                        "tag": "mainlist",
                        "children": [
                            {"type": "runlist", "attributes": {"name": "GeometryForNormals"}},
                            {"type": "setmkbound", "attributes": {"mk": "10"}},
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "0.1", "z": "0.1"}}
                                ]
                            },
                            {"type": "setmkfluid", "attributes": {"mk": "0"}},
                            {
                                "type": "fillbox",
                                "attributes": {"x": "0.5", "y": "0.05", "z": "0.3"},
                                "children": [
                                    {"tag": "modefill", "text": "void"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0.1"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "0.1", "z": "0.3"}}
                                ]
                            },
                            {"type": "shapeout", "attributes": {"file": "", "reset": True}}
                        ]
                    }
                ]
            },
            "normals": {
                "norgeometry": {
                    "geometryfile": {"file": "MyCase_hdp_Actual.vtk"},
                    "distanceh": {"v": "2.0"},
                    "svshapes": {"v": True}
                }
            }
        },
        "casedef_children": [
            {"type": "section", "key": "mkconfig"},
            {"type": "section", "key": "geometry"},
            {"type": "section", "key": "normals"}
        ],
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"},
                "TimeMax": {"value": "1.0"},
                "TimeOut": {"value": "0.1"}
            }
        }
    }

    def fake_llm_call(*_args, **_kwargs) -> str:
        return json.dumps(mdbc_config_with_normals)

    monkeypatch.setattr(generator, "llm_call", fake_llm_call)

    result = generator.generator_chain("create an mDBC case")

    # Verify result is successful
    assert "xml" in result
    xml_output = result["xml"]

    # Should still contain the normals structures
    case_root = _parse_case_xml(xml_output)

    lists = case_root.findall(f".//list[@name='{DEFAULT_NORMALS_LIST_NAME}']")
    assert len(lists) == 1, f"Should have exactly 1 GeometryForNormals list, found {len(lists)}"

    runlists = case_root.findall(f".//runlist[@name='{DEFAULT_NORMALS_LIST_NAME}']")
    assert len(runlists) == 1, f"Should have exactly 1 GeometryForNormals runlist, found {len(runlists)}"
    mainlist_elem = case_root.find(".//mainlist")
    assert mainlist_elem is not None
    first_effective = _first_effective_xml_child(mainlist_elem)
    assert first_effective is not None
    assert first_effective.tag == "runlist"
    assert first_effective.attrib.get("name") == DEFAULT_NORMALS_LIST_NAME

    normals_elem = case_root.find(".//normals")
    assert normals_elem is not None
    geometryfile_elem = normals_elem.find("norgeometry/geometryfile")
    assert geometryfile_elem is not None
    assert geometryfile_elem.attrib.get("file") == PLACEHOLDER_GEOMETRYFILE

    # Verify the config still has normals
    final_config = result["config"]
    assert "normals" in final_config["geometry"]
    geometry_normals = final_config["geometry"]["normals"]["norgeometry"]
    assert geometry_normals["geometryfile"]["file"] == PLACEHOLDER_GEOMETRYFILE
    top_level_normals = final_config["normals"]["norgeometry"]
    assert top_level_normals["geometryfile"]["file"] == PLACEHOLDER_GEOMETRYFILE


def test_generator_chain_skips_enforcement_for_non_mdbc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that non-mDBC configs (Boundary != 2) are not modified."""
    _disable_external_dependencies(monkeypatch)

    # Create a DBC config (Boundary=1) without normals
    dbc_config = {
        "constants": {
            "gravity": {"x": "0", "y": "0", "z": "-9.81"},
            "rhop0": {"value": "1000"}
        },
        "mkconfig": {"boundcount": "11", "fluidcount": "1"},
        "geometry": {
            "definition": {
                "dp": "0.01",
                "pointmin": {"x": "0", "y": "0", "z": "0"},
                "pointmax": {"x": "1", "y": "0.1", "z": "0.5"}
            },
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {"type": "setmkbound", "attributes": {"mk": "10"}},
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "0.1", "z": "0.1"}}
                                ]
                            },
                            {"type": "setmkfluid", "attributes": {"mk": "0"}},
                            {
                                "type": "fillbox",
                                "attributes": {"x": "0.5", "y": "0.05", "z": "0.3"},
                                "children": [
                                    {"tag": "modefill", "text": "void"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0.1"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "0.1", "z": "0.3"}}
                                ]
                            },
                            {"type": "shapeout", "attributes": {"file": "", "reset": True}}
                        ]
                    }
                ]
            }
        },
        "execution": {
            "parameters": {
                "Boundary": {"value": "1"},  # DBC, not mDBC
                "TimeMax": {"value": "1.0"},
                "TimeOut": {"value": "0.1"}
            }
        }
    }

    def fake_llm_call(*_args, **_kwargs) -> str:
        return json.dumps(dbc_config)

    monkeypatch.setattr(generator, "llm_call", fake_llm_call)

    result = generator.generator_chain("create a DBC case")

    # Verify result is successful
    assert "xml" in result
    xml_output = result["xml"]

    # Should NOT contain mDBC normals structures
    case_root = _parse_case_xml(xml_output)

    assert not case_root.findall(".//list[@name='GeometryForNormals']"), \
        "DBC case should not have GeometryForNormals list"
    assert case_root.find(".//runlist[@name='GeometryForNormals']") is None, \
        "DBC case should not have GeometryForNormals runlist"
    assert case_root.find(".//normals") is None, \
        "DBC case should not have normals section"

    # Verify config was not modified with normals
    final_config = result["config"]
    geometry = final_config.get("geometry", {})
    assert "normals" not in geometry or geometry.get("normals") is None, \
        "DBC case should not have normals section added"
