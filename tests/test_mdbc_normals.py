"""Tests for automatic mDBC normals enforcement."""
import copy
import json
from pathlib import Path

import pytest

from chains.mdbc_normals import enforce_mdbc_normals, DEFAULT_NORMALS_LIST_NAME, PLACEHOLDER_GEOMETRYFILE





def _first_effective_mainlist_item(children):
    for child in children:
        child_type = child.get("type") or child.get("tag", "")
        if child_type in {"comment", "newvarcte"}:
            continue
        return child
    return None


def test_early_exit_non_mdbc():
    """Non-mDBC configs should pass through unchanged."""
    config = {
        "execution": {
            "parameters": {
                "Boundary": {"value": "1"}  # DBC
            }
        }
    }
    result = enforce_mdbc_normals(config)
    # Should return config unchanged (early exit)
    assert result == config


def test_early_exit_no_boundary():
    """Configs without Boundary parameter should pass through unchanged."""
    config = {
        "execution": {
            "parameters": {}
        }
    }
    result = enforce_mdbc_normals(config)
    assert result == config


def test_inject_normals_for_simple_mdbc():
    """mDBC config lacking normals should have them injected."""
    config = {
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"}
            }
        },
        "geometry": {
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "setmkfluid",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "fillbox",
                                "attributes": {"x": "0.5", "y": "0.5", "z": "0.5"},
                                "children": [
                                    {"tag": "modefill", "text": "void"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "shapeout",
                                "attributes": {"file": ""}
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    result = enforce_mdbc_normals(config)
    
    # Should have created GeometryForNormals list
    commands_children = result["geometry"]["commands"]["children"]
    list_items = [c for c in commands_children if c.get("tag") == "list"]
    assert len(list_items) == 1
    assert list_items[0]["attributes"]["name"] == DEFAULT_NORMALS_LIST_NAME
    
    # Should have inserted runlist in mainlist
    mainlist = [c for c in commands_children if c.get("tag") == "mainlist"][0]
    runlist_items = [c for c in mainlist["children"] if (c.get("type") or c.get("tag")) == "runlist"]
    assert len(runlist_items) == 1
    assert runlist_items[0]["attributes"]["name"] == DEFAULT_NORMALS_LIST_NAME

    first_effective = _first_effective_mainlist_item(mainlist["children"])
    assert first_effective is not None
    assert (first_effective.get("type") or first_effective.get("tag")) == "runlist"
    
    # Should have created normals section
    assert "normals" in result["geometry"]
    assert result["geometry"]["normals"]["active"] is True
    assert "norgeometry" in result["geometry"]["normals"]
    assert result["normals"] == result["geometry"]["normals"]
    
    norgeometry = result["geometry"]["normals"]["norgeometry"]
    geometryfile = norgeometry.get("geometryfile", {})
    assert geometryfile.get("file") == PLACEHOLDER_GEOMETRYFILE
    assert "distanceh" in norgeometry
    assert "svshapes" in norgeometry
    
    # Should have set metadata flag
    assert result.get("structured_meta", {}).get("mdbc_normals_auto_added") is True


def test_idempotency():
    """Running enforce_mdbc_normals multiple times should not duplicate."""
    config = {
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"}
            }
        },
        "geometry": {
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "shapeout",
                                "attributes": {"file": ""}
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    result1 = enforce_mdbc_normals(config)
    result2 = enforce_mdbc_normals(result1)
    assert result1["normals"] == result1["geometry"]["normals"]
    assert result2["normals"] == result2["geometry"]["normals"]
    
    # Should have same structure after second run
    commands_children1 = result1["geometry"]["commands"]["children"]
    commands_children2 = result2["geometry"]["commands"]["children"]
    
    list_count1 = len([c for c in commands_children1 if c.get("tag") == "list"])
    list_count2 = len([c for c in commands_children2 if c.get("tag") == "list"])
    assert list_count1 == list_count2 == 1
    
    mainlist1 = [c for c in commands_children1 if c.get("tag") == "mainlist"][0]
    mainlist2 = [c for c in commands_children2 if c.get("tag") == "mainlist"][0]
    
    runlist_count1 = len([c for c in mainlist1["children"] if (c.get("type") or c.get("tag")) == "runlist"])
    runlist_count2 = len([c for c in mainlist2["children"] if (c.get("type") or c.get("tag")) == "runlist"])
    assert runlist_count1 == runlist_count2 == 1


def test_already_compliant_config():
    """Config that already has proper normals should not be modified."""
    config = {
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"}
            }
        },
        "geometry": {
            "commands": {
                "children": [
                    {
                        "tag": "list",
                        "attributes": {"name": DEFAULT_NORMALS_LIST_NAME},
                        "children": [
                            {
                                "type": "setactive",
                                "attributes": {"drawpoints": "0", "drawshapes": "1"}
                            },
                            {
                                "type": "setshapemode",
                                "text": "actual | bound"
                            },
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "shapeout",
                                "attributes": {"file": "hdp"}
                            },
                            {
                                "type": "resetdraw"
                            }
                        ]
                    },
                    {
                        "tag": "mainlist",
                        "children": [
                            {
                                "type": "runlist",
                                "attributes": {"name": DEFAULT_NORMALS_LIST_NAME}
                            },
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            }
                        ]
                    }
                ]
            },
            "normals": {
                "active": True,
                "norgeometry": {
                    "geometryfile": {"file": "[CaseName]_hdp_Actual.vtk"},
                    "distanceh": {"v": 2.0},
                    "svshapes": {"v": True}
                }
            }
        }
    }
    
    result = enforce_mdbc_normals(config)
    
    # Should still have exactly one list and one runlist
    commands_children = result["geometry"]["commands"]["children"]
    list_count = len([c for c in commands_children if c.get("tag") == "list"])
    assert list_count == 1


