"""Utilities to normalize loosely-structured generator JSON into the schema
expected by AutoXml_script.generate_xml."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


CANONICAL_CONFIG_KEYS = {
    "case_attributes",
    "casedef_attributes",
    "constants",
    "mkconfig",
    "patterns",
    "geometry",
    "initials",
    "floatings",
    "motion",
    "casedef_extra",
    "execution",
    "execution_attributes",
}

VECTOR_KEYS = {"x", "y", "z"}


@dataclass
class NormalizationResult:
    config: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


@dataclass
class ParameterNormalizationResult:
    parameters: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    extra_nodes: List[Dict[str, Any]] = field(default_factory=list)


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

    if "predefinition" in block:
        geometry["predefinition"] = block["predefinition"]
    if "extra" in block:
        geometry["extra"] = block["extra"]
    if "objects" in block and "commands" not in geometry:
        geometry["objects"] = block["objects"]
    return geometry


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


def _normalize_execution(entry: Any) -> NormalizationResult:
    if not isinstance(entry, dict):
        raise ValueError("execution section must be an object")

    exec_cfg: Dict[str, Any] = {}
    warnings: List[str] = []

    if "parameters" in entry:
        params_entry = entry["parameters"]
        param_result = _normalize_parameters(params_entry)
        exec_cfg["parameters"] = param_result.parameters
        warnings.extend(param_result.warnings)
        if param_result.extra_nodes:
            exec_cfg.setdefault("extra_nodes", []).extend(param_result.extra_nodes)
        # Synthesize parameters_children plan if not already present
        if "parameters_children" not in entry and param_result.parameters:
            exec_cfg["parameters_children"] = _synthesize_parameters_children_plan(
                param_result.parameters, param_result.extra_nodes
            )

    # Normalize gauges and synthesize children_plan
    if "gauges" in entry:
        gauges_entry = entry["gauges"]
        if isinstance(gauges_entry, list):
            exec_cfg["gauges"] = [_normalize_gauge(g) for g in gauges_entry]
        else:
            exec_cfg["gauges"] = gauges_entry

    for key in ("timeout", "special", "extra_nodes"):
        if key in entry:
            exec_cfg[key] = entry[key]

    if "simulationdomain" in entry:
        extra = _normalize_simulation_domain(entry["simulationdomain"])
        if extra:
            exec_cfg.setdefault("extra_nodes", []).append(extra)

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
