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
    if isinstance(entry, dict):
        attrs = {}
        children: List[Dict[str, Any]] = []
        for key, value in entry.items():
            if key in {"dp", "units_comment", "comment"} and _is_scalar(value):
                attrs[key] = value
            elif key in {"attributes", "children"}:
                if key == "attributes":
                    attrs.update(value)
                else:
                    children.extend(value)
            elif key.startswith("_"):
                continue
            elif isinstance(value, dict) and set(value.keys()) <= VECTOR_KEYS:
                children.append({"tag": key, "vector": value})
            else:
                children.append({"tag": key, "attributes": value if isinstance(value, dict) else {"value": value}})

        definition = {"attributes": attrs}
        if children:
            definition["children"] = children
        return definition

    raise ValueError("geometry.definition must be an object")


def _normalize_geometry_commands(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("geometry.commands must be an object")

    commands_out: Dict[str, Any] = {}
    if "lists" in entry:
        lists = []
        for list_cfg in entry["lists"]:
            if not isinstance(list_cfg, dict):
                continue
            # Accept both 'items' (preferred) and 'commands' (legacy) and normalize to 'items'
            list_out: Dict[str, Any] = {k: v for k, v in list_cfg.items() if k not in {"commands", "items"}}
            raw_cmds = list_cfg.get("items", list_cfg.get("commands", []))
            cmds = [_normalize_command(cmd) for cmd in (raw_cmds or [])]
            # Normalize to 'items' to match generator expectations in generate_xml.py
            existing_items = list_out.get("items")
            if isinstance(existing_items, list):
                existing_items.extend(cmds)
                list_out["items"] = existing_items
            else:
                list_out["items"] = cmds
            lists.append(list_out)
        if lists:
            commands_out["lists"] = lists

    mainlist = entry.get("mainlist")
    if mainlist is not None:
        commands_out["mainlist"] = [_normalize_command(cmd) for cmd in mainlist]
    return commands_out


def _normalize_command(entry: Any) -> Dict[str, Any]:
    if isinstance(entry, dict) and "type" in entry:
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
            children.append({"tag": key, "vector": value})
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

    for key in ("gauges", "timeout", "special", "extra_nodes"):
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
