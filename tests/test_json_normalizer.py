import json
import copy
from pathlib import Path
import xml.etree.ElementTree as ET

from chains.json_normalizer import normalize_case_config
from AutoXml_script.generate_xml import generate_case_xml


def test_normalize_nested_casedef_payload():
    payload = {
        "case_attributes": {"app": "AutoXML"},
        "casedef": {
            "constantsdef": {
                "gravity": {"x": 0, "y": 0, "z": -9.81, "_units": "m/s^2"},
                "rhop0": {"value": 1000, "_units": "kg/m^3"},
                "coefh": {"value": 1.3, "_comment": "h = coefh*sqrt(3*dp^2)"},
            },
            "mkconfig": {"boundcount": 10, "fluidcount": 5},
            "geometry": {
                "definition": {
                    "dp": 0.02,
                    "pointref": {"x": 0, "y": 0, "z": 0},
                    "pointmin": {"x": 0, "y": 0, "z": 0},
                    "pointmax": {"x": 2, "y": 0, "z": 1},
                    "_note": "thin axis y",
                },
                "commands": {
                    "mainlist": [
                        {"setmkfluid": {"mk": 0}},
                        {"drawbox": {"boxfill": "solid", "point": {"x": 0, "y": 0, "z": 0}, "size": {"x": 1, "y": 1, "z": 1}}},
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

    result = normalize_case_config(payload)
    config = result.config

    assert config["constants"]["gravity"] == {"attributes": {"x": 0, "y": 0, "z": -9.81, "units_comment": "m/s^2"}}
    assert config["constants"]["coefh"] == {"attributes": {"value": 1.3, "comment": "h = coefh*sqrt(3*dp^2)"}}
    assert config["mkconfig"] == {"boundcount": 10, "fluidcount": 5}

    geometry = config["geometry"]
    assert geometry["definition"]["dp"] == 0.02
    # ICS format: commands.children contains list/mainlist nodes
    commands_children = geometry["commands"]["children"]
    assert len(commands_children) == 1
    mainlist_node = commands_children[0]
    assert mainlist_node["tag"] == "mainlist"
    assert len(mainlist_node["children"]) == 2
    assert mainlist_node["children"][0]["type"] == "setmkfluid"
    assert mainlist_node["children"][1]["type"] == "drawbox"

    execution = config["execution"]
    assert execution["parameters"]["TimeMax"] == 3.0
    assert execution["parameters"]["TimeOut"] == 0.01
    # Check parameters_children plan was synthesized
    assert "parameters_children" in execution
    param_plan = execution["parameters_children"]
    assert any(entry["type"] == "parameter" and entry["key"] == "TimeMax" for entry in param_plan)
    assert any(entry["type"] == "parameter" and entry["key"] == "TimeOut" for entry in param_plan)
    # Check extra_nodes for simulationdomain
    extra_nodes = execution.get("extra_nodes", [])
    assert extra_nodes and extra_nodes[0]["tag"] == "simulationdomain"
    # Check simulationdomain is also in the plan
    assert any(entry["type"] == "generic" and entry["spec"]["tag"] == "simulationdomain" for entry in param_plan)

def test_normalize_dependency_files_sanitizes_inputs() -> None:
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"setmkfluid": {"mk": 0}},
                    {"drawbox": {"boxfill": "solid", "point": {"x": 0, "y": 0, "z": 0}}},
                ]
            },
        },
        "files": [
            {"path": "data/sample.csv", "purpose": "fixture"},
            {"path": "/tmp/global.dat"},
            {"path": "../escape.txt"},
        ],
    }

    result = normalize_case_config(payload)
    dependency_files = result.dependency_files
    assert dependency_files == [
        {"path": "data/sample.csv", "purpose": "fixture", "source": "declared"}
    ]
    assert result.config.get("files") == dependency_files
    warning_text = " ".join(result.warnings)
    assert "absolute" in warning_text
    assert "parent traversal" in warning_text



