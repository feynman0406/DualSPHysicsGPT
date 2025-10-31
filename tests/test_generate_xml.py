import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "AutoXml_script" / "generate_xml.py"
from AutoXml_script.generate_xml import generate_case_xml


def run_generator(tmp_path: Path, config: dict) -> Path:
    config = dict(config)
    geometry = config.get("geometry") or {}
    if "commands" not in geometry and not geometry.get("objects"):
        geometry = dict(geometry)
        geometry.setdefault(
            "definition",
            {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 0.1, "y": 0.1, "z": 0.1},
            },
        )
        geometry["commands"] = {
            "mainlist": [
                {"type": "setmkfluid", "attributes": {"mk": 0}},
                {
                    "type": "fillbox",
                    "children": [
                        {"tag": "modefill", "text": "void"},
                        {"tag": "point", "vector": {"x": 0, "y": 0, "z": 0}},
                        {"tag": "size", "vector": {"x": 0.1, "y": 0.1, "z": 0.1}},
                    ],
                },
            ]
        }
        config["geometry"] = geometry
    if "mkconfig" not in config:
        config["mkconfig"] = {"boundcount": 1, "fluidcount": 1}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    output_path = tmp_path / "case.xml"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(config_path), "--output", str(output_path)],
        check=True,
    )
    return output_path
    return output_path

def _external_stl_base_config() -> dict:
    return {
        "constants": {"rhop0": 1000},
        "mkconfig": {"boundcount": 20, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.05,
                "pointmin": {"x": 0.0, "y": 0.0, "z": 0.0},
                "pointmax": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            "commands": {
                "children": [
                    {
                        "tag": "list",
                        "attributes": {"name": "GeometryForNormals"},
                        "children": [
                            {"tag": "setactive", "attributes": {"drawpoints": 0, "drawshapes": 1}},
                            {"tag": "setmkbound", "attributes": {"mk": 10}},
                            {
                                "tag": "drawfilestl",
                                "attributes": {"file": "External.stl", "autofill": True, "advanced": True},
                                "children": [
                                    {"tag": "drawmove", "attributes": {"x": 0, "y": 0, "z": 0}},
                                ],
                            },
                        ],
                    },
                    {
                        "tag": "mainlist",
                        "children": [
                            {"tag": "setmkbound", "attributes": {"mk": 10}},
                            {
                                "tag": "drawfilestl",
                                "attributes": {"file": "External.stl", "autofill": True, "advanced": True},
                                "children": [
                                    {"tag": "drawscale", "attributes": {"x": 1, "y": 1, "z": 1}},
                                ],
                            },
                        ],
                    },
                ],
            },
        },
    }


def test_drawfilestl_placeholder_unchanged_without_external_stl(tmp_path: Path) -> None:
    config = _external_stl_base_config()
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()
    draw_nodes = root.findall('.//drawfilestl')
    assert len(draw_nodes) == 2
    assert [node.attrib.get('file') for node in draw_nodes] == ['External.stl', 'External.stl']


def test_drawfilestl_replaced_when_external_stl_provided(tmp_path: Path) -> None:
    config = _external_stl_base_config()
    config['external_stl'] = {"stored_relative_path": "uploads/run123/Boat.stl"}
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()
    draw_nodes = root.findall('.//drawfilestl')
    assert len(draw_nodes) == 2
    for node in draw_nodes:
        assert node.attrib.get('file') == 'Boat.stl'
        assert node.attrib.get('autofill') == 'true'
        assert node.attrib.get('advanced') == 'true'