def test_reorders_runlist_and_normalizes_existing_geometryfile():
    """Misordered runlists and concrete filenames are corrected."""
    config = {
        "execution": {"parameters": {"Boundary": {"value": "2"}}},
        "geometry": {
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {"type": "comment", "text": "Generated comment"},
                            {
                                "type": "newvarcte",
                                "attributes": {"name": "Alpha", "value": "1"}
                            },
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "runlist",
                                "attributes": {"name": DEFAULT_NORMALS_LIST_NAME}
                            },
                            {
                                "type": "runlist",
                                "attributes": {"name": DEFAULT_NORMALS_LIST_NAME}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "bottom"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            }
                        ]
                    }
                ]
            },
            "normals": {
                "norgeometry": {
                    "geometryfile": {"file": "CaseExample_hdp_Actual.vtk"}
                }
            }
        },
        "normals": {
            "norgeometry": {
                "geometryfile": {"file": "CaseExample_hdp_Actual.vtk"}
            }
        }
    }

    result = enforce_mdbc_normals(config)

    commands_children = result["geometry"]["commands"]["children"]
    mainlist = [c for c in commands_children if c.get("tag") == "mainlist"][0]

    assert mainlist["children"][0].get("type") == "comment"
    assert mainlist["children"][1].get("type") == "newvarcte"

    runlist_items = [
        c
        for c in mainlist["children"]
        if (c.get("type") or c.get("tag")) == "runlist"
        and c.get("attributes", {}).get("name") == DEFAULT_NORMALS_LIST_NAME
    ]
    assert len(runlist_items) == 1

    first_effective = _first_effective_mainlist_item(mainlist["children"])
    assert first_effective is not None
    assert (first_effective.get("type") or first_effective.get("tag")) == "runlist"

    geom_normals = result["geometry"]["normals"]["norgeometry"]
    assert geom_normals["geometryfile"]["file"] == PLACEHOLDER_GEOMETRYFILE

    top_level_normals = result["normals"]["norgeometry"]
    assert top_level_normals["geometryfile"]["file"] == PLACEHOLDER_GEOMETRYFILE