def test_execution_special_sections_preserved_and_ordered():
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"setmkfluid": {"mk": 0}},
                    {
                        "drawbox": {
                            "boxfill": "solid",
                            "point": {"x": 0, "y": 0, "z": 0},
                            "size": {"x": 1, "y": 1, "z": 1},
                        }
                    },
                ]
            },
        },
        "mkconfig": {"boundcount": 1, "fluidcount": 1},
        "execution": {
            "childrenOrder": ["parameters", "Special", "extraNodes"],
            "parameters": {"TimeMax": 1.5, "TimeOut": 0.1},
            "parametersOrder": ["TimeMax", "TimeOut"],
            "specialChildren": [
                {"type": "known", "key": "Gauges", "tag": "gauges"},
                {"type": "known", "key": "timeout"},
                {"type": "known", "key": "wavePaddles"},
                {"type": "known", "key": "ActiveAbsorption", "tag": "activeabsorption"},
                {"type": "known", "key": "passiveAbsorption", "tag": "passiveabsorption"},
                {"type": "generic", "spec": {"tag": "custom", "text": "value"}},
                {"type": "known", "key": "relaxationZones", "tag": "relaxationzones"},
                {"type": "known", "key": "particleFilter", "tag": "particlefilter"},
            ],
            "gauges": [
                {"type": "gauge", "attributes": {"name": "g1"}, "start": {"x": 0.0, "y": 0.0, "z": 0.0}},
            ],
            "timeout": {"entries": [{"value": 1.0}]},
            "wavepaddles": {"entries": [{"tag": "paddle", "attributes": {"id": "p1"}}]},
            "activeAbsorption": {"attributes": {"enabled": "true"}},
            "passive_absorption": {"entries": [{"tag": "passive", "attributes": {"id": "pa"}}]},
            "relaxationzones": {"entries": [{"tag": "zone", "attributes": {"id": "rz"}}]},
            "particle_filters": {"entries": [{"tag": "filter", "attributes": {"id": "pf"}}]},
            "special": [{"tag": "legacy", "text": "legacy"}],
            "extraNodes": [{"tag": "note", "text": "keep me"}],
            "unknownBlock": {"foo": "bar"},
        },
    }

    normalized = normalize_case_config(payload)
    execution = normalized.config["execution"]

    assert execution["children_order"] == ["parameters", "special", "extra_nodes"]
    assert execution["parameters_order"] == ["TimeMax", "TimeOut"]
    assert execution["wavepaddles"]["entries"][0]["attributes"]["id"] == "p1"
    assert execution["gauges"][0]["type"] == "gauge"
    assert execution["active_absorption"]["attributes"]["enabled"] == "true"
    assert execution["special"] == [{"tag": "legacy", "text": "legacy"}]
    assert execution["extra_nodes"][0]["tag"] == "note"

    known_keys = [entry["key"] for entry in execution["special_children"] if entry.get("type") == "known"]
    assert known_keys == [
        "gauges",
        "timeout",
        "wavepaddles",
        "active_absorption",
        "passive_absorption",
        "relaxation_zones",
        "particle_filters",
    ]
    assert any(
        entry.get("type") == "generic" and entry.get("spec", {}).get("tag") == "custom"
        for entry in execution["special_children"]
    )
    assert "unknownBlock" in execution
    assert any("unknownBlock" in warning for warning in normalized.warnings)

    xml_text = generate_case_xml(normalized.config)
    root = ET.fromstring(xml_text)
    special_node = root.find("execution/special")
    assert special_node is not None
    tags = [child.tag for child in list(special_node)]
    assert tags == [
        "gauges",
        "timeout",
        "wavepaddles",
        "activeabsorption",
        "passiveabsorption",
        "custom",
        "relaxationzones",
        "particlefilter",
    ]
    assert special_node.find("wavepaddles/paddle[@id='p1']") is not None
    active_absorption = special_node.find("activeabsorption")
    assert active_absorption is not None and active_absorption.attrib.get("enabled") == "true"
    custom_node = special_node.find("custom")
    assert custom_node is not None and (custom_node.text or "").strip() == "value"
def test_floatings_preserved_top_level():
    floatings_input = [
        {
            "type": "floating",
            "attributes": {"mkbound": 3, "rhopbody": 1200},
            "children": [
                {"type": "massbody", "attributes": {"value": 1.5}}
            ],
        }
    ]

    payload = {
        "constants": {
            "gravity": {"x": 0, "y": 0, "z": -9.81},
            "rhop0": {"value": 1000},
        },
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
        "floatings": copy.deepcopy(floatings_input),
    }

    result = normalize_case_config(payload)
    floating_entry = result.config["floatings"][0]
    attrs = floating_entry.get("attributes", {})
    assert attrs.get("mkbound") == 3
    assert "rhopbody" not in attrs
    children = floating_entry.get("children", [])
    assert any(
        isinstance(child, dict)
        and (child.get("tag") or child.get("type")) == "massbody"
        for child in children
    )
    assert any("multiple descriptors" in warning for warning in result.warnings)

    floatings_input[0]["attributes"]["mkbound"] = 7
    assert floating_entry["attributes"]["mkbound"] == 3
    assert "execution" not in result.config or "special" not in result.config.get("execution", {})


