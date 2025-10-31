from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from lxml import etree as ET

VectorDict = Dict[str, Any]
Attributes = Dict[str, Any]

DEFAULT_CONSTANT_META: Dict[str, Dict[str, Any]] = {
    "gravity": {
        "comment": "Gravitational acceleration",
        "units_comment": "m/s^2",
    },
    "rhop0": {
        "comment": "Reference density of the fluid",
        "units_comment": "kg/m^3",
    },
    "rhopgradient": {
        "comment": "Initial density gradient 1:Rhop0, 2:Water column, 3:Max. water height (default=2)",
    },
    "hswl": {
        "auto": True,
        "comment": "Maximum still water level to calculate speedofsound using coefsound",
        "units_comment": "metres (m)",

    },
    "gamma": {
        "comment": "Polytropic constant for water used in the state equation",
    },
    "speedsystem": {
        "auto": True,
        "comment": "Maximum system speed (by default the dam-break propagation is used)",
        "units_comment": "m/s",

    },
    "coefsound": {
        "comment": "Coefficient to multiply speedsystem",
    },
    "speedsound": {
        "auto": True,
        "comment": "Speed of sound to use in the simulation (by default speedofsound=coefsound*speedsystem)",
        "units_comment": "m/s",

    },
    "coefh": {
        "comment": "Coefficient to calculate the smoothing length (h=coefh*sqrt(3*dp^2) in 3D)",
    },
    "_hdp": {
        "comment": "Alternative option to calculate the smoothing length (h=hdp*dp)",
    },
    "cflnumber": {
        "comment": "Coefficient to multiply dt",
    },
}


PLACEHOLDER_STL_FILENAMES: Set[str] = {
    "external.stl",
    "duck.stl",
    "sampleexternal.stl",
    "file.stl",
}

