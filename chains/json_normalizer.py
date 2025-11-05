"""Utilities to normalize loosely-structured generator JSON into the schema
expected by AutoXml_script.generate_xml."""

from __future__ import annotations

import copy
import math

from dataclasses import dataclass, field
from chains.mdbc_normals import normalize_geometryfile_target
from typing import Any, Dict, Iterable, List, Optional, Tuple


CANONICAL_CONFIG_KEYS = {
    "case_attributes",
    "casedef_attributes",
    "casedef_children",
    "constants",
    "mkconfig",
    "patterns",
    "geometry",
    "normals",
    "initials",
    "floatings",
    "motion",
    "casedef_extra",
    "execution",
    "execution_attributes",
}

VECTOR_KEYS = {"x", "y", "z"}

EXECUTION_KEY_ALIASES = {
    "childrenorder": "children_order",
    "parameters": "parameters",
    "parametersorder": "parameters_order",
    "parameterschildren": "parameters_children",
    "gauges": "gauges",
    "timeout": "timeout",
    "wavepaddles": "wavepaddles",
    "wavepaddle": "wavepaddles",
    "activeabsorption": "active_absorption",
    "passiveabsorption": "passive_absorption",
    "relaxationzones": "relaxation_zones",
    "relaxationzone": "relaxation_zones",
    "particlefilters": "particle_filters",
    "particlefilter": "particle_filters",
    "special": "special",
    "specialchildren": "special_children",
    "extranodes": "extra_nodes",
    "simulationdomain": "simulationdomain",
}

EXECUTION_SPECIAL_SECTION_KEYS = (
    "wavepaddles",
    "active_absorption",
    "passive_absorption",
    "relaxation_zones",
    "particle_filters",
)

EXECUTION_SPECIAL_CHILD_KEYS = {
    "gauges",
    "timeout",
    "wavepaddles",
    "active_absorption",
    "passive_absorption",
    "relaxation_zones",
    "particle_filters",
    "special",
}

DEFAULT_COLLAPSED_AXIS_THICKNESS = "2"
FILLBOX_OVERSHOOT_MARGIN = 1.0

@dataclass
class NormalizationResult:
    config: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


@dataclass
class ParameterNormalizationResult:
    parameters: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    extra_nodes: List[Dict[str, Any]] = field(default_factory=list)

def _ensure_normals_geometryfile_placeholder(normals: Dict[str, Any]) -> None:
    """Force normals.norgeometry.geometryfile to use the placeholder name."""
    if not isinstance(normals, dict):
        return
    norgeometry = normals.get("norgeometry")
    if not isinstance(norgeometry, dict):
        return
    geometryfile = norgeometry.get("geometryfile")
    if isinstance(geometryfile, dict):
        placeholder = normalize_geometryfile_target(geometryfile.get("file"))
        if geometryfile.get("file") != placeholder:
            geometryfile["file"] = placeholder
    elif geometryfile is not None:
        norgeometry["geometryfile"] = {"file": normalize_geometryfile_target(geometryfile)}




def normalize_case_config(raw: Dict[str, Any]) -> NormalizationResult:
    """Normalize a generator JSON payload into the canonical schema."""

    if not isinstance(raw, dict):
        raise ValueError("config must be a JSON object")

    warnings: List[str] = []

    # Split known keys from extras.
    config: Dict[str, Any] = {}
    for key in CANONICAL_CONFIG_KEYS:
        if key in raw:
            if key == "constants":
                config[key] = _normalize_constants(raw[key])
            elif key == "geometry":
                config[key] = _normalize_geometry(raw[key])
            elif key == "normals":
                normalized_normals = _normalize_normals(raw[key])
                _ensure_normals_geometryfile_placeholder(normalized_normals)
                config[key] = normalized_normals
            elif key == "floatings":
                config[key] = _normalize_floatings(raw[key], warnings)
            elif key == "execution":
                exec_norm = _normalize_execution(raw[key])
                config[key] = exec_norm.config
                warnings.extend(exec_norm.warnings)
            else:
                config[key] = raw[key]

    casedef = raw.get("casedef")
    if isinstance(casedef, dict):
        if "constantsdef" in casedef and "constants" not in config:
            config["constants"] = _normalize_constants(casedef["constantsdef"])
        if "mkconfig" in casedef and "mkconfig" not in config:
            mkconfig = casedef["mkconfig"]
            if isinstance(mkconfig, dict):
                config["mkconfig"] = mkconfig
            else:
                warnings.append("mkconfig ignored: expected object")
        if "geometry" in casedef and "geometry" not in config:
            config["geometry"] = _normalize_geometry(casedef["geometry"])
        extras = [key for key in casedef.keys() if key not in {"constantsdef", "mkconfig", "geometry"}]
        if extras:
            warnings.append(f"casedef keys ignored: {', '.join(extras)}")

    if "constants" not in config:
        raise ValueError("constants section is required")
    if "geometry" not in config:
        raise ValueError("geometry section is required")

    _promote_normals_from_execution(config, warnings)

    _ensure_normals_geometryfile_placeholder(config.get("normals"))
    if isinstance(config.get("geometry"), dict):
        geom_normals = config["geometry"].get("normals")
        _ensure_normals_geometryfile_placeholder(geom_normals)

    geometry_cfg = config.get("geometry")
    normals_cfg = config.get("normals")
    if isinstance(geometry_cfg, dict) and isinstance(normals_cfg, dict) and "normals" not in geometry_cfg:
        geometry_cfg["normals"] = copy.deepcopy(normals_cfg)
        _ensure_normals_geometryfile_placeholder(geometry_cfg["normals"])

    # Normalize notes-like metadata into config extras.
    for meta_key in ("notes", "files", "checks", "domain_report", "citations"):
        if meta_key in raw:
            config.setdefault(meta_key, raw[meta_key])

    return NormalizationResult(config=config, warnings=warnings)


def _normalize_constants(block: Any) -> Dict[str, Any]:
    if not isinstance(block, dict):
        raise ValueError("constants section must be an object")

    constants: Dict[str, Any] = {}
    for name, payload in block.items():
        constants[name] = _normalize_constant_entry(payload)
    return constants


def _normalize_constant_entry(entry: Any) -> Any:
    if isinstance(entry, dict):
        base_attrs: Dict[str, Any] = {}
        node_spec: Dict[str, Any] = {}
        for key, value in entry.items():
            if key.startswith("_"):
                mapped = {
                    "_comment": "comment",
                    "_units": "units_comment",
                    "_notes": "notes",
                }.get(key, key.lstrip("_"))
                base_attrs[mapped] = value
            elif key in {"attributes", "children", "vector", "extra", "type", "tag", "text"}:
                node_spec[key] = value
            elif key in VECTOR_KEYS and _is_scalar(value):
                base_attrs[key] = value
            else:
                base_attrs[key] = value

        if node_spec:
            if base_attrs:
                node_spec.setdefault("attributes", {}).update(base_attrs)
            return node_spec

        if base_attrs and set(base_attrs.keys()) <= VECTOR_KEYS:
            return base_attrs

        if base_attrs:
            return {"attributes": base_attrs}

    return entry


def _normalize_geometry(block: Any) -> Dict[str, Any]:
    if not isinstance(block, dict):
        raise ValueError("geometry section must be an object")

    geometry: Dict[str, Any] = {}
    definition = block.get("definition")
    if definition is not None:
        geometry["definition"] = _normalize_geometry_definition(definition)

    if "commands" in block:
        geometry["commands"] = _normalize_geometry_commands(block["commands"])

    if (
        isinstance(geometry.get("definition"), dict)
        and isinstance(geometry.get("commands"), dict)
    ):
        _enforce_collapsed_axis_guardrails(geometry["definition"], geometry["commands"])
        _ensure_fluid_fillboxes_within_volume(geometry["definition"], geometry["commands"])

    if "predefinition" in block:
        geometry["predefinition"] = block["predefinition"]
    if "extra" in block:
        geometry["extra"] = block["extra"]
    if "objects" in block and "commands" not in geometry:
        geometry["objects"] = block["objects"]
    return geometry