def test_multiple_boundary_segments():
    """Config with multiple boundary segments should handle all."""
    config = {
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"}
            }
        },
        "geometry": {
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "bottom"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "1"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "left"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "shapeout",
                                "attributes": {"file": ""}
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    result = enforce_mdbc_normals(config)
    
    # Should have created list with both boundary blocks
    commands_children = result["geometry"]["commands"]["children"]
    geo_list = [c for c in commands_children if c.get("tag") == "list" and c.get("attributes", {}).get("name") == DEFAULT_NORMALS_LIST_NAME][0]
    
    # Count setmkbound commands in the list
    setmkbound_count = len([c for c in geo_list["children"] if (c.get("type") or c.get("tag")) == "setmkbound"])
    assert setmkbound_count == 2


def test_shapeout_file_inference():
    """Should normalize geometryfile placeholder even with keyword shapeout."""
    config = {
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"}
            }
        },
        "geometry": {
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            },
                            {
                                "type": "shapeout",
                                "attributes": {"file": "parts"}
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    result = enforce_mdbc_normals(config)
    
    # Should normalize to the placeholder even when the list uses keywords
    norgeometry = result["geometry"]["normals"]["norgeometry"]
    assert norgeometry["geometryfile"]["file"] == PLACEHOLDER_GEOMETRYFILE


CONFIG_LIBRARY_DIR = Path(__file__).resolve().parents[1] / "AutoXml_script" / "config_library"


def test_casedef_children_normals_entry():
    """Should add normals section entry to casedef_children if present."""
    config = {
        "execution": {
            "parameters": {
                "Boundary": {"value": "2"}
            }
        },
        "geometry": {
            "commands": {
                "children": [
                    {
                        "tag": "mainlist",
                        "children": [
                            {
                                "type": "setmkbound",
                                "attributes": {"mk": "0"}
                            },
                            {
                                "type": "drawbox",
                                "children": [
                                    {"tag": "boxfill", "text": "solid"},
                                    {"tag": "point", "vector": {"x": "0", "y": "0", "z": "0"}},
                                    {"tag": "size", "vector": {"x": "1", "y": "1", "z": "1"}}
                                ]
                            }
                        ]
                    }
                ]
            }
        },
        "casedef_children": [
            {"type": "section", "key": "constants"},
            {"type": "section", "key": "geometry"}
        ]
    }
    
    result = enforce_mdbc_normals(config)
    
    # Should have added normals section entry
    normals_entries = [e for e in result["casedef_children"] if e.get("key") == "normals"]
    assert len(normals_entries) == 1

    # Should be after geometry
    geometry_idx = next(i for i, e in enumerate(result["casedef_children"]) if e.get("key") == "geometry")
    normals_idx = next(i for i, e in enumerate(result["casedef_children"]) if e.get("key") == "normals")
    assert normals_idx == geometry_idx + 1


def test_config_library_mdbc_normals_sweeper():
    """Ensure all Boundary=2 configs in the library satisfy normals invariants."""
    library_paths = sorted(CONFIG_LIBRARY_DIR.glob("*.json"))
    assert library_paths, "Config library directory is empty"

    for config_path in library_paths:
        with config_path.open(encoding="utf-8") as fh:
            config = json.load(fh)

        boundary = (
            config.get("execution", {})
            .get("parameters", {})
            .get("Boundary", {})
            .get("value")
        )

        default_msg = f"{config_path.name}: unexpected modification for non-mDBC config"
        if boundary is None or str(boundary).strip() != "2":
            enforced = enforce_mdbc_normals(copy.deepcopy(config))
            assert enforced == config, default_msg
            continue

        enforced = enforce_mdbc_normals(copy.deepcopy(config))
        enforced_twice = enforce_mdbc_normals(copy.deepcopy(enforced))
        assert enforced == enforced_twice, f"{config_path.name}: enforcement not idempotent"

        geometry = enforced.get("geometry", {})
        commands = geometry.get("commands", {})
        children = commands.get("children", [])
        assert children, f"{config_path.name}: geometry.commands.children missing"

        geometry_lists = [
            child
            for child in children
            if child.get("tag") == "list"
            and child.get("attributes", {}).get("name") == DEFAULT_NORMALS_LIST_NAME
        ]
        assert geometry_lists, f"{config_path.name}: missing {DEFAULT_NORMALS_LIST_NAME} list"
        normals_list = geometry_lists[0]

        mainlists = [child for child in children if child.get("tag") == "mainlist"]
        assert mainlists, f"{config_path.name}: missing mainlist in geometry commands"
        mainlist = mainlists[0]

        runlists = [
            child
            for child in mainlist.get("children", [])
            if (child.get("type") or child.get("tag")) == "runlist"
            and child.get("attributes", {}).get("name") == DEFAULT_NORMALS_LIST_NAME
        ]
        assert runlists, f"{config_path.name}: missing runlist referencing {DEFAULT_NORMALS_LIST_NAME}"
        assert len(runlists) == 1, f"{config_path.name}: duplicate GeometryForNormals runlists"

        first_effective = _first_effective_mainlist_item(mainlist.get("children", []))
        assert first_effective is not None, f"{config_path.name}: no executable commands in mainlist"
        assert (first_effective.get("type") or first_effective.get("tag")) == "runlist", (
            f"{config_path.name}: GeometryForNormals runlist must run before other commands"
        )

        normals = geometry.get("normals")
        assert normals, f"{config_path.name}: normals section missing"
        norgeometry = normals.get("norgeometry")
        assert norgeometry, f"{config_path.name}: norgeometry missing within normals"
        geometryfile_value = norgeometry.get("geometryfile", {}).get("file")
        assert geometryfile_value == PLACEHOLDER_GEOMETRYFILE, (
            f"{config_path.name}: geometryfile should remain {PLACEHOLDER_GEOMETRYFILE}"
        )
        assert "distanceh" in norgeometry, f"{config_path.name}: distanceh missing"
        assert "svshapes" in norgeometry, f"{config_path.name}: svshapes missing"

        if enforced != config:
            meta_flag = enforced.get("structured_meta", {}).get("mdbc_normals_auto_added")
            assert meta_flag is True, f"{config_path.name}: metadata flag not set after enforcement"
