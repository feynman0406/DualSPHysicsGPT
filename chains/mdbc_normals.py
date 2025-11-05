"""
Automatic enforcement of mDBC normals configuration.

This module provides utilities to automatically inject and maintain the required
normals configuration for mDBC (Boundary=2) cases.
"""

from typing import Any, Dict, List, Optional, Set
import copy

# Shared constants for mDBC normals configuration
DEFAULT_NORMALS_LIST_NAME = "GeometryForNormals"
DEFAULT_DISTANCEH_VALUE = 2.0
DEFAULT_DISTANCEH_COMMENT = "Maximum orthogonal distance (H*value) to compute normals data (default=2)"
DEFAULT_SVSHAPES_VALUE = True
DEFAULT_SVSHAPES_COMMENT = "Saves VTK with geometry in triangles and quads with its normals for debug (default=false)"
DEFAULT_GEOMETRYFILE_COMMENT = "File with boundary geometry (VTK format)"

PLACEHOLDER_NORMALS_COMMENT = (
    "Boundary=2 (mDBC) uses normals; set active=true and provide norgeometry to enable normals generation."
)
AUTO_ENABLED_NORMALS_COMMENT = (
    "Normals auto-enabled for mDBC; edit norgeometry to customise normal generation."
)



PLACEHOLDER_GEOMETRYFILE = "[CaseName]_hdp_Actual.vtk"  # DualSPHysics expects this placeholder; downstream tools replace [CaseName].


def normalize_geometryfile_target(value: Optional[str]) -> str:
    """Normalize normals geometry file values to the DualSPHysics placeholder.

    Maintainers: keep this placeholder stable. Any exporter that expands
    [CaseName] should call this helper after munging filenames to ensure
    we do not commit generated case-specific paths back into configs.
    """
    candidate = (value or "").strip()
    lower_candidate = candidate.lower()
    if not candidate:
        return PLACEHOLDER_GEOMETRYFILE
    if lower_candidate in {"hdp", PLACEHOLDER_GEOMETRYFILE.lower()}:
        return PLACEHOLDER_GEOMETRYFILE
    if lower_candidate.endswith("_hdp_actual.vtk"):
        return PLACEHOLDER_GEOMETRYFILE
    if lower_candidate.endswith("hdp_actual.vtk"):
        return PLACEHOLDER_GEOMETRYFILE
    # Fallback to placeholder; tooling downstream replaces [CaseName] during export.
    return PLACEHOLDER_GEOMETRYFILE


def _get_boundary_value(config: Dict[str, Any]) -> Optional[int]:
    """Extract Boundary parameter value from config."""
    execution = config.get("execution", {})
    parameters = execution.get("parameters", {})
    
    if isinstance(parameters, dict):
        boundary_cfg = parameters.get("Boundary")
        if boundary_cfg is None:
            return None
        if isinstance(boundary_cfg, dict):
            value = boundary_cfg.get("value")
        else:
            value = boundary_cfg
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _infer_shapeout_target(commands_children: List[Dict[str, Any]]) -> str:
    """
    Infer the shapeout file target from geometry commands.
    Returns the default if detection fails.
    """
    # Look for existing shapeout in mainlist
    for child in commands_children:
        if child.get("tag") == "mainlist":
            for item in child.get("children", []):
                if item.get("type") == "shapeout" or item.get("tag") == "shapeout":
                    attrs = item.get("attributes", {})
                    file_val = attrs.get("file", "")
                    if file_val and file_val != "":
                        return normalize_geometryfile_target(file_val)

    # Default fallback
    return normalize_geometryfile_target(PLACEHOLDER_GEOMETRYFILE)


