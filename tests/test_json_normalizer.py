import json
import copy
from pathlib import Path

from chains.json_normalizer import normalize_case_config


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
    assert result.config["floatings"] == floatings_input

    floatings_input[0]["attributes"]["mkbound"] = 7
    assert result.config["floatings"][0]["attributes"]["mkbound"] == 3
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