def test_geometry_fallback_support(tmp_path: Path) -> None:
    config = {
        "constants": {"rhop0": 1000},
        "mkconfig": {"boundcount": 2, "fluidcount": 1},
        "geometry": {
            "dp": 0.05,
            "domain": {
                "min": {"x": -1, "y": 0, "z": -0.5},
                "max": {"x": 1, "y": 0, "z": 0.5},
            },
            "objects": [
                {
                    "type": "fluid",
                    "mk": 0,
                    "shape": "box",
                    "position": {"x": 0, "y": 0, "z": 0},
                    "size": {"x": 1, "y": 1, "z": 1},
                },
                {
                    "type": "bound",
                    "mk": 1,
                    "shape": "box",
                    "fill_mode": "bottom",
                    "position": {"x": 0, "y": 0, "z": -0.5},
                    "size": {"x": 2, "y": 1, "z": 1},
                },
            ],
        },
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    definition = root.find("casedef/geometry/definition")
    assert definition.attrib == {"dp": "0.05"}
    pointmin = definition.find("pointmin")
    assert pointmin.attrib == {"x": "-1", "y": "0", "z": "-0.5"}

    mainlist = root.find("casedef/geometry/commands/mainlist")
    tags = [child.tag for child in list(mainlist)]
    assert tags == ["setmkfluid", "setactive", "fillbox", "setmkbound", "drawbox"]
    fillbox = mainlist.find("fillbox")
    assert fillbox is not None
    assert fillbox.attrib.get("x") == "0"
    assert pytest.approx(float(fillbox.attrib.get("y", "nan")), abs=1e-9) == 0.0
    assert fillbox.attrib.get("z") == "0"


def test_fluid_fillbox_modefill_solid_becomes_void(tmp_path: Path) -> None:
    config = {
        "constants": {"rhop0": 1000},
        "mkconfig": {"boundcount": 1, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 1, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {
                        "type": "fillbox",
                        "children": [
                            {"tag": "modefill", "text": "solid"},
                            {"tag": "point", "vector": {"x": 0.5, "y": 0.0, "z": 0.0}},
                            {"tag": "size", "vector": {"x": 1.2, "y": 0.3, "z": 0.4}},
                        ],
                    },
                ],
            },
        },
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()
    modefill = root.find("casedef/geometry/commands/mainlist/fillbox/modefill")
    assert modefill is not None
    assert modefill.text == "void"

def test_normals_section_emitted(tmp_path: Path) -> None:
    normals_cfg = {
        "active": True,
        "norgeometry": {
            "comment": "Normals for test case",
            "geometryfile": {"file": "normals.vtk", "comment": "Normals mesh"},
            "distanceh": {"v": 1.5, "comment": "Distance multiplier"},
            "svshapes": {"v": True, "comment": "Dump debug shapes"},
        },
    }
    config = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {"normals": normals_cfg},
        "normals": normals_cfg,
    }

    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    normals_node = root.find("casedef/normals")
    assert normals_node is not None
    assert normals_node.attrib.get("active") == "true"

    norgeometry = normals_node.find("norgeometry")
    assert norgeometry is not None

    geometryfile = norgeometry.find("geometryfile")
    assert geometryfile is not None
    assert geometryfile.attrib["file"] == "normals.vtk"
    assert geometryfile.attrib["comment"] == "Normals mesh"

    distanceh = norgeometry.find("distanceh")
    assert distanceh is not None
    assert distanceh.attrib["v"] == "1.5"

    svshapes = norgeometry.find("svshapes")
    assert svshapes is not None
    assert svshapes.attrib["v"] == "true"
def test_mkconfig_patterns_and_timeout(tmp_path: Path) -> None:
    config = {
        "constants": {},
        "mkconfig": {
            "boundcount": 2,
            "fluidcount": 1,
            "orientations": [
                {"type": "bound", "mk": 0, "orient": "YxZ"},
                {"type": "fluid", "mk": 0, "orient": "Xyz"},
            ],
        },
        "patterns": [
            {
                "name": "Solid",
                "pattern": "X",
                "size": {"x": 1, "y": 1, "z": 1},
            }
        ],
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 1, "z": 1},
            }
        },
        "execution": {
            "parameters": {"TimeMax": 1.0},
            "timeout": {
                "entries": [
                    {"time": 0, "timeout": 0.01},
                    {"time": 0.5, "timeout": 0.1},
                ]
            },
        },
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    mkconfig = root.find("casedef/mkconfig")
    assert mkconfig.attrib == {"boundcount": "230", "fluidcount": "15"}
    orientations = [(elem.tag, elem.attrib["orient"]) for elem in mkconfig]
    assert orientations == [("mkorientbound", "YxZ"), ("mkorientfluid", "Xyz")]

    pattern = root.find("casedef/patterns/pattern")
    assert pattern.attrib["name"] == "Solid"
    size = pattern.find("size")
    assert size.attrib == {"x": "1", "y": "1", "z": "1"}

    timeout = root.find("execution/special/timeout")
    assert [elem.attrib for elem in timeout.findall("tout")] == [
        {"time": "0", "timeout": "0.01"},
        {"time": "0.5", "timeout": "0.1"},
    ]


