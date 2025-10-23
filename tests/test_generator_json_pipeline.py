import json
from pathlib import Path

from chains.generator import _parse_generator_config
from chains.json_normalizer import normalize_case_config
from sessions import store
from AutoXml_script.generate_xml import generate_case_xml
from AutoXml_script.xml_to_json import parse_case_xml
import xml.etree.ElementTree as ET


def test_parse_config_with_meta():
    text = """
    {
      \"config\": {\"geometry\": {\"dp\": 0.02}},
      \"files\": [
        {\"path\": \"normals.vtk\", \"purpose\": \"Normals mesh\"}
      ],
      \"checks\": [\"domain gate ok\"]
    }
    """
    config, meta = _parse_generator_config(text)
    assert config["geometry"]["dp"] == 0.02
    assert meta["files"][0]["path"] == "normals.vtk"
    assert meta["checks"] == ["domain gate ok"]


def test_parse_config_with_prefix_suffix():
    text = "Here is the plan -> {\"config\": {\"constants\": {\"rhop0\": 1000}}, \"domain_report\": \"ok\"} <- done"
    config, meta = _parse_generator_config(text)
    assert config["constants"]["rhop0"] == 1000
    assert meta["domain_report"] == "ok"


def test_persist_iteration_writes_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DSPH_SESSIONS_DIR", str(tmp_path))
    session_id = "test-session"
    result = {"status": "fail", "stdout": "out", "stderr": "err"}
    store.persist_iteration(
        session_id=session_id,
        iteration=1,
        prompt="demo",
        xml="<case/>",
        config={"constants": {"gravity": {"z": -9.81}}},
        structured_meta={"checks": ["ok"]},
        generator_warnings=["fallback xml used"],
        result=result,
    )
    base = Path(store.session_dir(session_id))
    config_text = (base / "last_config.json").read_text(encoding="utf-8")
    assert "gravity" in config_text
    assert "-9.81" in config_text
    warnings_text = (base / "generator_warnings.txt").read_text(encoding="utf-8").strip()
    assert warnings_text == "fallback xml used"
    history = json.loads((base / "history.json").read_text(encoding="utf-8"))
    assert history[-1]["config_chars"] > 0
    assert history[-1]["generator_warnings"] == ["fallback xml used"]


def _normalize_xml(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    return ET.tostring(root, encoding="unicode")


def test_roundtrip_json_xml_bijection():
    library_dir = Path(__file__).resolve().parents[1] / "AutoXml_script" / "config_library"
    assert library_dir.exists()

    for config_path in sorted(library_dir.glob("*.json")):
        config = json.loads(config_path.read_text(encoding="utf-8"))
        xml_initial = generate_case_xml(config)
        parsed_config = parse_case_xml(xml_initial)
        xml_roundtrip = generate_case_xml(parsed_config)
        assert _normalize_xml(xml_initial) == _normalize_xml(xml_roundtrip)
        parsed_again = parse_case_xml(xml_roundtrip)
        assert parsed_config == parsed_again


def test_gpt_style_payload_roundtrip():
    raw_payload = {
        "config": {
            "casedef": {
                "constantsdef": {
                    "gravity": {"x": 0, "y": 0, "z": -9.81, "_units": "m/s^2"},
                    "rhop0": {"value": 1000, "_units": "kg/m^3"},
                },
                "mkconfig": {"boundcount": 240, "fluidcount": 9},
                "geometry": {
                    "definition": {
                        "dp": 0.01,
                        "pointref": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "pointmin": {"x": -2.0, "y": 0.0, "z": -1.5},
                        "pointmax": {"x": 6.0, "y": 0.0, "z": 4.5},
                    },
                    "commands": {
                        "mainlist": [
                            {"setdrawmode": {"mode": "full"}},
                            {"setmkfluid": {"mk": 0}},
                            {"fillbox": {"modefill": "void", "point": {"x": 0.0, "y": -1.0, "z": 0.0}, "size": {"x": 1.0, "y": 2.0, "z": 2.0}}},
                            {"setmkbound": {"mk": 0}},
                            {
                                "drawbox": {
                                    "boxfill": "bottom | left | right | front | back",
                                    "point": {"x": 0.0, "y": -1.0, "z": 0.0},
                                    "size": {"x": 4.0, "y": 2.0, "z": 3.0},
                                }
                            },
                            {"shapeout": {"file": ""}},
                        ]
                    },
                },
            },
            "execution": {
                "parameters": {
                    "parameter": [
                        {"key": "TimeMax", "value": "3.0"},
                        {"key": "TimeOut", "value": "0.01"},
                    ],
                    "simulationdomain": {
                        "posmin": {"x": "default", "y": "default", "z": "default"},
                        "posmax": {"x": "default", "y": "default", "z": "default"},
                    },
                }
            },
        }
    }

    raw_json = json.dumps(raw_payload)
    config_payload, _ = _parse_generator_config(raw_json)
    assert config_payload is not None

    from chains.json_normalizer import normalize_case_config

    normalized = normalize_case_config(config_payload)
    xml_text = generate_case_xml(normalized.config)
    parsed_back = parse_case_xml(xml_text)
    gravity_entry = parsed_back["constants"]["gravity"]
    gravity_attrs = gravity_entry.get("attributes", gravity_entry)
    assert gravity_attrs["units_comment"] == "m/s^2"







def test_pipeline_emits_floatings_section():
    raw_payload = {
        "constants": {
            "gravity": {"x": 0, "y": 0, "z": -9.81},
            "rhop0": {"value": 1000},
        },
        "mkconfig": {"boundcount": 2, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"setmkfluid": {"mk": 0}},
                    {"fillbox": {"modefill": "void", "point": {"x": 0, "y": 0, "z": 0}, "size": {"x": 1, "y": 1, "z": 1}}},
                ]
            },
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 3},
                "children": [
                    {"type": "massbody", "attributes": {"value": 1.1}},
                ],
            }
        ],
        "execution": {
            "parameters": {
                "TimeMax": 1.0,
                "TimeOut": 0.1,
                "Boundary": 2,
            }
        },
    }

    normalized = normalize_case_config(raw_payload)
    xml_text = generate_case_xml(normalized.config)
    root = ET.fromstring(xml_text)

    floating = root.find("casedef/floatings/floating[@mkbound='3']")
    assert floating is not None
    mass_node = floating.find("massbody")
    assert mass_node is not None and mass_node.attrib.get("value") == "1.1"
    assert root.find("execution/special/floating") is None

    parsed = parse_case_xml(xml_text)
    assert "floatings" in parsed
    assert parsed["floatings"][0]["type"] == "floating"

    parsed_plan = [
        entry["key"]
        for entry in parsed.get("casedef_children", [])
        if isinstance(entry, dict) and entry.get("type") == "section"
    ]
    assert "floatings" in parsed_plan
    assert parsed_plan.count("floatings") == 1
    if "geometry" in parsed_plan:
        assert parsed_plan.index("floatings") > parsed_plan.index("geometry")
    if "initials" in parsed_plan:
        assert parsed_plan.index("floatings") > parsed_plan.index("initials")