def _is_normals_spec(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    tag = entry.get("tag") or entry.get("type") or entry.get("name")
    return isinstance(tag, str) and tag.strip().lower() == "normals"

def _coerce_bool_like(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return value

def _normalize_normals(entry: Any) -> Dict[str, Any]:
    if entry is None:
        return {}
    if isinstance(entry, dict):
        if _is_normals_spec(entry):
            return _convert_normals_generic(entry)
        normalized = dict(entry)
        normalized.pop("tag", None)
        normalized.pop("type", None)
        normalized.pop("name", None)
        if "norgeometry" in normalized:
            normalized["norgeometry"] = _normalize_norgeometry_structured(normalized["norgeometry"])
        _ensure_normals_geometryfile_placeholder(normalized)
        return normalized
    raise ValueError("normals section must be an object")

def _normalize_norgeometry_structured(entry: Any) -> Dict[str, Any]:
    if entry is None:
        return {}
    if isinstance(entry, dict):
        if _is_normals_spec(entry) or entry.get("tag") or entry.get("type") or entry.get("name"):
            return _convert_norgeometry_generic(entry)
        normalized: Dict[str, Any] = {}
        for key, value in entry.items():
            if key in {"geometryfile", "distanceh", "svshapes"} and isinstance(value, dict) and (value.get("tag") or value.get("type") or value.get("name")):
                normalized[key] = _convert_normals_child_generic(key, value)
            else:
                normalized[key] = value
        return normalized
    raise ValueError("normals.norgeometry must be an object")

def _convert_normals_generic(spec: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    attributes = spec.get("attributes")
    if isinstance(attributes, dict):
        if "active" in attributes:
            normalized["active"] = _coerce_bool_like(attributes["active"])
        if "comment" in attributes:
            normalized["comment"] = attributes["comment"]
    if spec.get("active") is not None:
        normalized["active"] = _coerce_bool_like(spec["active"])
    if spec.get("comment") is not None:
        normalized["comment"] = spec["comment"]

    norgeometry_spec: Optional[Dict[str, Any]] = None
    extras: List[Dict[str, Any]] = []
    for child in spec.get("children", []):
        if not isinstance(child, dict):
            continue
        if _is_normals_spec(child):
            continue
        tag = child.get("tag") or child.get("type") or child.get("name")
        if isinstance(tag, str) and tag.lower() == "norgeometry":
            norgeometry_spec = child
        else:
            extras.append(child)
    if norgeometry_spec is not None:
        normalized["norgeometry"] = _convert_norgeometry_generic(norgeometry_spec)
    if extras:
        normalized["extra"] = extras
    return normalized

def _convert_norgeometry_generic(spec: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    attributes = spec.get("attributes")
    if isinstance(attributes, dict) and attributes.get("comment") is not None:
        normalized["comment"] = attributes["comment"]
    if spec.get("comment") is not None:
        normalized["comment"] = spec["comment"]

    extras: List[Dict[str, Any]] = []
    for child in spec.get("children", []):
        if not isinstance(child, dict):
            continue
        tag = child.get("tag") or child.get("type") or child.get("name")
        if not isinstance(tag, str):
            extras.append(child)
            continue
        tag_lower = tag.lower()
        if tag_lower in {"geometryfile", "distanceh", "svshapes"}:
            normalized[tag_lower] = _convert_normals_child_generic(tag_lower, child)
        else:
            extras.append(child)
    if extras:
        normalized["extra"] = extras
    return normalized

def _convert_normals_child_generic(tag: str, child: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    attributes = child.get("attributes")
    comment_value = child.get("comment")
    if isinstance(attributes, dict) and comment_value is None:
        comment_value = attributes.get("comment")
    if tag == "geometryfile":
        file_value = child.get("file")
        if file_value is None and isinstance(attributes, dict):
            file_value = attributes.get("file")
        if file_value is not None:
            result["file"] = file_value
    elif tag == "distanceh":
        value = child.get("v")
        if value is None and isinstance(attributes, dict):
            value = attributes.get("v")
        if value is not None:
            result["v"] = _coerce_scalar(value)
    elif tag == "svshapes":
        value = child.get("v")
        if value is None and isinstance(attributes, dict):
            value = attributes.get("v")
        if value is not None:
            result["v"] = _coerce_bool_like(value)
    else:
        if isinstance(attributes, dict):
            result.update(attributes)
    for key in ("file", "v"):
        if key in child and key not in result and child[key] is not None:
            result[key] = child[key]
    if comment_value is not None:
        result["comment"] = comment_value
    remaining = {
        k: v
        for k, v in child.items()
        if k not in {"tag", "type", "name", "attributes", "children", "comment", "file", "v"}
    }
    if remaining:
        result.update(remaining)
    return result
def _normalize_geometry_definition(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("geometry.definition must be an object")

    def _vector_from_field(value: Any, tag_name: str) -> Dict[str, Any]:
        if isinstance(value, dict):
            if set(value.keys()) <= VECTOR_KEYS:
                return {axis: _coerce_scalar(value[axis]) for axis in VECTOR_KEYS if axis in value}
            vector = value.get("vector")
            if isinstance(vector, dict):
                return {axis: _coerce_scalar(vector[axis]) for axis in VECTOR_KEYS if axis in vector}
            attributes = value.get("attributes")
            if isinstance(attributes, dict) and set(attributes.keys()) <= VECTOR_KEYS:
                return {axis: _coerce_scalar(attributes[axis]) for axis in VECTOR_KEYS if axis in attributes}
        raise ValueError(f"geometry.definition requires {tag_name}")

    def _sanitize_node(node: Dict[str, Any]) -> Dict[str, Any] | None:
        if not isinstance(node, dict):
            return None
        tag = node.get("tag") or node.get("name") or node.get("type")
        if tag is None:
            return None
        tag_str = str(tag).strip()
        if not tag_str:
            return None
        clean: Dict[str, Any] = dict(node)
        clean["tag"] = tag_str
        if isinstance(clean.get("vector"), dict):
            clean["vector"] = _normalize_vector(clean["vector"])  # type: ignore[arg-type]
        if isinstance(clean.get("children"), list):
            sub = [n for n in (_sanitize_node(c) for c in clean["children"]) if n is not None]
            if sub:
                clean["children"] = sub
            else:
                clean.pop("children", None)
        if isinstance(clean.get("text"), str) and clean["text"].strip() == "":
            clean.pop("text", None)
        return clean

    def _sanitize_children(raw_children: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_children, list):
            return []
        cleaned = [n for n in (_sanitize_node(child) for child in raw_children) if n is not None]
        to_hoist: List[Dict[str, Any]] = []
        for child in cleaned:
            if child.get("tag") in {"pointmin", "pointmax"} and isinstance(child.get("children"), list):
                nested: List[Dict[str, Any]] = []
                for sub in child["children"]:  # type: ignore[index]
                    if sub.get("tag") in {"pointmin", "pointmax"}:
                        to_hoist.append(sub)
                    else:
                        nested.append(sub)
                if nested:
                    child["children"] = nested
                else:
                    child.pop("children", None)
        if to_hoist:
            cleaned.extend(to_hoist)
        return cleaned

    if {"dp", "pointmin", "pointmax"}.issubset(entry.keys()) and not isinstance(entry.get("attributes"), dict):
        dp_value = _coerce_scalar(entry["dp"])
        pointmin_vec = _vector_from_field(entry["pointmin"], "pointmin")
        pointmin_vec = _normalize_vector(pointmin_vec)
        pointmax_vec = _vector_from_field(entry["pointmax"], "pointmax")
        pointmax_vec = _normalize_vector(pointmax_vec)
        children = _sanitize_children(entry.get("children"))
        meta: Dict[str, Any] = {}
        meta_source = entry.get("meta")
        if isinstance(meta_source, dict):
            if meta_source.get("comment") is not None:
                meta["comment"] = meta_source["comment"]
            if meta_source.get("units_comment") is not None:
                meta["units_comment"] = meta_source["units_comment"]
        if entry.get("comment") is not None:
            meta["comment"] = entry["comment"]
        if entry.get("units_comment") is not None:
            meta["units_comment"] = entry["units_comment"]
        definition: Dict[str, Any] = {"dp": dp_value, "pointmin": pointmin_vec, "pointmax": pointmax_vec}
        if meta:
            definition["meta"] = meta
        if children:
            definition["children"] = children
        return definition

    attrs: Dict[str, Any] = {}
    children_specs: List[Dict[str, Any]] = []
    for key, value in entry.items():
        if key in {"dp", "comment", "units_comment"} and _is_scalar(value):
            attrs[key] = value
        elif key in {"attributes", "children"}:
            if key == "attributes" and isinstance(value, dict):
                attrs.update(value)
            elif key == "children" and isinstance(value, list):
                children_specs.extend(value)
        elif key.startswith("_"):
            continue
        elif isinstance(value, dict) and set(value.keys()) <= VECTOR_KEYS:
            children_specs.append({"tag": key, "vector": value})
        else:
            if isinstance(value, dict):
                child_spec: Dict[str, Any] = {"tag": key, "attributes": value}
            elif isinstance(value, list):
                child_spec = {"tag": key, "children": value}
            else:
                child_spec = {"tag": key, "attributes": {"value": value}}
            children_specs.append(child_spec)

    children = _sanitize_children(children_specs)

    dp_value = attrs.pop("dp", None)
    if dp_value is None:
        dp_value = entry.get("dp")
    if dp_value is None:
        raise ValueError("geometry.definition requires dp value")
    dp_value = _coerce_scalar(dp_value)

    def _take_vector(tag_name: str) -> Dict[str, Any]:
        for idx, child in enumerate(list(children)):
            tag = child.get("tag") or child.get("name") or child.get("type")
            if tag == tag_name:
                candidate = children.pop(idx)
                vector = candidate.get("vector")
                if isinstance(vector, dict):
                    return {axis: _coerce_scalar(vector[axis]) for axis in VECTOR_KEYS if axis in vector}
                attrs_node = candidate.get("attributes")
                if isinstance(attrs_node, dict):
                    subset = {axis: _coerce_scalar(attrs_node[axis]) for axis in VECTOR_KEYS if axis in attrs_node}
                    if subset:
                        return subset
                break
        raise ValueError(f"geometry.definition requires {tag_name}")

    pointmin_vec = _normalize_vector(_take_vector("pointmin"))
    pointmax_vec = _normalize_vector(_take_vector("pointmax"))

    meta: Dict[str, Any] = {}
    comment_val = attrs.pop("comment", None)
    if comment_val is not None:
        meta["comment"] = comment_val
    units_val = attrs.pop("units_comment", None)
    if units_val is not None:
        meta["units_comment"] = units_val

    definition: Dict[str, Any] = {
        "dp": dp_value,
        "pointmin": pointmin_vec,
        "pointmax": pointmax_vec,
    }
    if meta:
        definition["meta"] = meta
    if children:
        definition["children"] = children
    return definition
def _normalize_geometry_commands(entry: Any) -> Dict[str, Any]:
    """Normalize GOS geometry.commands (lists/mainlist) to ICS (children array)."""
    if not isinstance(entry, dict):
        raise ValueError("geometry.commands must be an object")

    # Already normalized (children array) ? coerce child nodes and return.
    if "children" in entry:
        children = [
            _normalize_vector_in_node(child)
            for child in entry.get("children", [])
            if child is not None
        ]
        return {"children": children} if children else {}

    # ICS format: commands.children is an ordered array of generic nodes
    children: List[Dict[str, Any]] = []

    # Convert lists to <list> nodes with children
    if "lists" in entry:
        for list_cfg in entry["lists"]:
            if not isinstance(list_cfg, dict):
                continue
            # Extract list attributes (name, etc.)
            list_attrs = {k: v for k, v in list_cfg.items() if k != "commands"}
            # Normalize commands within the list
            list_commands = [_normalize_command(cmd) for cmd in list_cfg.get("commands", [])]
            # Create generic node for <list>
            list_node: Dict[str, Any] = {
                "tag": "list",
                "attributes": list_attrs,
                "children": list_commands
            }
            children.append(list_node)

    # Convert mainlist to <mainlist> node with children
    mainlist = entry.get("mainlist")
    if mainlist is not None:
        mainlist_commands = [_normalize_command(cmd) for cmd in mainlist]
        _enforce_fluid_fillbox_defaults(mainlist_commands)
        mainlist_node: Dict[str, Any] = {
            "tag": "mainlist",
            "children": mainlist_commands
        }
        children.append(mainlist_node)

    return {"children": children} if children else {}


def _normalize_command(entry: Any) -> Dict[str, Any]:
    if isinstance(entry, dict) and "type" in entry:
        # Already normalized, but ensure vectors are clean and coerce common text forms
        entry = dict(entry)
        if "children" in entry:
            entry["children"] = [_normalize_vector_in_node(child) for child in entry["children"]]
        if "vector" in entry:
            entry["vector"] = _normalize_vector(entry["vector"])

        cmd = str(entry.get("type") or "").lower()
        text_val = entry.get("text")
        children = entry.get("children") or []

        # Coerce setmk* text like "mk=2" into attributes
        if cmd in {"setmkfluid", "setmkbound"} and isinstance(text_val, str) and text_val:
            txt = text_val.strip()
            if txt.startswith("mk="):
                mk_str = txt.split("=", 1)[1].strip()
                try:
                    mk_num = int(float(mk_str))
                except ValueError:
                    mk_num = None  # keep text if not parseable
                if mk_num is not None:
                    entry.setdefault("attributes", {})["mk"] = mk_num
                    entry.pop("text", None)

        # Coerce drawbox/fillbox text like "x0 y0 z0 x1 y1 z1" into <point> and <size>
        if cmd in {"drawbox", "fillbox"} and isinstance(text_val, str) and text_val and not children:
            parts = [p for p in text_val.replace(",", " ").split() if p]
            if len(parts) == 6:
                try:
                    nums = [float(p) for p in parts]
                except ValueError:
                    nums = []
                if len(nums) == 6:
                    pt = {"x": nums[0], "y": nums[1], "z": nums[2]}
                    sz = {"x": nums[3], "y": nums[4], "z": nums[5]}
                    entry["children"] = [
                        {"tag": "point", "vector": pt},
                        {"tag": "size", "vector": sz},
                    ]
                    entry.pop("text", None)
                    # Ensure drawbox has a <boxfill> child for validation
                    if cmd == "drawbox" and not any((c.get("tag") == "boxfill") for c in entry["children"]):
                        entry["children"].insert(0, {"tag": "boxfill", "text": "solid"})

        return entry

    if isinstance(entry, dict) and len(entry) == 1:
        (command_name, payload), = entry.items()
        command_name = str(command_name).lower()
        payload = payload or {}
    else:
        raise ValueError(f"Unsupported command specification: {entry!r}")

    attributes: Dict[str, Any] = {}
    children: List[Dict[str, Any]] = []

    for key, value in payload.items():
        lower = str(key).lower()
        if lower in {"boxfill", "modefill", "text"}:
            children.append({"tag": key, "text": value})
        elif isinstance(value, dict) and set(value.keys()) <= VECTOR_KEYS:
            children.append({"tag": key, "vector": _normalize_vector(value)})
        elif isinstance(value, dict):
            children.append({"tag": key, "attributes": value})
        elif isinstance(value, list):
            children.append({"tag": key, "children": value})
        else:
            attributes[key] = value

    command_spec: Dict[str, Any] = {"type": command_name}
    if attributes:
        command_spec["attributes"] = attributes
    if children:
        command_spec["children"] = children
    return command_spec

def _values_equivalent(a: Any, b: Any) -> bool:
    a_str = str(a).strip()
    b_str = str(b).strip()
    if a_str == b_str:
        return True
    try:
        return float(a_str) == float(b_str)
    except ValueError:
        return False

def _stringify_plane(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else value
    return str(value)

def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None

def _format_number(value: float) -> str:
    if not math.isfinite(value):
        return str(value)
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(int(rounded))
    return f"{value:.6g}"

def _compose_offset_expression(base: str, offset: float) -> str:
    base_str = base.strip() if isinstance(base, str) else str(base)
    if abs(offset) < 1e-9:
        return base_str
    magnitude = _format_number(abs(offset))
    operator = '-' if offset > 0 else '+'
    return f"({base_str}) {operator} {magnitude}"

def _walk_geometry_nodes(nodes: Iterable[Any]) -> Iterable[Dict[str, Any]]:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        yield node
        child_nodes = node.get("children")
        if isinstance(child_nodes, list):
            yield from _walk_geometry_nodes(child_nodes)

def _enforce_collapsed_axis_guardrails(definition: Dict[str, Any], commands: Dict[str, Any]) -> None:
    pointmin = definition.get("pointmin")
    pointmax = definition.get("pointmax")
    if not isinstance(pointmin, dict) or not isinstance(pointmax, dict):
        return

    planes: Dict[str, str] = {}
    for axis in ("x", "y", "z"):
        if axis not in pointmin or axis not in pointmax:
            continue
        if _values_equivalent(pointmin[axis], pointmax[axis]):
            planes[axis] = _stringify_plane(pointmin[axis])
    if not planes:
        return

    command_children = commands.get("children")
    if not isinstance(command_children, list):
        return

    for node in _walk_geometry_nodes(command_children):
        cmd = str(node.get("type") or node.get("tag") or "").lower()
        if cmd == "fillbox":
            _enforce_fillbox_collapsed_axis(node, planes)
        elif cmd == "drawextrude":
            _enforce_drawextrude_collapsed_axis(node, planes)

def _ensure_fluid_fillboxes_within_volume(definition: Dict[str, Any], commands: Dict[str, Any]) -> None:
    """Shift fluid fillboxes into the declared fluid volume when needed."""
    pointmin = definition.get("pointmin")
    pointmax = definition.get("pointmax")
    if not isinstance(pointmin, dict) or not isinstance(pointmax, dict):
        return

    bounds: Dict[str, Tuple[float, float]] = {}
    for axis in ("x", "y", "z"):
        min_val = _coerce_float(pointmin.get(axis))
        max_val = _coerce_float(pointmax.get(axis))
        if min_val is None or max_val is None:
            continue
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        bounds[axis] = (min_val, max_val)
    if not bounds:
        return

    command_children = commands.get("children")
    if not isinstance(command_children, list):
        return

    for node in command_children:
        if not isinstance(node, dict):
            continue
        tag = str(node.get("tag") or node.get("type") or "").lower()
        if tag == "mainlist":
            sequence = node.get("children")
            if isinstance(sequence, list):
                _relocate_fluid_fillboxes(sequence, bounds)

def _relocate_fluid_fillboxes(commands: List[Dict[str, Any]], bounds: Dict[str, Tuple[float, float]]) -> None:
    current_role: Optional[str] = None
    for entry in commands:
        if not isinstance(entry, dict):
            continue
        cmd_type = str(entry.get("type") or entry.get("tag") or "").lower()
        if cmd_type == "setmkfluid":
            current_role = "fluid"
            continue
        if cmd_type.startswith("setmk"):
            current_role = None if cmd_type == "setmkvoid" else "other"
            continue
        if cmd_type == "fillbox" and current_role == "fluid":
            _clamp_fillbox_to_volume(entry, bounds)

def _clamp_fillbox_to_volume(fillbox: Dict[str, Any], bounds: Dict[str, Tuple[float, float]]) -> None:
    attrs = fillbox.get("attributes")
    if not isinstance(attrs, dict):
        attrs = {}
        fillbox["attributes"] = attrs
    children = fillbox.get("children")
    if not isinstance(children, list):
        children = []
        fillbox["children"] = children

    point_child = None
    size_child = None
    for child in children:
        if not isinstance(child, dict):
            continue
        tag = str(child.get("tag") or "").lower()
        if tag == "point" and point_child is None:
            point_child = child
        elif tag == "size" and size_child is None:
            size_child = child

    if point_child is None:
        point_child = {"tag": "point", "vector": {}}
        children.append(point_child)
    if size_child is None:
        size_child = {"tag": "size", "vector": {}}
        children.append(size_child)

    point_vec = point_child.setdefault("vector", {})
    if not isinstance(point_vec, dict):
        point_vec = {}
        point_child["vector"] = point_vec
    size_vec = size_child.setdefault("vector", {})
    if not isinstance(size_vec, dict):
        size_vec = {}
        size_child["vector"] = size_vec

    for axis in ("x", "y", "z"):
        if axis not in bounds:
            continue
        min_bound, max_bound = bounds[axis]
        axis_span = max_bound - min_bound
        original_point_value = point_vec.get(axis)
        if axis_span <= 1e-9:
            plane_str = _format_number(min_bound)
            attrs[axis] = plane_str
            if original_point_value is None or (isinstance(original_point_value, str) and not original_point_value.strip()):
                point_vec[axis] = plane_str
            continue

        allowed_min = min_bound - FILLBOX_OVERSHOOT_MARGIN
        allowed_max = max_bound + FILLBOX_OVERSHOOT_MARGIN
        allowed_span = allowed_max - allowed_min

        size_num = _coerce_float(size_vec.get(axis))
        if size_num is None or size_num <= 0:
            continue

        point_num = _coerce_float(original_point_value)
        if point_num is None:
            point_num = _coerce_float(attrs.get(axis))
        inferred_point = False
        if point_num is None:
            point_num = min_bound
            inferred_point = True

        start = point_num
        start_changed = False

        if size_num > allowed_span:
            size_num = allowed_span

        if start < allowed_min:
            start = allowed_min
            start_changed = True

        if start + size_num > allowed_max:
            start = allowed_max - size_num
            start_changed = True

        if start < allowed_min:
            start = allowed_min
            start_changed = True

        end = start + size_num
        if end > allowed_max:
            end = allowed_max
            size_num = end - start

        size_vec[axis] = _format_number(size_num)

        if start_changed or inferred_point or original_point_value is None:
            formatted_start = _format_number(start)
            point_vec[axis] = formatted_start
            attrs[axis] = formatted_start


def _enforce_fillbox_collapsed_axis(node: Dict[str, Any], planes: Dict[str, str]) -> None:
    attrs = node.setdefault("attributes", {})
    children = node.setdefault("children", [])

    point_child = None
    size_child = None
    for child in children:
        tag = str(child.get("tag") or "").lower()
        if tag == "point" and point_child is None:
            point_child = child
        elif tag == "size" and size_child is None:
            size_child = child

    if point_child is None:
        point_child = {"tag": "point", "vector": {}}
        children.append(point_child)
    point_vec = point_child.setdefault("vector", {})
    if not isinstance(point_vec, dict):
        point_vec = {}
        point_child["vector"] = point_vec

    if size_child is None:
        size_child = {"tag": "size", "vector": {}}
        children.append(size_child)
    size_vec = size_child.setdefault("vector", {})
    if not isinstance(size_vec, dict):
        size_vec = {}
        size_child["vector"] = size_vec

    for axis, plane in planes.items():
        plane_str = _stringify_plane(plane)

        raw_size = size_vec.get(axis)
        if raw_size is None or (isinstance(raw_size, str) and not raw_size.strip()):
            raw_size = DEFAULT_COLLAPSED_AXIS_THICKNESS

        thickness_num = _coerce_float(raw_size)
        if thickness_num is None or thickness_num <= 0:
            raw_size = DEFAULT_COLLAPSED_AXIS_THICKNESS
            thickness_num = _coerce_float(raw_size)

        if thickness_num is not None:
            size_vec[axis] = _format_number(thickness_num)
        else:
            size_vec[axis] = _stringify_plane(raw_size)

        plane_num = _coerce_float(plane_str)
        if plane_num is not None and thickness_num is not None:
            point_val = plane_num - thickness_num / 2.0
            point_str = _format_number(point_val)
            attrs[axis] = point_str
            point_vec[axis] = point_str
        else:
            fallback_thickness = thickness_num if thickness_num is not None else _coerce_float(DEFAULT_COLLAPSED_AXIS_THICKNESS) or 1.0
            point_expr = _compose_offset_expression(plane_str, fallback_thickness / 2.0)
            attrs[axis] = point_expr
            point_vec[axis] = point_expr

def _enforce_drawextrude_collapsed_axis(node: Dict[str, Any], planes: Dict[str, str]) -> None:
    children = node.get("children")
    if not isinstance(children, list):
        return

    extrude_child = None
    for child in children:
        if str(child.get("tag") or "").lower() == "extrude":
            extrude_child = child
            break
    if extrude_child is None:
        extrude_child = {"tag": "extrude", "vector": {}}
        children.insert(0, extrude_child)

    extrude_vec = extrude_child.setdefault("vector", {})
    if not isinstance(extrude_vec, dict):
        extrude_vec = {}
        extrude_child["vector"] = extrude_vec

    for axis in planes:
        extrude_vec[axis] = DEFAULT_COLLAPSED_AXIS_THICKNESS

    for child in children:
        if not isinstance(child, dict):
            continue
        tag = str(child.get("tag") or "").lower()
        if tag in {"point", "point0", "point1", "point2", "pointref", "endpoint"}:
            vec = child.setdefault("vector", {})
            if not isinstance(vec, dict):
                vec = {}
                child["vector"] = vec
            for axis, plane in planes.items():
                vec[axis] = plane
def _enforce_fluid_fillbox_defaults(commands: List[Dict[str, Any]]) -> None:
    current_role: Optional[str] = None
    for entry in commands:
        cmd_type = str(entry.get("type") or entry.get("tag") or "").lower()
        if cmd_type == "setmkfluid":
            current_role = "fluid"
            continue
        if cmd_type.startswith("setmk"):
            current_role = None if cmd_type == "setmkvoid" else "other"
            continue
        if cmd_type != "fillbox":
            continue
        if current_role != "fluid":
            continue
        children = entry.setdefault("children", [])
        modefill = None
        point_vec = None
        for child in children:
            tag = str(child.get("tag") or "").lower()
            if tag == "modefill":
                modefill = child
            elif tag == "point":
                vector = child.get("vector")
                if isinstance(vector, dict):
                    point_vec = vector
        if modefill is None:
            modefill = {"tag": "modefill"}
            children.insert(0, modefill)
        modefill["text"] = "void"
        if isinstance(point_vec, dict):
            attrs = entry.setdefault("attributes", {})
            for axis in ("x", "y", "z"):
                if axis in point_vec and axis not in attrs:
                    attrs[axis] = point_vec[axis]

def _canonicalize_execution_key(name: Any) -> Tuple[str, bool]:
    if not isinstance(name, str):
        return str(name), False
    normalized = name.strip().lower()
    simplified = "".join(ch for ch in normalized if ch not in {"_", "-"})
    canonical = EXECUTION_KEY_ALIASES.get(simplified)
    if canonical:
        return canonical, True
    return name, False


def _normalize_execution_children_order(order: Any, warnings: List[str]) -> Optional[List[Any]]:
    if order is None:
        return None
    if not isinstance(order, list):
        warnings.append("children_order ignored: expected list")
        return None
    normalized: List[Any] = []
    for item in order:
        if isinstance(item, str):
            canonical, recognized = _canonicalize_execution_key(item)
            normalized.append(canonical if recognized else item)
        else:
            normalized.append(item)
    return normalized


def _normalize_special_children_plan(plan: Any, warnings: List[str]) -> Optional[List[Dict[str, Any]]]:
    if plan is None:
        return None
    if not isinstance(plan, list):
        warnings.append("special_children ignored: expected list")
        return None
    normalized_plan: List[Dict[str, Any]] = []
    for entry in plan:
        if not isinstance(entry, dict):
            normalized_plan.append(entry)
            continue
        normalized_entry = copy.deepcopy(entry)
        if normalized_entry.get("type") == "known":
            key_value = normalized_entry.get("key")
            if isinstance(key_value, str):
                canonical, recognized = _canonicalize_execution_key(key_value)
                if recognized and canonical in EXECUTION_SPECIAL_CHILD_KEYS:
                    normalized_entry["key"] = canonical
        normalized_plan.append(normalized_entry)
    return normalized_plan


def _merge_extra_nodes(exec_cfg: Dict[str, Any], nodes: List[Dict[str, Any]], warnings: List[str]) -> None:
    if not nodes:
        return
    existing = exec_cfg.get("extra_nodes")
    if existing is None:
        exec_cfg["extra_nodes"] = list(nodes)
    elif isinstance(existing, list):
        existing.extend(nodes)
    else:
        warnings.append("extra_nodes preserved but could not merge additional nodes")


def _normalize_execution(entry: Any) -> NormalizationResult:
    if not isinstance(entry, dict):
        raise ValueError("execution section must be an object")

    exec_cfg: Dict[str, Any] = {}
    warnings: List[str] = []

    canonical_entries: Dict[str, Any] = {}
    source_keys: Dict[str, str] = {}
    recognized_flags: Dict[str, bool] = {}

    for raw_key, value in entry.items():
        canonical_key, recognized = _canonicalize_execution_key(raw_key)
        str_key = str(raw_key)
        if canonical_key in canonical_entries:
            prev_source = source_keys[canonical_key]
            if prev_source != str_key:
                if canonical_key == str_key:
                    warnings.append(
                        f"execution key '{prev_source}' duplicates '{canonical_key}'; kept '{canonical_key}'"
                    )
                    canonical_entries[canonical_key] = value
                    source_keys[canonical_key] = str_key
                else:
                    warnings.append(
                        f"execution key '{str_key}' duplicates '{prev_source}'; kept '{prev_source}'"
                    )
            else:
                canonical_entries[canonical_key] = value
        else:
            canonical_entries[canonical_key] = value
            source_keys[canonical_key] = str_key
        recognized_flags[canonical_key] = recognized_flags.get(canonical_key, False) or recognized

    extra_nodes_entry = canonical_entries.pop("extra_nodes", None)
    parameters_entry = canonical_entries.pop("parameters", None)

    parameters_children_present = "parameters_children" in canonical_entries
    parameters_children_entry = (
        canonical_entries.pop("parameters_children", None) if parameters_children_present else None
    )
    parameters_order_present = "parameters_order" in canonical_entries
    parameters_order_entry = (
        canonical_entries.pop("parameters_order", None) if parameters_order_present else None
    )
    children_order_present = "children_order" in canonical_entries
    children_order_entry = (
        canonical_entries.pop("children_order", None) if children_order_present else None
    )
    special_children_present = "special_children" in canonical_entries
    special_children_entry = (
        canonical_entries.pop("special_children", None) if special_children_present else None
    )

    gauges_entry = canonical_entries.pop("gauges", None)
    timeout_entry = canonical_entries.pop("timeout", None)
    special_entry = canonical_entries.pop("special", None)
    simulationdomain_entry = canonical_entries.pop("simulationdomain", None)

    special_sections: Dict[str, Any] = {}
    for section_key in EXECUTION_SPECIAL_SECTION_KEYS:
        if section_key in canonical_entries:
            special_sections[section_key] = canonical_entries.pop(section_key)

    if extra_nodes_entry is not None:
        if isinstance(extra_nodes_entry, list):
            exec_cfg["extra_nodes"] = list(extra_nodes_entry)
        else:
            exec_cfg["extra_nodes"] = extra_nodes_entry

    if parameters_entry is not None:
        param_result = _normalize_parameters(parameters_entry)
        exec_cfg["parameters"] = param_result.parameters
        warnings.extend(param_result.warnings)

        if parameters_order_present:
            exec_cfg["parameters_order"] = parameters_order_entry
        if parameters_children_present:
            exec_cfg["parameters_children"] = parameters_children_entry
        elif param_result.parameters:
            exec_cfg["parameters_children"] = _synthesize_parameters_children_plan(
                param_result.parameters, param_result.extra_nodes
            )

        _merge_extra_nodes(exec_cfg, param_result.extra_nodes, warnings)
    else:
        if parameters_order_present:
            exec_cfg["parameters_order"] = parameters_order_entry
        if parameters_children_present:
            exec_cfg["parameters_children"] = parameters_children_entry

    if gauges_entry is not None:
        if isinstance(gauges_entry, list):
            exec_cfg["gauges"] = [_normalize_gauge(g) for g in gauges_entry]
        else:
            exec_cfg["gauges"] = gauges_entry

    if timeout_entry is not None:
        exec_cfg["timeout"] = timeout_entry

    for section_key, section_value in special_sections.items():
        exec_cfg[section_key] = section_value

    if special_entry is not None:
        exec_cfg["special"] = special_entry

    if children_order_present:
        normalized_children_order = _normalize_execution_children_order(children_order_entry, warnings)
        if normalized_children_order is not None:
            exec_cfg["children_order"] = normalized_children_order

    if special_children_present:
        normalized_special_children = _normalize_special_children_plan(special_children_entry, warnings)
        if normalized_special_children is not None:
            exec_cfg["special_children"] = normalized_special_children

    if simulationdomain_entry is not None:
        extra_node = _normalize_simulation_domain(simulationdomain_entry)
        if extra_node:
            _merge_extra_nodes(exec_cfg, [extra_node], warnings)

    for key, value in canonical_entries.items():
        exec_cfg[key] = value
        if not recognized_flags.get(key, False):
            warnings.append(f"execution key '{source_keys.get(key, key)}' preserved without normalization")

    return NormalizationResult(exec_cfg, warnings)

def _normalize_parameters(entry: Any) -> ParameterNormalizationResult:
    warnings: List[str] = []
    parameters: Dict[str, Any] = {}
    extra_nodes: List[Dict[str, Any]] = []

    simulationdomain = None
    parameter_source = entry

    if isinstance(entry, dict):
        simulationdomain = entry.get("simulationdomain")
        if "parameter" in entry:
            parameter_source = entry["parameter"]

    if isinstance(parameter_source, list):
        for param in parameter_source:
            if not isinstance(param, dict) or "key" not in param:
                warnings.append(f"Ignored malformed parameter entry: {param!r}")
                continue
            key = param["key"]
            value = _coerce_scalar(param.get("value"))
            attrs = {k: v for k, v in param.items() if k not in {"key", "value"}}
            if attrs:
                attrs["value"] = value
                parameters[key] = attrs
            else:
                parameters[key] = value
    elif isinstance(parameter_source, dict):
        for key, value in parameter_source.items():
            if key == "simulationdomain":
                simulationdomain = value
                continue
            parameters[key] = _coerce_scalar(value)
    else:
        warnings.append("parameters ignored: expected list or object")

    if simulationdomain:
        extra = _normalize_simulation_domain(simulationdomain)
        if extra:
            extra_nodes.append(extra)

    return ParameterNormalizationResult(parameters=parameters, warnings=warnings, extra_nodes=extra_nodes)




def _extract_normals_specs_from_list(entries: List[Any]) -> Tuple[List[Dict[str, Any]], List[Any]]:
    normals: List[Dict[str, Any]] = []
    remaining: List[Any] = []
    for entry in entries:
        if _is_normals_spec(entry):
            normals.append(entry)
        else:
            remaining.append(entry)
    return normals, remaining

def _merge_normals(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(existing)
    for key, value in incoming.items():
        if key == "extra":
            if not value:
                continue
            extras = merged.setdefault("extra", [])
            if isinstance(value, list):
                extras.extend(value)
            else:
                extras.append(value)
        elif key == "norgeometry":
            if not isinstance(value, dict):
                continue
            current_geo = merged.get("norgeometry")
            if not isinstance(current_geo, dict):
                merged["norgeometry"] = copy.deepcopy(value)
                continue
            for sub_key, sub_value in value.items():
                if sub_key == "extra":
                    if not sub_value:
                        continue
                    geo_extras = current_geo.setdefault("extra", [])
                    if isinstance(sub_value, list):
                        geo_extras.extend(sub_value)
                    else:
                        geo_extras.append(sub_value)
                elif sub_key not in current_geo or current_geo[sub_key] in (None, "", []):
                    current_geo[sub_key] = copy.deepcopy(sub_value)
        else:
            if key not in merged or merged[key] in (None, "", []):
                merged[key] = copy.deepcopy(value)
    return merged

def _promote_normals_from_execution(config: Dict[str, Any], warnings: List[str]) -> None:
    execution = config.get("execution")
    normals_specs: List[Dict[str, Any]] = []
    moved = False

    if isinstance(execution, dict):
        special = execution.get("special")
        if isinstance(special, list):
            filtered_special: List[Any] = []
            for entry in special:
                if _is_normals_spec(entry):
                    normals_specs.append(entry)
                    moved = True
                else:
                    filtered_special.append(entry)
            if filtered_special:
                execution["special"] = filtered_special
            else:
                execution.pop("special", None)
        elif _is_normals_spec(special):
            if isinstance(special, dict):
                normals_specs.append(special)
            moved = True
            execution.pop("special", None)

        children_order = execution.get("children_order")
        if isinstance(children_order, list):
            special_content_keys = {"special", "special_children", "gauges", "timeout"} | set(EXECUTION_SPECIAL_SECTION_KEYS)
            has_special_content = False
            for key in special_content_keys:
                if key == "special_children":
                    value = execution.get(key)
                    if isinstance(value, list) and value:
                        has_special_content = True
                        break
                else:
                    if execution.get(key):
                        has_special_content = True
                        break
            if not has_special_content:
                filtered_order = [item for item in children_order if item != "special"]
                if filtered_order:
                    execution["children_order"] = filtered_order
                else:
                    execution.pop("children_order", None)

        special_children = execution.get("special_children")
        if isinstance(special_children, list):
            filtered_children: List[Dict[str, Any]] = []
            for child in special_children:
                if child.get("type") == "generic" and _is_normals_spec(child.get("spec")):
                    spec = child.get("spec")
                    if isinstance(spec, dict):
                        normals_specs.append(spec)
                        moved = True
                    continue
                if child.get("type") == "section" and str(child.get("key", "")).lower() == "normals":
                    moved = True
                    continue
                filtered_children.append(child)
            if filtered_children:
                execution["special_children"] = filtered_children
            else:
                execution.pop("special_children", None)

    extras_raw = config.get("casedef_extra")
    extras_list: List[Any] = []
    if isinstance(extras_raw, list):
        extras_list = list(extras_raw)
    elif isinstance(extras_raw, (tuple, set)):
        extras_list = list(extras_raw)
    elif extras_raw is not None:
        extras_list = [extras_raw]

    if extras_list:
        extra_normals, filtered_extras = _extract_normals_specs_from_list(extras_list)
        if extra_normals:
            normals_specs.extend(extra_normals)
            moved = True
        if filtered_extras:
            config["casedef_extra"] = filtered_extras
        else:
            config.pop("casedef_extra", None)

    existing_normals = config.get("normals")
    if normals_specs:
        normalized_normals = _normalize_normals(normals_specs[0])
        if isinstance(existing_normals, dict):
            normalized_normals = _merge_normals(existing_normals, normalized_normals)
        config["normals"] = normalized_normals
        if len(normals_specs) > 1:
            extras_bucket = config["normals"].setdefault("extra", [])
            for extra_spec in normals_specs[1:]:
                extras_bucket.append(extra_spec)
    elif existing_normals is not None:
        config["normals"] = _normalize_normals(existing_normals)

    if "normals" in config:
        config["normals"] = _normalize_normals(config["normals"])
        _ensure_normals_section_plan(config)
    _ensure_floatings_section_plan(config)
    _ensure_floatings_have_descriptor(config, warnings)
    if moved and config.get("normals"):
        warnings.append("Moved normals block from execution.special to top-level normals")
def _ensure_normals_section_plan(config: Dict[str, Any]) -> None:
    """Insert a normals section entry after geometry in casedef_children when needed."""
    children_plan = config.get("casedef_children")
    if not isinstance(children_plan, list):
        return

    for entry in children_plan:
        if isinstance(entry, dict) and entry.get("type") == "section":
            key = entry.get("key")
            if isinstance(key, str) and key.lower() == "normals":
                return

    insertion_index = len(children_plan)
    for idx, entry in enumerate(children_plan):
        if isinstance(entry, dict) and entry.get("type") == "section":
            key = entry.get("key")
            if isinstance(key, str) and key.lower() == "geometry":
                insertion_index = idx + 1
                break

    children_plan.insert(insertion_index, {"type": "section", "key": "normals"})

def _normalize_floatings(raw_floatings: Any, warnings: List[str]) -> Any:
    data = copy.deepcopy(raw_floatings)
    _sanitize_floatings_nodes(data, warnings)
    return data


def _sanitize_floatings_nodes(node: Any, warnings: List[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "floating":
            _strip_bodyfloating_child(node, warnings)
            _prune_unsupported_floating_children(node, warnings)
        for value in node.values():
            if isinstance(value, (dict, list)):
                _sanitize_floatings_nodes(value, warnings)
    elif isinstance(node, list):
        for item in node:
            _sanitize_floatings_nodes(item, warnings)


def _strip_bodyfloating_child(floating: Dict[str, Any], warnings: List[str]) -> None:
    children = floating.get("children")
    if not isinstance(children, list):
        return
    kept_children: List[Dict[str, Any]] = []
    bodyfloating_removed = False
    for child in children:
        if isinstance(child, dict) and str(child.get("tag", "")).lower() == "bodyfloating":
            _merge_bodyfloating_into_attributes(floating, child, warnings)
            bodyfloating_removed = True
        else:
            kept_children.append(child)
    if bodyfloating_removed:
        if kept_children:
            floating["children"] = kept_children
        else:
            floating.pop("children", None)
        warnings.append("Dropped unsupported bodyfloating child from floatings and merged its attributes")


def _merge_bodyfloating_into_attributes(floating: Dict[str, Any], child: Dict[str, Any], warnings: List[str]) -> None:
    target_attrs = floating.setdefault("attributes", {})
    merged_attrs: Dict[str, Any] = {}
    child_attrs = child.get("attributes")
    if isinstance(child_attrs, dict):
        merged_attrs.update(child_attrs)
    for key, value in child.items():
        if key in {"tag", "attributes", "children", "extra", "text", "vector"}:
            continue
        merged_attrs[key] = value
    if child.get("children"):
        warnings.append("Ignoring nested children on bodyfloating entry under floatings")
    if "vector" in child:
        warnings.append("Ignoring vector on bodyfloating entry under floatings")
    for key, value in merged_attrs.items():
        if key not in target_attrs:
            target_attrs[key] = value
        elif target_attrs[key] != value:
            warnings.append(f"bodyfloating attribute '{key}' already present on floating; keeping existing value")


ALLOWED_FLOATING_CHILD_TAGS = {
    "massbody",
    "masspart",
    "center",
    "inertia",
    "inertiafull",
    "inertiatensor",
    "tensor",
    "hydroforce",
    "force",
    "torque",
    "linearvel",
    "angularvel",
}


def _prune_unsupported_floating_children(floating: Dict[str, Any], warnings: List[str]) -> None:
    children = floating.get("children")
    if not isinstance(children, list):
        return
    kept: List[Dict[str, Any]] = []
    removed_any = False
    for child in children:
        tag = None
        if isinstance(child, dict):
            tag = child.get("tag") or child.get("type")
        if tag is None:
            kept.append(child)
            continue
        tag_lower = str(tag).lower()
        if tag_lower in ALLOWED_FLOATING_CHILD_TAGS:
            kept.append(child)
        else:
            removed_any = True
            warnings.append(f"Ignoring unsupported floating child '{tag}'")
    if removed_any:
        if kept:
            floating["children"] = kept
        else:
            floating.pop("children", None)


def _enforce_single_floating_descriptor(floating: Dict[str, Any], warnings: List[str]) -> None:
    """Ensure a floating entry exposes at most one descriptor (massbody, relativeweight, rhopbody)."""
    attrs = floating.get("attributes")
    if not isinstance(attrs, dict):
        attrs = {}
        floating["attributes"] = attrs

    children_obj = floating.get("children")
    children_list = children_obj if isinstance(children_obj, list) else None

    massbody_nodes: List[Dict[str, Any]] = []
    if children_list:
        for child in children_list:
            if not isinstance(child, dict):
                continue
            tag = child.get("tag") or child.get("type")
            if isinstance(tag, str) and tag.lower() == "massbody":
                massbody_nodes.append(child)

    preferred = None
    if massbody_nodes:
        preferred = "massbody"
    elif "relativeweight" in attrs:
        preferred = "relativeweight"
    elif "rhopbody" in attrs:
        preferred = "rhopbody"

    if preferred is None:
        return

    removed_notes: List[str] = []

    if preferred == "massbody":
        if len(massbody_nodes) > 1 and children_list is not None:
            for extra in massbody_nodes[1:]:
                if extra in children_list:
                    children_list.remove(extra)
            removed_notes.append("duplicate massbody entries")
        for key in ("relativeweight", "rhopbody"):
            if key in attrs:
                attrs.pop(key, None)
                removed_notes.append(key)
    else:
        if massbody_nodes and children_list is not None:
            for node in massbody_nodes:
                if node in children_list:
                    children_list.remove(node)
            removed_notes.append("massbody")
        other_key = "relativeweight" if preferred == "rhopbody" else "rhopbody"
        if other_key in attrs:
            attrs.pop(other_key, None)
            removed_notes.append(other_key)

    if children_list is not None and not children_list:
        floating.pop("children", None)

    if removed_notes:
        removed_text = ", ".join(removed_notes)
        warnings.append(f"Floating entry had multiple descriptors; kept {preferred} and removed {removed_text}")


def _ensure_floatings_have_descriptor(config: Dict[str, Any], warnings: List[str]) -> None:
    floatings = config.get("floatings")
    if not isinstance(floatings, list):
        return
    default_rhop = _extract_default_rhop_value(config)
    for floating in floatings:
        if not isinstance(floating, dict):
            continue
        _enforce_single_floating_descriptor(floating, warnings)
        attrs = floating.get("attributes")
        if not isinstance(attrs, dict):
            attrs = {}
            floating["attributes"] = attrs
        has_rhop = any(key in attrs for key in ("rhopbody", "relativeweight"))
        children = floating.get("children")
        has_massbody = False
        if isinstance(children, list):
            for child in children:
                if not isinstance(child, dict):
                    continue
                tag = child.get("tag") or child.get("type")
                if isinstance(tag, str) and tag.lower() == "massbody":
                    has_massbody = True
                    break
        if has_rhop or has_massbody:
            continue
        if default_rhop is not None:
            floating.setdefault("attributes", {})["rhopbody"] = default_rhop
            warnings.append("Added rhopbody to floating because no massbody or relativeweight was provided")
        else:
            warnings.append("Floating entry missing massbody, relativeweight, or rhopbody")

def _extract_default_rhop_value(config: Dict[str, Any]) -> Optional[float]:
    constants = config.get("constants")
    if not isinstance(constants, dict):
        return None
    candidate = None
    for key in ("rhopbody", "rhop0", "rho0"):
        entry = constants.get(key)
        if entry is None:
            continue
        candidate = entry
        break
    if candidate is None:
        entry = constants.get("rhop0")
        if entry is not None:
            candidate = entry
    if candidate is None:
        return None
    value = None
    if isinstance(candidate, dict):
        attrs = candidate.get("attributes")
        if isinstance(attrs, dict) and "value" in attrs:
            value = attrs["value"]
        elif "value" in candidate:
            value = candidate["value"]
    else:
        value = candidate
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _ensure_floatings_section_plan(config: Dict[str, Any]) -> None:
    """Ensure casedef_children carries a floatings plan entry when floatings exist."""
    children_plan = config.get("casedef_children")
    if not isinstance(children_plan, list):
        return

    floatings_block = config.get("floatings")
    if not _has_floatings_content(floatings_block):
        return

    if _find_last_section_index(children_plan, {"floatings"}) is not None:
        return

    insertion_index = _find_last_section_index(children_plan, {"initials"})
    if insertion_index is not None:
        insertion_index += 1
    else:
        fallback = _find_last_section_index(children_plan, {"normals", "geometry"})
        if fallback is not None:
            insertion_index = fallback + 1
        else:
            fallback = _find_last_section_index(children_plan, {"mkconfig", "constants"})
            if fallback is not None:
                insertion_index = fallback + 1
            else:
                insertion_index = len(children_plan)

    children_plan.insert(insertion_index, {"type": "section", "key": "floatings"})

def _find_last_section_index(children_plan: List[Any], targets: set[str]) -> Optional[int]:
    for idx in range(len(children_plan) - 1, -1, -1):
        entry = children_plan[idx]
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "section":
            continue
        key = entry.get("key")
        if isinstance(key, str) and key.lower() in targets:
            return idx
    return None

def _has_floatings_content(block: Any) -> bool:
    if block is None:
        return False
    if isinstance(block, list):
        return len(block) > 0
    if isinstance(block, dict):
        return bool(block)
    return bool(block)

def _normalize_simulation_domain(entry: Any) -> Dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None

    node: Dict[str, Any] = {"tag": "simulationdomain"}
    attrs: Dict[str, Any] = {}
    children: List[Dict[str, Any]] = []
    for key, value in entry.items():
        if key.startswith("_"):
            attrs[key.lstrip("_")] = value
        elif isinstance(value, dict):
            children.append({"tag": key, "attributes": value})
        else:
            attrs[key] = value
    if attrs:
        node["attributes"] = attrs
    if children:
        node["children"] = children
    return node


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (int, float, str, bool))


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return value
        try:
            if any(ch in raw for ch in (".", "e", "E")):
                return float(raw)
            return int(raw)
        except ValueError:
            return value
    return value


def _normalize_vector(vector: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure vector contains only x, y, z keys."""
    return {axis: vector[axis] for axis in ("x", "y", "z") if axis in vector}


def _normalize_vector_in_node(node: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively normalize vectors in a generic node."""
    if "vector" in node:
        node["vector"] = _normalize_vector(node["vector"])
    if "children" in node and isinstance(node["children"], list):
        node["children"] = [_normalize_vector_in_node(child) for child in node["children"]]
    return node


def _synthesize_parameters_children_plan(
    parameters: Dict[str, Any], extra_nodes: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Synthesize parameters_children plan for ICS compatibility."""
    plan: List[Dict[str, Any]] = []
    
    # Add all parameters in sorted order for deterministic output
    for key in sorted(parameters.keys()):
        plan.append({"type": "parameter", "key": key})
    
    # Add extra nodes (e.g., simulationdomain)
    for node in extra_nodes:
        plan.append({"type": "generic", "spec": node})
    
    return plan


def _normalize_gauge(gauge: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a gauge entry and synthesize children_plan."""
    if not isinstance(gauge, dict):
        return gauge
    
    normalized = dict(gauge)
    
    # Normalize vectors in start/mid/end
    for key in ("start", "mid", "end"):
        if key in normalized and isinstance(normalized[key], dict):
            normalized[key] = _normalize_vector(normalized[key])
    
    # Normalize children if present
    if "children" in normalized and isinstance(normalized["children"], list):
        normalized["children"] = [_normalize_vector_in_node(child) for child in normalized["children"]]
    
    # Synthesize children_plan if not present
    if "children_plan" not in normalized:
        plan: List[Dict[str, Any]] = []
        
        # Map standard point keys
        if "start" in normalized:
            plan.append({"type": "mapped", "key": "start", "tag": "point0"})
        if "mid" in normalized:
            plan.append({"type": "mapped", "key": "mid", "tag": "point1"})
        if "end" in normalized:
            plan.append({"type": "mapped", "key": "end", "tag": "point2"})
        
        # Add generic children (e.g., pointdp)
        for child in normalized.get("children", []):
            plan.append({"type": "generic", "spec": child})
        
        if plan:
            normalized["children_plan"] = plan
    
    return normalized







def promote_normals_from_execution(config: Dict[str, Any]) -> bool:
    """Public helper to relocate normals nodes from execution.special."""
    if not isinstance(config, dict):
        return False

    collector: List[str] = []
    _promote_normals_from_execution(config, collector)
    return any(msg.startswith("Moved normals block from execution.special") for msg in collector)