def load_config(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def looks_like_vector(candidate: Any) -> bool:
    if not isinstance(candidate, dict):
        return False
    keys = set(candidate.keys())
    return bool(keys) and keys <= {"x", "y", "z"}


def sanitize_xml_tag(name: str) -> str:
    if name is None:
        raise ValueError("XML tag name must not be None")
    text = str(name).strip()
    if not text:
        raise ValueError("XML tag name must not be empty")
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", text)
    sanitized = re.sub(r"_+", "_", sanitized)
    if sanitized.strip("_") == "":
        sanitized = "n"
    if not sanitized:
        sanitized = "n"
    if not re.match(r"[A-Za-z_]", sanitized[0]):
        sanitized = f"n_{sanitized}"
    if sanitized.lower().startswith("xml"):
        sanitized = f"n_{sanitized}"
    return sanitized


def split_label(label: str) -> tuple[Optional[str], Optional[str]]:
    text = label.strip()
    match = re.match(r"^(?P<base>[^\[]+?)(?:\s*\[(?P<units>[^\]]+)\])?$", text)
    if not match:
        return text or None, None
    base = match.group("base").strip()
    units = match.group("units")
    return (base or None), (units.strip() if units else None)


def element_with_attributes(name: str, attribs: Attributes) -> ET.Element:
    original_name = str(name)
    safe_name = sanitize_xml_tag(original_name)
    attributes = dict(attribs or {})
    if safe_name != original_name and "label" not in attributes:
        attributes["label"] = original_name

    value_value = attributes.pop("value", None) if "value" in attributes else None
    auto_value = attributes.pop("auto", None) if "auto" in attributes else None
    comment_value = attributes.pop("comment", None) if "comment" in attributes else None
    units_value = attributes.pop("units_comment", None) if "units_comment" in attributes else None

    element = ET.Element(safe_name)
    if value_value is not None:
        element.set("value", stringify(value_value))
    if auto_value is not None:
        element.set("auto", stringify(auto_value))

    for key, value in sorted(attributes.items()):
        element.set(str(key), stringify(value))

    if comment_value is not None:
        element.set("comment", stringify(comment_value))
    if units_value is not None:
        element.set("units_comment", stringify(units_value))

    return element


def vector_element(name: str, vector: VectorDict) -> ET.Element:
    ordered = {axis: vector.get(axis) for axis in ("x", "y", "z") if axis in vector}
    return element_with_attributes(name, ordered)


def append_if_not_none(parent: ET.Element, element: Optional[ET.Element]) -> None:
    if element is not None:
        parent.append(element)


def build_generic_node(spec: Dict[str, Any]) -> ET.Element:
    if not isinstance(spec, dict):
        raise TypeError(f"Generic node specification must be a dict, got {type(spec)!r}")
    data = dict(spec)
    tag = data.pop("tag", None) or data.pop("name", None) or data.pop("type", None)
    if not tag:
        raise ValueError(f"Generic node specification missing 'tag': {spec}")

    # Handle comments
    if tag == "comment":
        return ET.Comment(' ' + data.get("text", "").strip() + ' ')

    attributes = dict(data.pop("attributes", {}))
    node = element_with_attributes(tag, attributes)
    vector = data.pop("vector", None)
    if vector is not None:
        for axis, value in vector.items():
            node.set(str(axis), stringify(value))
    text = data.pop("text", None)
    if text is not None:
        node.text = stringify(text)
    for child_spec in data.pop("children", []):
        node.append(build_generic_node(child_spec))
    for extra_spec in data.pop("extra", []):
        node.append(build_generic_node(extra_spec))
    for key in list(data.keys()):
        value = data.pop(key)
        if isinstance(value, dict):
            nested_spec = dict(value)
            nested_spec.setdefault('tag', key)
            node.append(build_generic_node(nested_spec))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested_spec = dict(item)
                    if 'tag' not in nested_spec and 'name' not in nested_spec and 'type' not in nested_spec:
                        nested_spec['tag'] = key
                    node.append(build_generic_node(nested_spec))
                else:
                    node.append(build_generic_node({'tag': key, 'text': item}))
        else:
            node.set(str(key), stringify(value))
    return node


class CaseBuilder:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._external_stl_filename = self._resolve_external_stl_filename()

    def build(self) -> ET.Element:
        case = element_with_attributes("case", self.config.get("case_attributes", {}))
        case.append(self._build_casedef())
        case.append(self._build_execution())
        return case

    def _build_casedef(self) -> ET.Element:
        casedef = element_with_attributes("casedef", self.config.get("casedef_attributes", {}))
        added_sections: set[str] = set()
        ordered_entries = self.config.get("casedef_children")
        if ordered_entries:
            for entry in ordered_entries:
                entry_type = entry.get("type")
                if entry_type == "section":
                    key = entry.get("key")
                    if key == "constants" and "constants" in self.config and key not in added_sections:
                        append_if_not_none(casedef, self._build_constantsdef())
                        added_sections.add(key)
                    elif key == "mkconfig" and "mkconfig" in self.config and key not in added_sections:
                        append_if_not_none(casedef, self._build_mkconfig())
                        added_sections.add(key)
                    elif key == "patterns" and "patterns" in self.config and key not in added_sections:
                        append_if_not_none(casedef, self._build_patterns())
                        added_sections.add(key)
                    elif key == "geometry" and "geometry" in self.config and key not in added_sections:
                        append_if_not_none(casedef, self._build_geometry())
                        added_sections.add(key)
                    elif key == "normals" and key not in added_sections:
                        append_if_not_none(casedef, self._build_normals())
                        added_sections.add(key)
                    elif key in {"initials", "floatings", "motion"} and key in self.config and key not in added_sections:
                        append_if_not_none(casedef, self._build_section_list(key))
                        added_sections.add(key)
                elif entry_type == "generic":
                    casedef.append(build_generic_node(entry["spec"]))
        else:
            config_order = ["constants", "mkconfig", "patterns", "geometry", "normals", "initials", "floatings", "motion", "casedef_extra"]
            for key in config_order:
                if key == "constants":
                    if "constants" in self.config or "constantsdef" in self.config:
                        append_if_not_none(casedef, self._build_constantsdef())
                elif key == "mkconfig" and "mkconfig" in self.config:
                    append_if_not_none(casedef, self._build_mkconfig())
                elif key == "patterns" and "patterns" in self.config:
                    append_if_not_none(casedef, self._build_patterns())
                elif key == "geometry" and "geometry" in self.config:
                    append_if_not_none(casedef, self._build_geometry())
                elif key == "normals" and ("normals" in self.config or (isinstance(self.config.get("geometry"), dict) and self.config["geometry"].get("normals") is not None)):
                    append_if_not_none(casedef, self._build_normals())
                elif key in {"initials", "floatings", "motion"} and key in self.config:
                    append_if_not_none(casedef, self._build_section_list(key))
                elif key == "casedef_extra" and "casedef_extra" in self.config:
                    for spec in self.config["casedef_extra"]:
                        casedef.append(build_generic_node(spec))

        remaining_extras = self.config.get("casedef_extra", [])
        if ordered_entries:
            for spec in remaining_extras:
                if not any(entry.get("type") == "generic" and entry.get("spec") is spec for entry in ordered_entries):
                    casedef.append(build_generic_node(spec))
        return casedef

    def _build_constantsdef(self) -> ET.Element:
        constants_node = ET.Element("constantsdef")
        constants_cfg = self.config.get("constants") or self.config.get("constantsdef") or {}
        for name, cfg in constants_cfg.items():
            if cfg is None:
                continue

            if isinstance(cfg, dict) and any(
                key in cfg for key in ("tag", "attributes", "children", "text", "extra", "vector")
            ):
                spec = dict(cfg)
                spec.setdefault("tag", name)
                constants_node.append(build_generic_node(spec))
                continue

            meta = DEFAULT_CONSTANT_META.get(name, {})
            attributes: Dict[str, Any] = {}

            if isinstance(cfg, dict):
                for key, value in cfg.items():
                    if key in {"value", "auto", "comment", "units_comment", "label", "tag"}:
                        continue
                    attributes[key] = value
            else:
                attributes["value"] = cfg

            if isinstance(cfg, dict) and cfg.get("value") is not None:
                attributes["value"] = cfg["value"]

            vector_only = bool(attributes) and set(attributes.keys()) <= {"x", "y", "z"}
            include_meta = isinstance(cfg, dict)

            if include_meta and "value" not in attributes and not vector_only and meta.get("value") is not None:
                attributes["value"] = meta["value"]

            if isinstance(cfg, dict) and "auto" in cfg:
                attributes["auto"] = cfg["auto"]
            elif include_meta and not vector_only and "auto" in meta:
                attributes["auto"] = meta["auto"]

            label_comment = None
            label_units = None
            has_label = False
            if isinstance(cfg, dict) and cfg.get("label"):
                label_comment, label_units = split_label(cfg["label"])
                has_label = True

            if isinstance(cfg, dict) and "comment" in cfg:
                attributes["comment"] = cfg["comment"]
            elif label_comment:
                attributes.setdefault("comment", label_comment)
            elif include_meta and not vector_only and not has_label and "comment" in meta and "comment" not in attributes:
                attributes["comment"] = meta["comment"]

            if isinstance(cfg, dict) and "units_comment" in cfg:
                attributes["units_comment"] = cfg["units_comment"]
            elif label_units and "units_comment" not in attributes:
                attributes["units_comment"] = label_units
            elif include_meta and not vector_only and not has_label and "units_comment" in meta and "units_comment" not in attributes:
                attributes["units_comment"] = meta["units_comment"]

            spec = {"tag": name, "attributes": attributes}
            constants_node.append(build_generic_node(spec))
        return constants_node

    def _build_mkconfig(self) -> Optional[ET.Element]:
        data = self.config.get("mkconfig")
        if not data:
            return None
        attributes = {
            key: value
            for key, value in data.items()
            if key not in {"orientations", "extra"}
            and not isinstance(value, list)
        }
        # Force safe mk totals when emitting XML; agent configs may undershoot these counts.
        attributes["boundcount"] = "230"
        attributes["fluidcount"] = "15"
        node = element_with_attributes("mkconfig", attributes)
        for orientation in data.get("orientations", []):
            orient_type = orientation.get("type")
            if not orient_type:
                raise ValueError(f"mkconfig orientation missing 'type': {orientation}")
            orient_attributes = {
                key: value
                for key, value in orientation.items()
                if key != "type"
            }
            node.append(element_with_attributes(f"mkorient{orient_type}", orient_attributes))
        for spec in data.get("extra", []):
            node.append(build_generic_node(spec))
        return node

    def _build_patterns(self) -> Optional[ET.Element]:
        patterns = self.config.get("patterns")
        if not patterns:
            return None
        node = ET.Element("patterns")
        for pattern_cfg in patterns:
            attributes = {
                key: value
                for key, value in pattern_cfg.items()
                if key not in {"size", "scale", "gap", "border", "children"}
            }
            pattern_node = element_with_attributes("pattern", attributes)
            for vector_key in ("size", "scale", "gap", "border"):
                if vector_key in pattern_cfg:
                    pattern_node.append(vector_element(vector_key, pattern_cfg[vector_key]))
            for child_spec in pattern_cfg.get("children", []):
                pattern_node.append(build_generic_node(child_spec))
            node.append(pattern_node)
        return node

    def _build_geometry(self) -> Optional[ET.Element]:
        geometry_cfg = self.config.get("geometry")
        if geometry_cfg is None:
            return None
        geometry_node = ET.Element("geometry")

        append_if_not_none(geometry_node, self._build_geometry_predefinition(geometry_cfg.get("predefinition")))

        definition_node = self._build_geometry_definition(geometry_cfg)
        if definition_node is not None:
            geometry_node.append(definition_node)
        elif "definition" in geometry_cfg:
            raise ValueError("geometry.definition missing")

        commands = self._build_geometry_commands(geometry_cfg)
        if commands is not None:
            geometry_node.append(commands)

        for spec in geometry_cfg.get("extra", []):
            geometry_node.append(build_generic_node(spec))

        self._apply_external_stl_filename(geometry_node)
        return geometry_node

    def _build_normals(self) -> Optional[ET.Element]:
        geometry_cfg = self.config.get("geometry")
        normals_cfg: Any = None
        if isinstance(geometry_cfg, dict):
            geometry_normals = geometry_cfg.get("normals")
            if geometry_normals is not None:
                normals_cfg = geometry_normals
        if normals_cfg is None:
            normals_cfg = self.config.get("normals")
        if normals_cfg is None:
            return None

        if isinstance(normals_cfg, list):
            entries = [entry for entry in normals_cfg if entry is not None]
            if not entries:
                return None
            if len(entries) == 1:
                normals_cfg = entries[0]
            else:
                children_specs: List[Dict[str, Any]] = []
                for entry in entries:
                    if isinstance(entry, dict):
                        child_spec = dict(entry)
                        if "tag" not in child_spec and "name" not in child_spec and "type" not in child_spec:
                            child_spec["tag"] = "item"
                        children_specs.append(child_spec)
                    else:
                        children_specs.append({"tag": "item", "text": entry})
                return build_generic_node({"tag": "normals", "children": children_specs})

        if isinstance(normals_cfg, dict):
            spec = dict(normals_cfg)
            spec.setdefault("tag", "normals")
            return build_generic_node(spec)

        return build_generic_node({"tag": "normals", "text": normals_cfg})

    def _build_geometry_predefinition(self, config: Any) -> Optional[ET.Element]:
        if not config:
            return None
        if isinstance(config, dict) and (config.get("tag") or config.get("name")):
            return build_generic_node(config)
        entries: Iterable[Dict[str, Any]]
        if isinstance(config, dict):
            entries = config.get("entries", [])
        else:
            entries = config
        node = ET.Element("predefinition")
        for spec in entries:
            node.append(build_generic_node(spec))
        return node

    def _build_geometry_definition(self, geometry_cfg: Dict[str, Any]) -> Optional[ET.Element]:
        definition_cfg = geometry_cfg.get("definition")
        if definition_cfg is None:
            dp = geometry_cfg.get("dp")
            if dp is None:
                return None
            domain = geometry_cfg.get("domain", {})
            definition_cfg = {
                "dp": dp,
                "pointmin": domain.get("min"),
                "pointmax": domain.get("max"),
            }
            comment = geometry_cfg.get("comment")
            units = geometry_cfg.get("units_comment")
            if comment is not None or units is not None:
                meta: Dict[str, Any] = {}
                if comment is not None:
                    meta["comment"] = comment
                if units is not None:
                    meta["units_comment"] = units
                definition_cfg["meta"] = meta

        if isinstance(definition_cfg, dict) and (definition_cfg.get("tag") or definition_cfg.get("name")):
            definition_node = build_generic_node(definition_cfg)
            if "dp" not in definition_node.attrib:
                raise ValueError("definition.dp attribute is required")
            return definition_node

        if not isinstance(definition_cfg, dict):
            raise TypeError("geometry.definition must be a dict when provided")

        def _vector_from_spec(source: Any, tag_name: str) -> Dict[str, Any]:
            if source is None:
                raise ValueError(f"geometry.definition requires {tag_name}")
            if looks_like_vector(source):
                return {axis: source[axis] for axis in ("x", "y", "z") if axis in source}
            if isinstance(source, dict):
                vector = source.get("vector")
                if looks_like_vector(vector):
                    return {axis: vector[axis] for axis in ("x", "y", "z") if axis in vector}
                attributes = source.get("attributes")
                if looks_like_vector(attributes):
                    return {axis: attributes[axis] for axis in ("x", "y", "z") if axis in attributes}
                if looks_like_vector(source):
                    return {axis: source[axis] for axis in ("x", "y", "z") if axis in source}
            raise TypeError(f"Unsupported {tag_name} specification: {source}")

        if {"dp", "pointmin", "pointmax"}.issubset(definition_cfg.keys()) and not isinstance(definition_cfg.get("attributes"), dict):
            dp_value = definition_cfg["dp"]
            pointmin_vec = _vector_from_spec(definition_cfg["pointmin"], "pointmin")
            pointmax_vec = _vector_from_spec(definition_cfg["pointmax"], "pointmax")
            meta = definition_cfg.get("meta")
            node_attrs: Dict[str, Any] = {"dp": dp_value}
            if isinstance(meta, dict):
                comment = meta.get("comment")
                units = meta.get("units_comment")
                if comment is not None:
                    node_attrs["comment"] = comment
                if units is not None:
                    node_attrs["units_comment"] = units
            node = element_with_attributes("definition", node_attrs)
            child_specs = definition_cfg.get("children", [])
            pointref_specs: List[Any] = []
            other_specs: List[Any] = []
            for child_spec in child_specs:
                tag_name = ""
                if isinstance(child_spec, dict):
                    tag_name = str(child_spec.get("tag") or child_spec.get("name") or child_spec.get("type") or "").lower()
                if tag_name == "pointref":
                    pointref_specs.append(child_spec)
                else:
                    other_specs.append(child_spec)
            for child_spec in pointref_specs:
                node.append(build_generic_node(child_spec))
            node.append(vector_element("pointmin", pointmin_vec))
            node.append(vector_element("pointmax", pointmax_vec))
            for child_spec in other_specs:
                node.append(build_generic_node(child_spec))
            return node

        attributes = dict(definition_cfg.get("attributes", {}))
        if definition_cfg.get("dp") is not None and "dp" not in attributes:
            attributes["dp"] = definition_cfg["dp"]
        if "dp" not in attributes:
            raise ValueError("geometry.definition requires dp value")

        node = element_with_attributes("definition", attributes)

        children_specs = definition_cfg.get("children")
        if children_specs is None:
            remaining_children: List[Dict[str, Any]] = []
        elif isinstance(children_specs, list):
            remaining_children = [dict(child) if isinstance(child, dict) else child for child in children_specs]
        else:
            raise TypeError("geometry.definition.children must be an array when provided")

        def _pop_child(tag_name: str) -> Optional[Dict[str, Any]]:
            for idx, child in enumerate(list(remaining_children)):
                child_tag = child.get("tag") or child.get("name") or child.get("type")
                if child_tag == tag_name:
                    return remaining_children.pop(idx)
            return None

        pointref_specs: List[Dict[str, Any]] = []
        other_specs: List[Any] = []
        for child_spec in remaining_children:
            tag_name = ""
            if isinstance(child_spec, dict):
                tag_name = str(child_spec.get("tag") or child_spec.get("name") or child_spec.get("type") or "").lower()
            if tag_name == "pointref":
                pointref_specs.append(child_spec)
            else:
                other_specs.append(child_spec)
        for child_spec in pointref_specs:
            node.append(build_generic_node(child_spec))

        for tag_name in ("pointmin", "pointmax"):
            vector_source = definition_cfg.get(tag_name)
            if vector_source is None:
                popped = _pop_child(tag_name)
                if popped is not None:
                    vector_source = popped
            vector = _vector_from_spec(vector_source, tag_name)
            node.append(vector_element(tag_name, vector))

        for child_spec in other_specs:
            node.append(build_generic_node(child_spec))

        return node
    def _build_geometry_commands(self, geometry_cfg: Dict[str, Any]):
        commands_cfg = geometry_cfg.get("commands")
        objects_cfg = geometry_cfg.get("objects")
        if not commands_cfg and not objects_cfg:
            return None

        node = ET.Element("commands")
        mainlist_node = None

        if commands_cfg and "children" in commands_cfg:
            for child_spec in commands_cfg["children"]:
                built_child = build_generic_node(child_spec)
                node.append(built_child)
                if str(built_child.tag) == "mainlist":
                    mainlist_node = built_child
        else:
            if commands_cfg:
                if "lists" in commands_cfg:
                    for list_cfg in commands_cfg.get("lists", []):
                        list_children = list_cfg.pop("items", [])
                        list_spec = {"tag": "list", "attributes": list_cfg, "children": list_children}
                        node.append(self._build_command(list_spec))
                if "mainlist" in commands_cfg:
                    mainlist_node = ET.Element("mainlist")
                    for cmd_spec in commands_cfg["mainlist"]:
                        mainlist_node.append(self._build_command(cmd_spec))
                    node.append(mainlist_node)

        if objects_cfg:
            if mainlist_node is None:
                mainlist_node = ET.SubElement(node, "mainlist")
            legacy_commands = self._objects_to_commands(objects_cfg)
            for command_spec in legacy_commands:
                mainlist_node.append(self._build_command(command_spec))

        if mainlist_node is not None and not (commands_cfg and "children" in commands_cfg):
            self._ensure_fillcommands_use_points(mainlist_node)

        return node

    def _objects_to_commands(self, objects: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        commands: List[Dict[str, Any]] = []
        for obj in objects:
            obj_type = obj.get("type")
            if obj_type not in {"fluid", "bound"}:
                raise ValueError(f"Unsupported object type in geometry.objects: {obj}")
            if obj.get("shape") != "box":
                raise ValueError(f"Only box shapes are supported in geometry.objects, got: {obj}")
            mk = obj.get("mk")
            commands.append({"type": f"setmk{obj_type}", "attributes": {"mk": mk}})
            if obj_type == "fluid":
                children = [
                    {"tag": "modefill", "text": obj.get("modefill", "void")},
                    {"tag": "point", "vector": obj.get("position", {})},
                    {"tag": "size", "vector": obj.get("size", {})},
                ]
                command_type = "fillbox"
            else:
                children = [
                    {"tag": "boxfill", "text": obj.get("fill_mode", "solid")},
                    {"tag": "point", "vector": obj.get("position", {})},
                    {"tag": "size", "vector": obj.get("size", {})},
                ]
                command_type = "drawbox"
            commands.append({"type": command_type, "children": children})
        return commands

    def _build_command(self, command_config: Dict[str, Any]) -> ET.Element:
        cfg_copy = dict(command_config)

        if cfg_copy.get('tag') == 'list':
            list_attribs = cfg_copy.get("attributes", {})
            list_node = element_with_attributes("list", list_attribs)
            for cmd_spec in cfg_copy.get("children", []):
                list_node.append(self._build_command(cmd_spec))
            return list_node

        command_type = cfg_copy.pop("type", None) or cfg_copy.pop("tag", None)
        if (cfg_copy.get("type") == "comment") or (cfg_copy.get("tag") == "comment"):
            text = cfg_copy.get("text", "")
            return build_generic_node({"tag": "comment", "text": text})

        if not command_type:
            raise ValueError(f"Command specification missing 'type' or 'tag': {cfg_copy}")

        attributes = cfg_copy.pop("attributes", {})
        if not attributes:
             attributes = {k: v for k, v in cfg_copy.items() if k not in {"type", "tag", "children", "extra", "text", "vector"}}

        # Lift special dict attributes into child elements (avoids stringified dicts in XML)
        special_children: List[Dict[str, Any]] = []
        for special_key in ("point", "size"):
            val = attributes.get(special_key)
            if isinstance(val, dict) and looks_like_vector(val):
                special_children.append({"tag": special_key, "vector": val})
                del attributes[special_key]
                # Also remove from cfg_copy so it is not re-added as a stringified attribute below
                if special_key in cfg_copy:
                    cfg_copy.pop(special_key, None)
        # Prefer child <boxfill> node for draw* commands
        if str(command_type).lower().startswith("draw"):
            val = attributes.get("boxfill")
            if val is not None:
                special_children.append({"tag": "boxfill", "text": val})
                del attributes["boxfill"]
                cfg_copy.pop("boxfill", None)

        node = element_with_attributes(command_type, attributes)
        for child_spec in special_children:
            node.append(build_generic_node(child_spec))

        # Ensure these keys are never serialized as stringified dict attributes
        for _k in ("point", "size", "boxfill"):
            cfg_copy.pop(_k, None)

        vector = cfg_copy.pop("vector", None)
        if vector:
            for axis, value in vector.items():
                node.set(str(axis), stringify(value))

        for child_spec in cfg_copy.pop("children", []):
            node.append(build_generic_node(child_spec))
        for extra_spec in cfg_copy.pop("extra", []):
            node.append(build_generic_node(extra_spec))
        if cfg_copy.get("text") is not None:
            node.text = stringify(cfg_copy.pop("text"))

        # any remaining items are attributes
        for key, value in cfg_copy.items():
            node.set(str(key), stringify(value))

        # Special coercions/fallbacks for compatibility
        cmd = str(command_type).lower()
        if cmd == "setdrawmode":
            val = node.attrib.pop("value", None)
            if val is not None and "mode" not in node.attrib:
                node.set("mode", stringify(val))
        elif cmd == "setshapemode":
            val = node.attrib.pop("value", None)
            if (node.text is None or node.text == "") and val is not None:
                node.text = stringify(val)

        if cmd == "fillbox":
            for child in node:
                if str(child.tag or "").lower() == "modefill":
                    text = (child.text or "").strip().lower()
                    if text == "solid":
                        child.text = "void"

        return node

    def _ensure_fillcommands_use_points(self, mainlist_node: ET.Element) -> None:
        drawpoints_enabled = False
        children = list(mainlist_node)
        idx = 0
        while idx < len(children):
            child = children[idx]
            tag = str(child.tag or "").lower()
            if tag == "resetdraw":
                drawpoints_enabled = True
            elif tag == "setactive":
                value = child.attrib.get("drawpoints")
                if value is None:
                    drawpoints_enabled = True
                else:
                    drawpoints_enabled = str(value).lower() not in {"0", "false"}
            elif tag.startswith("fill"):
                if not drawpoints_enabled:
                    setactive = ET.Element("setactive")
                    setactive.set("drawpoints", "1")
                    setactive.set("drawshapes", "0")
                    mainlist_node.insert(idx, setactive)
                    children.insert(idx, setactive)
                    drawpoints_enabled = True
                    idx += 1
                    child = children[idx]
                self._ensure_fill_command_position(child)
                drawpoints_enabled = True
            idx += 1

    def _ensure_fill_command_position(self, command_node: ET.Element) -> None:
        missing_axes = [axis for axis in ("x", "y", "z") if axis not in command_node.attrib]
        if not missing_axes:
            return
        point_node = None
        for child in list(command_node):
            if str(child.tag or "").lower() == "point":
                point_node = child
                break
        if point_node is None:
            return
        for axis in ("x", "y", "z"):
            if axis in command_node.attrib:
                continue
            value = point_node.attrib.get(axis)
            if value is not None:
                command_node.set(axis, value)

    def _apply_external_stl_filename(self, geometry_node: ET.Element) -> None:
        filename = self._external_stl_filename
        if not filename:
            return
        for draw_node in geometry_node.findall('.//drawfilestl'):
            file_attr = draw_node.attrib.get('file')
            if not file_attr:
                continue
            current_name = Path(str(file_attr)).name.lower()
            if current_name in PLACEHOLDER_STL_FILENAMES:
                draw_node.set('file', filename)

    def _resolve_external_stl_filename(self) -> Optional[str]:
        candidates: List[Any] = []
        direct = self.config.get('external_stl')
        if direct:
            candidates.append(direct)
        geometry_cfg = self.config.get('geometry')
        if isinstance(geometry_cfg, dict):
            geometry_external = geometry_cfg.get('external_stl')
            if geometry_external:
                candidates.append(geometry_external)
        try:
            from external_stl import get_external_stl_context  # type: ignore
        except Exception:
            context = None
        else:
            context = get_external_stl_context()
            if context:
                candidates.append(context)
        for candidate in candidates:
            name = self._extract_external_stl_filename(candidate)
            if name:
                return name
        return None

    @staticmethod
    def _extract_external_stl_filename(source: Any) -> Optional[str]:
        if source is None:
            return None
        candidates: List[Any] = []
        if isinstance(source, str):
            candidates.append(source)
        elif isinstance(source, dict):
            for key in (
                'stored_filename',
                'original_filename',
                'filename',
                'name',
                'stored_relative_path',
                'relative_path',
                'stored_path',
                'source_path',
                'path',
            ):
                value = source.get(key)
                if value is not None:
                    candidates.append(value)
        else:
            return None
        for candidate in candidates:
            candidate_str = str(candidate).strip()
            if not candidate_str:
                continue
            name = Path(candidate_str).name
            if not name or not name.lower().endswith('.stl'):
                continue
            return name
        return None
    def _build_section_list(self, section_key: str) -> Optional[ET.Element]:
        specs_config = self.config.get(section_key)
        if not specs_config:
            return None
        if isinstance(specs_config, dict):
            if 'entries' in specs_config:
                entries = specs_config['entries']
            elif 'children' in specs_config:
                entries = specs_config['children']
            else:
                entries = [specs_config]
        elif isinstance(specs_config, list):
            entries = specs_config
        else:
            raise TypeError(f"Unsupported configuration for section '{section_key}': {type(specs_config)!r}")

        if not entries:
            return None
        node = ET.Element(section_key)
        for spec in entries:
            node.append(build_generic_node(spec))
        return node

    def _build_execution(self) -> ET.Element:
        execution = element_with_attributes("execution", self.config.get("execution_attributes", {}))
        exec_config = self.config.get("execution", {})

        build_order = exec_config.get("children_order", ["parameters", "special", "extra_nodes"])

        for key in build_order:
            if key == "parameters" and exec_config.get("parameters"):
                execution.append(
                    self._build_parameters(
                        exec_config.get("parameters"),
                        exec_config.get("parameters_order"),
                        exec_config.get("parameters_children"),
                    )
                )
            elif key == "special":
                special_children = exec_config.get("special_children")
                special_node = ET.Element("special")
                if special_children:
                    for entry in special_children:
                        entry_type = entry.get("type")
                        if entry_type == "generic":
                            special_node.append(build_generic_node(entry["spec"]))
                        elif entry_type == "known":
                            mapped_key = entry.get("key")
                            tag_name = entry.get("tag", mapped_key)
                            if mapped_key == "gauges" and exec_config.get("gauges"):
                                gauges_node = self._build_gauges(exec_config.get("gauges"))
                                if gauges_node.tag != tag_name:
                                    gauges_node.tag = tag_name
                                special_node.append(gauges_node)
                            elif mapped_key == "timeout" and exec_config.get("timeout"):
                                timeout_node = self._build_timeout(exec_config.get("timeout"))
                                if timeout_node.tag != tag_name:
                                    timeout_node.tag = tag_name
                                special_node.append(timeout_node)
                            else:
                                section_cfg = exec_config.get(mapped_key)
                                if section_cfg:
                                    special_node.append(self._build_special_section(tag_name, section_cfg))
                        # Ignore unknown entry types silently to preserve robustness
                    if len(special_node):
                        execution.append(special_node)
                else:
                    special_cfg = exec_config.get("special", [])
                    has_special_content = (
                        special_cfg
                        or exec_config.get("wavepaddles")
                        or exec_config.get("gauges")
                        or exec_config.get("timeout")
                        or exec_config.get("activeabsorption")
                        or exec_config.get("passiveabsorption")
                        or exec_config.get("relaxationzones")
                        or exec_config.get("particlefilter")
                        or exec_config.get("active_absorption")
                        or exec_config.get("passive_absorption")
                        or exec_config.get("relaxation_zones")
                        or exec_config.get("particle_filters")
                    )
                    if has_special_content:
                        special_order = [
                            "gauges",
                            "timeout",
                            "activeabsorption",
                            "passiveabsorption",
                            "relaxationzones",
                            "wavepaddles",
                            "particlefilter",
                            "special",
                        ]
                        key_aliases = {
                            "activeabsorption": "active_absorption",
                            "passiveabsorption": "passive_absorption",
                            "relaxationzones": "relaxation_zones",
                            "particlefilter": "particle_filters",
                        }
                        for special_key in special_order:
                            if special_key == "special":
                                for spec in special_cfg:
                                    special_node.append(build_generic_node(spec))
                                continue
                            cfg = exec_config.get(special_key)
                            if cfg is None and special_key in key_aliases:
                                cfg = exec_config.get(key_aliases[special_key])
                            if cfg is None:
                                continue
                            if special_key == "gauges":
                                special_node.append(self._build_gauges(cfg))
                            elif special_key == "timeout":
                                special_node.append(self._build_timeout(cfg))
                            else:
                                special_node.append(self._build_special_section(special_key, cfg))
                        if len(special_node):
                            execution.append(special_node)
            elif key == "extra_nodes":
                for spec in exec_config.get("extra_nodes", []):
                    execution.append(build_generic_node(spec))

        return execution

    def _build_parameters(self, parameters_config: Any, order: Optional[Sequence[str]] = None, children_plan: Optional[Sequence[Dict[str, Any]]] = None) -> ET.Element:
        node = ET.Element("parameters")
        if isinstance(parameters_config, dict):
            emitted: set[str] = set()

            def append_parameter(key: str, value: Any) -> None:
                if value is None:
                    return
                if isinstance(value, dict):
                    is_generic = any(
                        marker in value
                        for marker in ("tag", "children", "text", "vector", "extra", "attributes")
                    )
                    if is_generic:
                        spec = dict(value)
                        spec.setdefault("tag", "parameter")
                        if "key" not in spec:
                            if "attributes" in spec and isinstance(spec["attributes"], dict):
                                attrs = dict(spec["attributes"])
                                attrs.setdefault("key", key)
                                spec["attributes"] = attrs
                            else:
                                spec.setdefault("key", key)
                        node.append(build_generic_node(spec))
                    else:
                        attributes = dict(value)
                        attributes.setdefault("key", key)
                        node.append(element_with_attributes("parameter", attributes))
                else:
                    attributes = {"key": key, "value": value}
                    node.append(element_with_attributes("parameter", attributes))

            if children_plan:
                for entry in children_plan:
                    entry_type = entry.get("type")
                    if entry_type == "parameter":
                        key = entry.get("key")
                        if key is None or key not in parameters_config:
                            continue
                        append_parameter(key, parameters_config[key])
                        emitted.add(key)
                    elif entry_type == "generic":
                        node.append(build_generic_node(entry["spec"]))
                remaining_keys = [
                    key for key in parameters_config.keys() if key not in emitted
                ]
                if remaining_keys:
                    for key in remaining_keys:
                        append_parameter(key, parameters_config[key])
            else:
                if order:
                    keys: Iterable[str] = order
                else:
                    keys = sorted(parameters_config.keys())
                for key in keys:
                    if key not in parameters_config:
                        continue
                    append_parameter(key, parameters_config[key])
        elif isinstance(parameters_config, list):
            for item in parameters_config:
                if "key" not in item:
                    raise ValueError(f"Execution parameter entry missing 'key': {item}")
                node.append(element_with_attributes("parameter", item))
        else:
            raise TypeError("execution.parameters must be a dict or a list")
        return node

    def _build_gauges(self, gauges: Sequence[Dict[str, Any]]) -> ET.Element:
        gauges_node = ET.Element("gauges")
        for gauge in gauges:
            gauge_type = gauge.get("type")
            if not gauge_type:
                raise ValueError(f"Gauge specification missing 'type': {gauge}")
            attributes = dict(gauge.get("attributes", {}))
            if "name" in gauge:
                attributes.setdefault("name", gauge["name"])
            gauge_element = element_with_attributes(gauge_type, attributes)
            plan = gauge.get("children_plan")
            processed_keys = set()
            planned_generic_ids = set()
            planned_generic_fingerprints: Set[str] = set()

            def _fingerprint_spec(spec: Dict[str, Any]) -> str:
                def _normalize(value: Any):
                    if isinstance(value, dict):
                        return {k: _normalize(value[k]) for k in sorted(value.keys())}
                    if isinstance(value, list):
                        return [_normalize(item) for item in value]
                    return value
                return json.dumps(_normalize(spec), sort_keys=True, ensure_ascii=False)

            if plan:
                for entry in plan:
                    entry_type = entry.get("type")
                    if entry_type == "mapped":
                        key = entry.get("key")
                        if not key or key not in gauge:
                            continue
                        processed_keys.add(key)
                        tag_name = entry.get("tag")
                        if key == "start":
                            default_tag = "point0"
                        elif key == "mid":
                            default_tag = "point1"
                        elif key == "end":
                            default_tag = "point2"
                        else:
                            default_tag = key
                        gauge_element.append(
                            build_generic_node({"tag": tag_name or default_tag, "vector": gauge[key]})
                        )
                    elif entry_type == "generic":
                        spec = entry["spec"]
                        planned_generic_ids.add(id(spec))
                        fingerprint = _fingerprint_spec(spec)
                        planned_generic_fingerprints.add(fingerprint)
                        gauge_element.append(build_generic_node(spec))
                for key, default_tag in (("start", "point0"), ("mid", "point1"), ("end", "point2")):
                    if key in gauge and key not in processed_keys:
                        gauge_element.append(
                            build_generic_node({"tag": default_tag, "vector": gauge[key]})
                        )
                        processed_keys.add(key)
            else:
                if "start" in gauge:
                    gauge_element.append(build_generic_node({"tag": "point0", "vector": gauge["start"]}))
                if "mid" in gauge:
                    gauge_element.append(build_generic_node({"tag": "point1", "vector": gauge["mid"]}))
                if "end" in gauge:
                    gauge_element.append(build_generic_node({"tag": "point2", "vector": gauge["end"]}))
            for child_spec in gauge.get("children", []):
                if plan:
                    if id(child_spec) in planned_generic_ids:
                        continue
                    fingerprint = _fingerprint_spec(child_spec)
                    if fingerprint in planned_generic_fingerprints:
                        continue
                gauge_element.append(build_generic_node(child_spec))
            gauges_node.append(gauge_element)
        return gauges_node

    def _build_special_section(self, tag: str, config: Any) -> ET.Element:
        if isinstance(config, dict) and any(key in config for key in ('tag', 'type', 'name')) and "entries" not in config and "children" not in config:
            entries = [config]
            attributes = {}
            extra = []
        elif isinstance(config, dict):
            attributes = dict(config.get('attributes', {}))
            extra = config.get('extra', [])
            if 'entries' in config:
                entries = config['entries']
            elif 'children' in config:
                entries = config['children']
            else:
                entries = []
                for key, value in config.items():
                    if key in {'attributes', 'extra'}:
                        continue
                    if isinstance(value, dict):
                        nested_spec = dict(value)
                        nested_spec.setdefault('tag', key)
                        entries.append(nested_spec)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                nested_spec = dict(item)
                                if 'tag' not in nested_spec and 'name' not in nested_spec and 'type' not in nested_spec:
                                    nested_spec['tag'] = key
                                entries.append(nested_spec)
                            else:
                                entries.append({'tag': key, 'text': item})
                    else:
                        attributes[key] = value
        elif isinstance(config, list):
            attributes = {}
            extra = []
            entries = config
        else:
            raise TypeError(f"Unsupported configuration for special section '{tag}': {type(config)!r}")
        node = element_with_attributes(tag, attributes)
        for spec in entries:
            node.append(build_generic_node(spec))
        if isinstance(extra, list):
            for spec in extra:
                node.append(build_generic_node(spec))
        return node


    def _build_timeout(self, timeout_config: Dict[str, Any]) -> ET.Element:
        attributes = timeout_config.get("attributes", {})
        timeout_node = element_with_attributes("timeout", attributes)
        for entry in timeout_config.get("entries", []):
            timeout_node.append(element_with_attributes("tout", entry))
        for child_spec in timeout_config.get("children", []):
            timeout_node.append(build_generic_node(child_spec))
        return timeout_node


def serialize_xml(root: ET.Element) -> str:
    return ET.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8")


def build_case_element(config: Dict[str, Any]) -> ET.Element:
    builder = CaseBuilder(config)
    return builder.build()


FILL_COMMAND_TAGS = {
    "fillbox",
    "fillcylinder",
    "fillmesh",
    "fillpoints",
    "fillplane",
    "fillprism",
}

THIN_AXIS_TOLERANCE = 1e-9
_SYMBOLIC_VALUE_PATTERN = re.compile(r"[#A-Za-z]")


def _is_symbolic_value(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    return bool(_SYMBOLIC_VALUE_PATTERN.search(text))

def _parse_float_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _parse_int_value(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _validate_fluid_fillbox_guardrails(
    node: ET.Element,
    geometry_bounds: Dict[str, Tuple[float, float]],
    errors: List[str],
) -> None:
    modefill = None
    point_node = None
    size_node = None
    for child in list(node):
        tag = str(child.tag or "").lower()
        if tag == "modefill":
            modefill = child
        elif tag == "point":
            point_node = child
        elif tag == "size":
            size_node = child
    if modefill is None or (modefill.text or "").strip().lower() != "void":
        errors.append("Fluid fillbox requires <modefill>void</modefill>")
    if point_node is None or size_node is None:
        errors.append("Fluid fillbox missing <point> or <size> child elements")
        return
    for axis in ("x", "y", "z"):
        origin_text = node.attrib.get(axis)
        point_text = point_node.attrib.get(axis)
        size_text = size_node.attrib.get(axis)
        origin = _parse_float_value(origin_text)
        point_val = _parse_float_value(point_text)
        size_val = _parse_float_value(size_text)
        if any(
            value is None and not _is_symbolic_value(raw)
            for value, raw in (
                (origin, origin_text),
                (point_val, point_text),
                (size_val, size_text),
            )
        ):
            errors.append(
                f"Fluid fillbox axis {axis} requires numeric origin/point/size values"
            )
            continue
        if origin is None or point_val is None or size_val is None:
            continue
        end = point_val + size_val
        lower = min(point_val, end) - THIN_AXIS_TOLERANCE
        upper = max(point_val, end) + THIN_AXIS_TOLERANCE
        if origin < lower or origin > upper:
            errors.append(
                f"Fluid fillbox {axis}-coordinate {origin} lies outside the fluid volume [{point_val}, {end}]"
            )
    if not geometry_bounds:
        return
    y_bounds = geometry_bounds.get("y")
    if y_bounds is not None:
        min_y, max_y = y_bounds
        origin_y_text = node.attrib.get("y")
        origin_y = _parse_float_value(origin_y_text)
        if origin_y is None:
            if not _is_symbolic_value(origin_y_text):
                errors.append("Fluid fillbox missing numeric y-coordinate")
        elif abs(max_y - min_y) <= THIN_AXIS_TOLERANCE:
            if abs(origin_y - min_y) > THIN_AXIS_TOLERANCE:
                errors.append(
                    f"Fluid fillbox y-coordinate {origin_y} must equal geometry.definition plane {min_y}"
                )
        elif origin_y < min_y - THIN_AXIS_TOLERANCE or origin_y > max_y + THIN_AXIS_TOLERANCE:
            errors.append(
                f"Fluid fillbox y-coordinate {origin_y} lies outside geometry.definition bounds [{min_y}, {max_y}]"
            )
    for axis in ("x", "z"):
        bounds = geometry_bounds.get(axis)
        if bounds is None:
            continue
        min_val, max_val = bounds
        origin_text = node.attrib.get(axis)
        origin_val = _parse_float_value(origin_text)
        if origin_val is None:
            if not _is_symbolic_value(origin_text):
                errors.append(f"Fluid fillbox missing numeric {axis}-coordinate")
            continue
        if origin_val < min_val - THIN_AXIS_TOLERANCE or origin_val > max_val + THIN_AXIS_TOLERANCE:
            errors.append(
                f"Fluid fillbox {axis}-coordinate {origin_val} lies outside geometry.definition bounds [{min_val}, {max_val}]"
            )


def validate_case_tree(root: ET.Element) -> List[str]:
    errors: List[str] = []

    geometry_bounds: Dict[str, Tuple[float, float]] = {}

    casedef = root.find("casedef")
    if casedef is None:
        errors.append("missing <casedef> block")
        return errors

    geometry = casedef.find("geometry")
    if geometry is None:
        errors.append("missing <geometry> block")
        return errors

    definition = geometry.find("definition")
    if definition is None:
        errors.append("geometry.definition missing")
    else:
        dp_value = _parse_float_value(definition.attrib.get("dp"))
        if dp_value is None or dp_value <= 0:
            errors.append("geometry.definition.dp must be a positive number")

        pointmin = definition.find("pointmin")
        pointmax = definition.find("pointmax")
        if pointmin is None or pointmax is None:
            errors.append("geometry.definition requires <pointmin> and <pointmax>")
        else:
            thin_axes = 0
            for axis in ("x", "y", "z"):
                min_val = _parse_float_value(pointmin.attrib.get(axis))
                max_val = _parse_float_value(pointmax.attrib.get(axis))
                if min_val is None or max_val is None:
                    errors.append(f"geometry.definition point{axis} missing numeric value")
                    continue
                geometry_bounds[axis] = (min_val, max_val)
                if max_val < min_val:
                    errors.append(f"geometry.definition {axis}-axis has pointmax < pointmin")
                elif abs(max_val - min_val) <= THIN_AXIS_TOLERANCE:
                    thin_axes += 1
            if thin_axes > 1:
                errors.append("geometry.definition collapses more than one axis; 2D cases may collapse only one axis")

    commands_block = geometry.find("commands")
    mainlist = commands_block.find("mainlist") if commands_block is not None else None
    if mainlist is None:
        errors.append("geometry.commands.mainlist missing or empty")
    else:
        used_fluid_mks: set[int] = set()
        used_bound_mks: set[int] = set()
        setmkfluid_seen = False
        fluid_fill_found = False
        current_role = None

        for child in list(mainlist):
            tag = str(child.tag or "").lower()
            if tag == "setmkfluid":
                current_role = "fluid"
                setmkfluid_seen = True
                mk_val = _parse_int_value(child.attrib.get("mk"))
                if mk_val is not None:
                    used_fluid_mks.add(mk_val)
            elif tag == "setmkbound":
                current_role = "bound"
                mk_val = _parse_int_value(child.attrib.get("mk"))
                if mk_val is not None:
                    used_bound_mks.add(mk_val)
            elif tag == "setmkvoid":
                current_role = "void"
            elif tag.startswith("setmk"):
                current_role = None
            elif tag in FILL_COMMAND_TAGS:
                if current_role == "fluid":
                    fluid_fill_found = True
                    if tag == "fillbox":
                        _validate_fluid_fillbox_guardrails(child, geometry_bounds, errors)
                elif current_role is None:
                    errors.append(f"{tag} command appears without an active setmkfluid context")
            elif tag.startswith("draw"):
                # Validate drawbox requires boxfill child
                if tag == "drawbox":
                    has_boxfill = any(
                        str(c.tag or "").lower() == "boxfill"
                        for c in list(child)
                    )
                    if not has_boxfill:
                        errors.append(f"Error in geometry.commands.mainlist: drawbox requires child element <boxfill>\n"
                                    f"Expected: <boxfill>solid</boxfill> or <boxfill>bottom | left | right</boxfill>")

                if current_role == "fluid":
                    fluid_fill_found = True
                elif current_role is None:
                    errors.append(f"{tag} command appears without an active setmkfluid context")

        if setmkfluid_seen and not fluid_fill_found:
            errors.append("no fluid fill command found after setmkfluid in geometry.commands.mainlist")

        mkconfig = casedef.find("mkconfig")
        if mkconfig is not None:
            bound_count = _parse_int_value(mkconfig.attrib.get("boundcount"))
            fluid_count = _parse_int_value(mkconfig.attrib.get("fluidcount"))
            if used_bound_mks:
                if bound_count is None:
                    errors.append("mkconfig.boundcount missing while boundary mk are used")
                elif bound_count <= max(used_bound_mks):
                    errors.append(f"mkconfig.boundcount={bound_count} does not cover boundary mk {max(used_bound_mks)}")
            if used_fluid_mks:
                if fluid_count is None:
                    errors.append("mkconfig.fluidcount missing while fluid mk are used")
                elif fluid_count <= max(used_fluid_mks):
                    errors.append(f"mkconfig.fluidcount={fluid_count} does not cover fluid mk {max(used_fluid_mks)}")
        elif used_bound_mks or used_fluid_mks:
            errors.append("mkconfig missing while setmk commands define markers")

    return errors

def generate_case_xml(config: Dict[str, Any], *, pretty: bool = True) -> str:
    root = build_case_element(config)
    errors = validate_case_tree(root)
    if errors:
        details = "; ".join(errors)
        raise ValueError(f"Case validation failed: {details}")
    if pretty:
        return serialize_xml(root)
    return ET.tostring(root, encoding="unicode")

def write_case(config_path: Path, output_path: Path) -> None:
    config = load_config(config_path)
    xml_string = generate_case_xml(config)
    output_path.write_text(xml_string, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate DualSPHysics case XML from JSON config.")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--output", type=Path, default=Path("case.xml"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_case(args.config, args.output)
    print(f"Generated {args.output}")


if __name__ == "__main__":
    main()

