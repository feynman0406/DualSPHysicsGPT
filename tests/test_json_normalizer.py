import json
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
    assert geometry["definition"]["attributes"]["dp"] == 0.02
    commands = geometry["commands"]["mainlist"]
    assert commands[0]["type"] == "setmkfluid"
    assert commands[1]["type"] == "drawbox"

    execution = config["execution"]
    assert execution["parameters"]["TimeMax"] == 3.0
    assert execution["parameters"]["TimeOut"] == 0.01
    extra_nodes = execution.get("extra_nodes", [])
    assert extra_nodes and extra_nodes[0]["tag"] == "simulationdomain"