def test_execution_parameters_and_gauges(tmp_path: Path) -> None:
    config = {
        "geometry": {
            "definition": {
                "dp": 0.01,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 1, "z": 1},
            }
        },
        "execution": {
            "parameters": {
                "TimeMax": {"value": 2.0, "units_comment": "seconds"},
                "TimeOut": 0.1,
            },
            "gauges": [
                {
                    "type": "swl",
                    "name": "GaugeA",
                    "start": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "end": {"x": 1.0, "y": 0.0, "z": 1.0},
                }
            ],
        },
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    parameters = root.find("execution/parameters")
    items = {
        elem.attrib["key"]: elem.attrib for elem in parameters.findall("parameter")
    }
    assert items["TimeMax"] == {"key": "TimeMax", "value": "2.0", "units_comment": "seconds"}
    assert items["TimeOut"] == {"key": "TimeOut", "value": "0.1"}

    gauge = root.find("execution/special/gauges/swl")
    assert gauge.attrib == {"name": "GaugeA"}
    assert gauge.find("point0").attrib == {"x": "0.0", "y": "0.0", "z": "0.0"}
    assert gauge.find("point2").attrib == {"x": "1.0", "y": "0.0", "z": "1.0"}


def test_initials_floatings_motion(tmp_path: Path) -> None:
    config = {
        "geometry": {
            "definition": {
                "dp": 0.01,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 1, "z": 1},
            }
        },
        "initials": [
            {"type": "velocity", "mkfluid": 0, "x": 0.2, "y": 0.0, "z": 0.0},
            {
                "type": "rotateaxis",
                "attributes": {"mkbound": 0, "angle": 45, "anglesunits": "degrees"},
                "children": [
                    {"type": "axisp1", "vector": {"x": 0, "y": 0, "z": 0}},
                    {"type": "axisp2", "vector": {"x": 0, "y": 1, "z": 0}},
                ],
            },
        ],
        "floatings": [
            {"type": "floating", "attributes": {"mkbound": 0, "rhopbody": 1300}},
            {
                "type": "floating",
                "attributes": {"mkbound": 1, "property": "Material_1"},
                "children": [
                    {"type": "massbody", "attributes": {"value": 1.3}},
                    {"type": "inertia", "vector": {"x": 11, "y": 12, "z": 13}},
                ],
            },
        ],
        "motion": [
            {
                "type": "obj",
                "children": [
                    {"type": "begin", "attributes": {"mov": 1, "start": 0}},
                    {
                        "type": "mvrect",
                        "attributes": {"id": 1, "duration": 1},
                        "children": [
                            {"type": "vel", "vector": {"x": 0.5, "y": 0.0, "z": 0.0}},
                        ],
                    },
                ],
            }
        ],
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    velocity = root.find("casedef/initials/velocity")
    assert velocity.attrib == {"mkfluid": "0", "x": "0.2", "y": "0.0", "z": "0.0"}
    rotateaxis = root.find("casedef/initials/rotateaxis")
    assert rotateaxis.attrib["mkbound"] == "0"
    assert rotateaxis.find("axisp2").attrib == {"x": "0", "y": "1", "z": "0"}

    floating = root.find("casedef/floatings/floating[@mkbound='1']")
    assert floating.find("massbody").attrib == {"value": "1.3"}
    assert floating.find("inertia").attrib == {"x": "11", "y": "12", "z": "13"}

    mvrect = root.find("casedef/motion/obj/mvrect")
    assert mvrect.attrib["id"] == "1"
    assert mvrect.find("vel").attrib == {"x": "0.5", "y": "0.0", "z": "0.0"}



def test_execution_special_sections(tmp_path: Path) -> None:
    config = {
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 2, "y": 0, "z": 1},
            }
        },
        "execution": {
            "wavepaddles": {
                "piston": {
                    "children": [
                        {"type": "mkbound", "attributes": {"value": 10}},
                        {"type": "waveheight", "attributes": {"value": 0.15}},
                        {"type": "waveperiod", "attributes": {"value": 2.0}},
                    ]
                }
            },
            "relaxation_zones": {
                "attributes": {"active": 1},
                "entries": [
                    {
                        "type": "regular",
                        "children": [
                            {"type": "center", "vector": {"x": 5.0, "y": 0.0, "z": -0.2}},
                            {"type": "width", "attributes": {"value": 1.5}},
                            {"type": "function", "attributes": {"alpha": 6.0, "beta": 2.0}},
                        ],
                    }
                ],
            },
            "particle_filters": {
                "attributes": {"active": 1},
                "entries": [
                    {
                        "type": "filterpos",
                        "children": [
                            {"type": "posmin", "vector": {"x": 0.0, "y": 0.0, "z": -0.5}},
                            {"type": "posmax", "vector": {"x": 1.0, "y": 0.0, "z": 1.0}},
                        ],
                    },
                    {"type": "operation", "attributes": {"type": "add"}},
                ],
            },
        },
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    piston = root.find("execution/special/wavepaddles/piston")
    assert piston is not None
    assert piston.find("waveheight").attrib == {"value": "0.15"}
    assert piston.find("waveperiod").attrib == {"value": "2.0"}

    relaxation = root.find("execution/special/relaxationzones/regular")
    assert relaxation is not None
    assert relaxation.find("center").attrib == {"x": "5.0", "y": "0.0", "z": "-0.2"}
    assert relaxation.find("function").attrib == {"alpha": "6.0", "beta": "2.0"}

    particle = root.find("execution/special/particlefilter")
    assert particle is not None
    assert particle.attrib.get("active") == "1"
    filterpos = particle.find("filterpos")
    assert filterpos.find("posmax").attrib["x"] == "1.0"
    operation = particle.find("operation")
    assert operation.attrib == {"type": "add"}