def _extract_boundary_blocks(mainlist_children: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Extract boundary blocks from mainlist.
    Each block starts with setmkbound/setnormalinvert and ends with resetdraw or the next setmk*.
    Returns list of command sequences.
    """
    blocks: List[List[Dict[str, Any]]] = []
    current_block: List[Dict[str, Any]] = []
    in_boundary = False
    
    for item in mainlist_children:
        item_type = item.get("type") or item.get("tag", "")
        
        # Start of a boundary block
        if item_type in ("setmkbound", "setnormalinvert"):
            if current_block and in_boundary:
                # Save previous block
                blocks.append(current_block)
            current_block = [item]
            in_boundary = True
        
        # Fluid block - save any pending boundary block and skip
        elif item_type == "setmkfluid":
            if current_block and in_boundary:
                blocks.append(current_block)
            current_block = []
            in_boundary = False
        
        # End of block markers
        elif item_type in ("resetdraw", "shapeout", "_shapeout"):
            if in_boundary and current_block:
                current_block.append(item)
                blocks.append(current_block)
                current_block = []
                in_boundary = False
        
        # Add to current block if we're tracking a boundary
        elif in_boundary:
            current_block.append(item)
    
    # Save any remaining block
    if current_block and in_boundary:
        blocks.append(current_block)
    
    return blocks


def _build_normals_list(boundary_blocks: List[List[Dict[str, Any]]], 
                        shapeout_target: str) -> Dict[str, Any]:
    """Build the GeometryForNormals list from extracted boundary blocks."""
    list_children: List[Dict[str, Any]] = [
        {
            "type": "setactive",
            "attributes": {
                "drawpoints": "0",
                "drawshapes": "1"
            }
        },
        {
            "type": "setshapemode",
            "text": "actual | bound"
        }
    ]
    
    # Add all boundary commands from extracted blocks
    for block in boundary_blocks:
        list_children.extend(block)
    
    # Add shapeout and resetdraw at the end
    list_children.append({
        "type": "shapeout",
        "attributes": {
            "file": "hdp" if shapeout_target == "[CaseName]_hdp_Actual.vtk" else shapeout_target
        }
    })
    list_children.append({
        "type": "resetdraw"
    })
    
    return {
        "tag": "list",
        "attributes": {
            "name": DEFAULT_NORMALS_LIST_NAME
        },
        "children": list_children
    }


def _ensure_runlist_before_first_draw(mainlist_children: List[Dict[str, Any]]) -> bool:
    """
    Ensure the GeometryForNormals runlist is the first executable mainlist command.
    Returns True when the list needs to be created or repositioned.
    """
    modified = False

    # Remove duplicate GeometryForNormals runlists but leave other runlists untouched.
    runlist_indices = [
        idx
        for idx, item in enumerate(mainlist_children)
        if (item.get("type") or item.get("tag")) == "runlist"
        and item.get("attributes", {}).get("name") == DEFAULT_NORMALS_LIST_NAME
    ]
    for dup_idx in reversed(runlist_indices[1:]):
        del mainlist_children[dup_idx]
        modified = True

    runlist_idx = runlist_indices[0] if runlist_indices else None

    # GeometryForNormals must execute before any draw commands for DualSPHysics to
    # compute normals correctly, so place it before the first non-comment item.
    insert_idx = 0
    while insert_idx < len(mainlist_children):
        item_type = mainlist_children[insert_idx].get("type") or mainlist_children[insert_idx].get("tag", "")
        if item_type in ("comment", "newvarcte"):
            insert_idx += 1
            continue
        break

    if runlist_idx is None:
        runlist_item = {
            "type": "runlist",
            "attributes": {"name": DEFAULT_NORMALS_LIST_NAME}
        }
        mainlist_children.insert(insert_idx, runlist_item)
        return True

    if runlist_idx != insert_idx:
        runlist_item = mainlist_children.pop(runlist_idx)
        if runlist_idx < insert_idx:
            insert_idx -= 1
        mainlist_children.insert(insert_idx, runlist_item)
        modified = True

    return modified


def _ensure_normals_section(geometry: Dict[str, Any], shapeout_target: str) -> bool:
    """
    Ensure geometry.normals.norgeometry exists with required fields.
    Returns True if modifications were made.
    """
    modified = False
    normalized_target = normalize_geometryfile_target(shapeout_target)

    if "normals" not in geometry:
        geometry["normals"] = {}
        modified = True

    normals = geometry["normals"]

    active_value = normals.get("active")
    if active_value is None:
        normals["active"] = True
        modified = True
    else:
        if isinstance(active_value, str):
            active_normalized = active_value.strip().lower()
            is_active = active_normalized in {"true", "1", "yes", "on"}
        else:
            is_active = bool(active_value)

        if not is_active:
            normals["active"] = True
            modified = True

            comment_value = normals.get("comment")
            if comment_value == PLACEHOLDER_NORMALS_COMMENT:
                normals["comment"] = AUTO_ENABLED_NORMALS_COMMENT

    if "norgeometry" not in normals:
        normals["norgeometry"] = {}
        modified = True

    norgeometry = normals["norgeometry"]

    geometryfile = norgeometry.get("geometryfile")
    if not isinstance(geometryfile, dict):
        norgeometry["geometryfile"] = {
            "file": normalized_target,
            "comment": DEFAULT_GEOMETRYFILE_COMMENT
        }
        modified = True
    else:
        if geometryfile.get("file") != normalized_target:
            geometryfile["file"] = normalized_target
            modified = True
        if "comment" not in geometryfile:
            geometryfile["comment"] = DEFAULT_GEOMETRYFILE_COMMENT
            modified = True

    if "distanceh" not in norgeometry:
        norgeometry["distanceh"] = {
            "v": DEFAULT_DISTANCEH_VALUE,
            "comment": DEFAULT_DISTANCEH_COMMENT
        }
        modified = True

    if "svshapes" not in norgeometry:
        norgeometry["svshapes"] = {
            "v": DEFAULT_SVSHAPES_VALUE,
            "comment": DEFAULT_SVSHAPES_COMMENT
        }
        modified = True

    return modified


def _ensure_normals_in_casedef_children(config: Dict[str, Any]) -> bool:
    """
    Ensure normals section entry exists in casedef_children.
    Returns True if modifications were made.
    """
    casedef_children = config.get("casedef_children")
    if not isinstance(casedef_children, list):
        return False
    
    # Check if normals section already exists
    has_normals = any(
        entry.get("type") == "section" and entry.get("key") == "normals"
        for entry in casedef_children
    )
    
    if has_normals:
        return False
    
    # Find geometry section index
    geometry_idx = None
    for idx, entry in enumerate(casedef_children):
        if entry.get("type") == "section" and entry.get("key") == "geometry":
            geometry_idx = idx
            break
    
    # Insert normals after geometry
    if geometry_idx is not None:
        casedef_children.insert(geometry_idx + 1, {
            "type": "section",
            "key": "normals"
        })
        return True
    
    # If no geometry found, append at end
    casedef_children.append({
        "type": "section",
        "key": "normals"
    })
    return True


def _sync_top_level_normals(config: Dict[str, Any], geometry_normals: Dict[str, Any]) -> bool:
    """Ensure top-level normals mirrors geometry.normals."""
    if not isinstance(geometry_normals, dict):
        return False

    desired = copy.deepcopy(geometry_normals)
    current = config.get("normals")
    if current == desired:
        return False

    config["normals"] = desired
    return True


def enforce_mdbc_normals(config: dict) -> dict:
    """
    Enforce mDBC normals configuration automatically.
    
    Args:
        config: The case configuration dictionary
        
    Returns:
        Modified configuration (may be same object if modified in place,
        or a deep copy if no changes needed for idempotency)
        
    The function:
    - Checks if Boundary=2 (mDBC), early exits otherwise
    - Extracts boundary blocks from mainlist
    - Creates/updates GeometryForNormals list
    - Ensures runlist is present in mainlist
    - Ensures geometry.normals.norgeometry exists
    - Sets structured_meta["mdbc_normals_auto_added"] flag if changes made
    - Is idempotent (multiple calls don't duplicate)
    """
    # Early exit if not mDBC
    boundary_value = _get_boundary_value(config)
    if boundary_value != 2:
        return config
    
    # Work with deep copy for safety, but track if we actually modify
    config = copy.deepcopy(config)
    modified = False
    
    # Ensure geometry section exists
    if "geometry" not in config:
        config["geometry"] = {}
    
    geometry = config["geometry"]
    
    # Ensure commands section exists
    if "commands" not in geometry:
        geometry["commands"] = {"children": []}
    
    commands = geometry["commands"]
    
    # Ensure children list exists
    if "children" not in commands:
        commands["children"] = []
    
    commands_children = commands["children"]
    
    # Find or create mainlist
    mainlist = None
    mainlist_idx = None
    for idx, child in enumerate(commands_children):
        if child.get("tag") == "mainlist":
            mainlist = child
            mainlist_idx = idx
            break
    
    if mainlist is None:
        mainlist = {
            "tag": "mainlist",
            "children": []
        }
        commands_children.append(mainlist)
        mainlist_idx = len(commands_children) - 1
        modified = True
    
    mainlist_children = mainlist.setdefault("children", [])
    
    # Check if GeometryForNormals list already exists
    has_normals_list = any(
        child.get("tag") == "list" 
        and child.get("attributes", {}).get("name") == DEFAULT_NORMALS_LIST_NAME
        for child in commands_children
    )
    
    if not has_normals_list:
        # Extract boundary blocks
        boundary_blocks = _extract_boundary_blocks(mainlist_children)
        
        if boundary_blocks:
            # Infer shapeout target
            shapeout_target = _infer_shapeout_target(commands_children)
            normalized_target = normalize_geometryfile_target(shapeout_target)

            # Build normals list
            normals_list = _build_normals_list(boundary_blocks, normalized_target)

            # Insert before mainlist
            commands_children.insert(mainlist_idx, normals_list)
            modified = True

            # Ensure runlist in mainlist
            if _ensure_runlist_before_first_draw(mainlist_children):
                modified = True

            # Ensure normals section
            if _ensure_normals_section(geometry, normalized_target):
                modified = True
            
            # Ensure normals in casedef_children
            if _ensure_normals_in_casedef_children(config):
                modified = True
    else:
        # List exists, just ensure normals section and runlist
        shapeout_target = _infer_shapeout_target(commands_children)
        normalized_target = normalize_geometryfile_target(shapeout_target)

        if _ensure_runlist_before_first_draw(mainlist_children):
            modified = True

        if _ensure_normals_section(geometry, normalized_target):
            modified = True
        
        if _ensure_normals_in_casedef_children(config):
            modified = True
    
    geom_normals = geometry.get("normals") if isinstance(geometry, dict) else None
    if _sync_top_level_normals(config, geom_normals):
        modified = True

    # Set metadata flag if we made changes
    if modified:
        if "structured_meta" not in config:
            config["structured_meta"] = {}
        config["structured_meta"]["mdbc_normals_auto_added"] = True
    
    return config