def test_bodyfloating_child_removed_from_floatings():
    payload = {
        "constants": {
            "gravity": {"x": 0, "y": 0, "z": -9.81},
            "rhop0": {"value": 1000},
        },
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
                "children": [
                    {"tag": "bodyfloating", "attributes": {"mkbound": 5}, "id": "Floater"},
                    {
                        "tag": "shape",
                        "children": [
                            {"tag": "drawbox"}
                        ]
                    },
                    {"type": "massbody", "attributes": {"value": 2.2}},
                ],
            }
        ],
    }

    result = normalize_case_config(payload)
    floating_entry = result.config["floatings"][0]
    children = floating_entry.get("children", [])
    assert all(not isinstance(child, dict) or child.get("tag") != "bodyfloating" for child in children)
    assert all(not isinstance(child, dict) or str(child.get("tag")).lower() != "shape" for child in children)
    attrs = floating_entry.get("attributes") or {}
    assert attrs.get("mkbound") == 5
    assert attrs.get("id") == "Floater"
    assert any("bodyfloating" in warning for warning in result.warnings)
    assert any("unsupported floating child" in warning for warning in result.warnings)


def test_casedef_children_inserts_floatings_after_initials():
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "initials": [
            {"type": "initial", "attributes": {"mkfluid": 1}}
        ],
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 5},
                "children": [
                    {"type": "massbody", "attributes": {"value": 2.5}}
                ],
            }
        ],
        "casedef_children": [
            {"type": "section", "key": "constants"},
            {"type": "section", "key": "geometry"},
            {"type": "section", "key": "initials"},
            {"type": "section", "key": "execution"},
        ],
        "execution": {"parameters": {"TimeMax": 1.0}},
    }

    result = normalize_case_config(payload)
    children_plan = [
        entry["key"]
        for entry in result.config.get("casedef_children", [])
        if isinstance(entry, dict) and entry.get("type") == "section"
    ]
    assert children_plan == ["constants", "geometry", "initials", "floatings", "execution"]


def test_casedef_children_inserts_floatings_after_geometry_when_no_initials():
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "normals": {
            "norgeometry": {"geometryfile": {"file": "case_hdp.vtk"}}
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 3},
            }
        ],
        "casedef_children": [
            {"type": "section", "key": "constants"},
            {"type": "section", "key": "geometry"},
            {"type": "section", "key": "normals"},
            {"type": "section", "key": "execution"},
        ],
        "execution": {"parameters": {"TimeMax": 1.0}},
    }

    result = normalize_case_config(payload)
    children_plan = [
        entry["key"]
        for entry in result.config.get("casedef_children", [])
        if isinstance(entry, dict) and entry.get("type") == "section"
    ]
    assert children_plan == ["constants", "geometry", "normals", "floatings", "execution"]


def test_casedef_children_does_not_duplicate_floatings_entry():
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 7},
            }
        ],
        "casedef_children": [
            {"type": "section", "key": "constants"},
            {"type": "section", "key": "geometry"},
            {"type": "section", "key": "floatings"},
            {"type": "section", "key": "execution"},
        ],
        "execution": {"parameters": {"TimeMax": 1.0}},
    }

    result = normalize_case_config(payload)
    floatings_entries = [
        entry
        for entry in result.config.get("casedef_children", [])
        if isinstance(entry, dict)
        and entry.get("type") == "section"
        and isinstance(entry.get("key"), str)
        and entry["key"].lower() == "floatings"
    ]
    assert len(floatings_entries) == 1


def test_floatings_missing_descriptor_gets_rhopbody():
    payload = {
        "constants": {
            "rhop0": {"value": 1000}
        },
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 7}
            }
        ]
    }

    result = normalize_case_config(payload)
    attrs = result.config["floatings"][0]["attributes"]
    assert attrs.get("rhopbody") == 1000.0
    assert any("Added rhopbody" in warning for warning in result.warnings)