def test_fillbox_infers_point_attributes(tmp_path: Path) -> None:
    config = {
        "geometry": {
            "definition": {
                "dp": 0.05,
                "pointmin": {"x": 0, "y": 0, "z": -0.5},
                "pointmax": {"x": 2, "y": 0, "z": 0.5},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {
                        "type": "fillbox",
                        "children": [
                            {"tag": "modefill", "text": "void"},
                            {"tag": "point", "vector": {"x": 1.1, "y": 0.0, "z": -0.2}},
                            {"tag": "size", "vector": {"x": 0.3, "y": 0.02, "z": 0.3}},
                        ],
                    },
                ],
            },
        }
    }

    output_xml = run_generator(tmp_path, config)
    fillbox = ET.parse(output_xml).getroot().find("casedef/geometry/commands/mainlist/fillbox")
    assert fillbox is not None
    assert fillbox.attrib == {"x": "1.1", "y": "0.0", "z": "-0.2"}

def test_fillbox_inserts_setactive(tmp_path: Path) -> None:
    config = {
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0.02, "z": 0.5},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkbound", "attributes": {"mk": 0}},
                    {
                        "type": "drawbox",
                        "children": [
                            {"tag": "boxfill", "text": "bottom"},
                            {"tag": "point", "vector": {"x": 0, "y": 0, "z": 0}},
                            {"tag": "size", "vector": {"x": 1, "y": 0.02, "z": 0.5}},
                        ],
                    },
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {
                        "type": "fillbox",
                        "attributes": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "children": [
                            {"tag": "modefill", "text": "void"},
                            {"tag": "point", "vector": {"x": 0.0, "y": 0.0, "z": 0.0}},
                            {"tag": "size", "vector": {"x": 0.5, "y": 0.02, "z": 0.4}},
                        ],
                    },
                ]
            },
        }
    }

    output_xml = run_generator(tmp_path, config)
    mainlist = ET.parse(output_xml).getroot().find("casedef/geometry/commands/mainlist")
    assert mainlist is not None
    tags = [child.tag for child in list(mainlist)]
    assert "fillbox" in tags
    fill_index = tags.index("fillbox")
    assert fill_index > 0
    assert tags[fill_index - 1] == "setactive"
    setactive_attrs = list(mainlist.findall("setactive"))[0].attrib
    assert setactive_attrs == {"drawpoints": "1", "drawshapes": "0"}