def test_floatings_missing_descriptor_without_rhop_warns():
    payload = {
        "constants": {
            "gravity": {"x": 0, "y": 0, "z": -9.81}
        },
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 9}
            }
        ]
    }

    result = normalize_case_config(payload)
    attrs = result.config["floatings"][0].get("attributes", {})
    assert "rhopbody" not in attrs
    assert any("missing massbody" in warning for warning in result.warnings)






def test_floatings_top_level_descriptor_migrated():
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 50},
                "relativeweight": 0.5,
            }
        ],
    }

    result = normalize_case_config(payload)
    floating = result.config["floatings"][0]
    attrs = floating.get("attributes", {})
    assert attrs.get("relativeweight") == 0.5
    assert "relativeweight" not in floating
    assert "rhopbody" not in attrs
    assert not any("Added rhopbody" in warning for warning in result.warnings)
def test_floatings_multiple_descriptors_prefers_massbody():
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 4, "rhopbody": 1050.0},
                "children": [
                    {"type": "massbody", "attributes": {"value": 1.8}},
                ],
            }
        ],
    }

    result = normalize_case_config(payload)
    floating = result.config["floatings"][0]
    attrs = floating.get("attributes", {})
    assert "rhopbody" not in attrs
    children = floating.get("children", [])
    mass_nodes = [
        child
        for child in children
        if isinstance(child, dict)
        and (child.get("tag") or child.get("type")) == "massbody"
    ]
    assert len(mass_nodes) == 1
    assert any("multiple descriptors" in warning for warning in result.warnings)


def test_floatings_multiple_attributes_prefers_relativeweight():
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 0, "z": 1},
            }
        },
        "floatings": [
            {
                "type": "floating",
                "attributes": {"mkbound": 6, "rhopbody": 1020.0, "relativeweight": 0.5},
            }
        ],
    }

    result = normalize_case_config(payload)
    floating = result.config["floatings"][0]
    attrs = floating.get("attributes", {})
    assert "relativeweight" in attrs
    assert "rhopbody" not in attrs
    assert any("multiple descriptors" in warning for warning in result.warnings)

def test_normalize_fluid_fillbox_forces_void_and_coordinates() -> None:
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "geometry": {
            "definition": {
                "dp": 0.02,
                "pointmin": {"x": 0, "y": 0, "z": 0},
                "pointmax": {"x": 1, "y": 1, "z": 1},
            },
            "commands": {
                "mainlist": [
                    {"setmkfluid": {"mk": 0}},
                    {
                        "fillbox": {
                            "modefill": "solid",
                            "point": {"x": 0.5, "y": 0.3, "z": 0.2},
                            "size": {"x": 0.2, "y": 0.1, "z": 0.1},
                        }
                    },
                ]
            },
        },
    }
    result = normalize_case_config(payload)
    mainlist = result.config["geometry"]["commands"]["children"][0]
    fillbox = mainlist["children"][1]
    modefill_entry = next(child for child in fillbox["children"] if child.get("tag") == "modefill")
    assert modefill_entry["text"] == "void"
    attrs = fillbox.get("attributes") or {}
    assert attrs.get("x") == 0.5
    assert attrs.get("y") == 0.3
    assert attrs.get("z") == 0.2

def test_normalize_fluid_fillbox_collapsed_axis_sets_default_thickness() -> None:
    payload = {
        "constants": {"rhop0": {"value": 1000}},
        "mkconfig": {"boundcount": 1, "fluidcount": 1},
        "geometry": {
            "definition": {
                "dp": 0.01,
                "pointmin": {"x": 0.0, "y": 0.0, "z": 0.0},
                "pointmax": {"x": 1.0, "y": 0.0, "z": 1.0},
            },
            "commands": {
                "mainlist": [
                    {"type": "setmkfluid", "attributes": {"mk": 0}},
                    {
                        "type": "fillbox",
                        "attributes": {"x": 0.0, "y": 0.1, "z": 0.0},
                        "children": [
                            {"tag": "point", "vector": {"x": 0.0, "y": 0.0, "z": 0.0}},
                            {"tag": "size", "vector": {"x": 0.5, "y": 0.05, "z": 0.5}},
                            {"tag": "modefill", "text": "solid"},
                        ],
                    },
                ]
            },
        },
    }
    result = normalize_case_config(payload)
    commands = result.config["geometry"]["commands"]["children"][0]["children"]
    fillbox = next(entry for entry in commands if entry.get("type") == "fillbox")
    size_child = next(child for child in fillbox["children"] if child.get("tag") == "size")
    assert size_child["vector"].get("y") == "2"