def test_constants_label_preserved(tmp_path: Path) -> None:
    config = {
        "constants": {
            "gravity": {"x": 0, "y": 0, "z": -9.81, "label": "Gravity [m/s^2]"},
            "rhop0": {"value": 1000, "label": "Reference density"},
            "hswl": {
                "value": 0,
                "auto": True,
                "label": "Still water level [m]",
                "comment": "Manual override comment",
            },
        }
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    constants = root.find("casedef/constantsdef")
    assert constants is not None

    gravity = constants.find("gravity")
    assert gravity is not None
    assert gravity.attrib["comment"] == "Gravity"
    assert gravity.attrib["units_comment"] == "m/s^2"
    assert gravity.attrib["x"] == "0"
    assert gravity.attrib["z"] == "-9.81"

    rhop0 = constants.find("rhop0")
    assert rhop0 is not None
    assert rhop0.attrib["comment"] == "Reference density"
    assert "units_comment" not in rhop0.attrib
    assert rhop0.attrib["value"] == "1000"

    hswl = constants.find("hswl")
    assert hswl is not None
    assert hswl.attrib["comment"] == "Manual override comment"
    assert hswl.attrib["units_comment"] == "m"
    assert hswl.attrib["auto"] == "true"
    assert hswl.attrib["value"] == "0"


def test_invalid_tag_names_are_sanitized(tmp_path: Path) -> None:
    geometry = {
        "definition": {
            "dp": 0.02,
            "pointmin": {"x": 0, "y": 0, "z": 0},
            "pointmax": {"x": 0.1, "y": 0.1, "z": 0.1},
            "children": [
                {"tag": "Gravity [m/s^2]", "text": "labelled node"},
            ],
        },
        "commands": {
            "mainlist": [
                {"type": "setmkfluid", "attributes": {"mk": 0}},
                {
                    "type": "fillbox",
                    "children": [
                        {"tag": "modefill", "text": "void"},
                        {"tag": "point", "vector": {"x": 0, "y": 0, "z": 0}},
                        {"tag": "size", "vector": {"x": 0.1, "y": 0.1, "z": 0.1}},
                    ],
                },
            ]
        },
    }
    config = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": geometry,
        "mkconfig": {"boundcount": 1, "fluidcount": 1},
    }
    output_xml = run_generator(tmp_path, config)
    root = ET.parse(output_xml).getroot()

    definition = root.find("casedef/geometry/definition")
    assert definition is not None

    sanitized = None
    for child in definition:
        if child.attrib.get("label") == "Gravity [m/s^2]":
            sanitized = child
            break
    assert sanitized is not None
    assert sanitized.tag.startswith("Gravity_m_s_2")
    assert sanitized.text == "labelled node"


def test_generate_case_requires_fluid_fill():
    config = {
        "constants": {"rhop0": 1000},
        "mkconfig": {"boundcount": 2, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {"type": "setmkbound", "attributes": {"mk": 0}},
                ],
            },
        },
    }
    with pytest.raises(ValueError) as excinfo:
        generate_case_xml(config)
    assert "no fluid fill command" in str(excinfo.value)




def test_fluid_fillbox_origin_outside_volume_raises_error() -> None:
    config = {
        "constants": {"rhop0": 1000},
        "mkconfig": {"boundcount": 1, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 1, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {
                        "type": "fillbox",
                        "attributes": {"x": 2.0, "y": 0.5, "z": 0.5},
                        "children": [
                            {"tag": "modefill", "text": "void"},
                            {"tag": "point", "vector": {"x": 0, "y": 0, "z": 0}},
                            {"tag": "size", "vector": {"x": 1, "y": 1, "z": 1}},
                        ],
                    },
                ],
            },
        },
    }
    with pytest.raises(ValueError, match=r"(fluid volume|geometry.definition bounds)"):
        generate_case_xml(config)


def test_fluid_fillbox_2d_geometry_plane_is_enforced() -> None:
    config = {
        "constants": {"rhop0": 1000},
        "mkconfig": {"boundcount": 1, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0.2, "z": 0},
                "pointmax": {"x": 1, "y": 0.2, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {
                        "type": "fillbox",
                        "attributes": {"x": 0.5, "y": 1.0, "z": 0.5},
                        "children": [
                            {"tag": "modefill", "text": "void"},
                            {"tag": "point", "vector": {"x": 0, "y": 0.2, "z": 0}},
                            {"tag": "size", "vector": {"x": 1, "y": 0.4, "z": 1}},
                        ],
                    },
                ],
            },
        },
    }
    xml_string = generate_case_xml(config)
    root = ET.fromstring(xml_string)
    fillbox = root.find("casedef/geometry/commands/mainlist/fillbox")
    assert fillbox is not None
    assert fillbox.attrib.get("y") == "0.2"


def test_fluid_fillbox_geometry_bounds_violation_raises_error() -> None:
    config = {
        "constants": {"rhop0": 1000},
        "mkconfig": {"boundcount": 1, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1.5, "y": 1, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {
                        "type": "fillbox",
                        "attributes": {"x": 1.8, "y": 0.5, "z": 0.5},
                        "children": [
                            {"tag": "modefill", "text": "void"},
                            {"tag": "point", "vector": {"x": 1.0, "y": 0.0, "z": 0.0}},
                            {"tag": "size", "vector": {"x": 1.0, "y": 1.0, "z": 1.0}},
                        ],
                    },
                ],
            },
        },
    }
    with pytest.raises(ValueError, match="geometry.definition bounds"):
        generate_case_xml(config)
