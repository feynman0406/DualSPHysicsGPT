from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
import xml.etree.ElementTree as ET
from xml.dom import minidom

VectorDict = Dict[str, Any]
Attributes = Dict[str, Any]


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


def element_with_attributes(name: str, attribs: Attributes) -> ET.Element:
    element = ET.Element(name)
    for key, value in attribs.items():
        if value is None:
            continue
        element.set(str(key), stringify(value))
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

    def build(self) -> ET.Element:
        case = element_with_attributes("case", self.config.get("case_attributes", {}))
        case.append(self._build_casedef())
        case.append(self._build_execution())
        return case

    def _build_casedef(self) -> ET.Element:
        casedef = element_with_attributes("casedef", self.config.get("casedef_attributes", {}))
        append_if_not_none(casedef, self._build_constantsdef())
        append_if_not_none(casedef, self._build_mkconfig())
        append_if_not_none(casedef, self._build_patterns())
        append_if_not_none(casedef, self._build_geometry())
        append_if_not_none(casedef, self._build_section_list("initials"))
        append_if_not_none(casedef, self._build_section_list("floatings"))
        append_if_not_none(casedef, self._build_section_list("motion"))
        for spec in self.config.get("casedef_extra", []):
            casedef.append(build_generic_node(spec))
        return casedef

    def _build_constantsdef(self) -> ET.Element:
        constants_node = ET.Element("constantsdef")
        constants = self.config.get("constants", {})
        for name, value in constants.items():
            if value is None:
                continue
            if looks_like_vector(value):
                constants_node.append(build_generic_node({"tag": name, "vector": value}))
            elif isinstance(value, dict):
                node_spec = dict(value)
                if 'tag' not in node_spec and 'name' not in node_spec and 'type' not in node_spec:
                    node_spec['tag'] = name
                constants_node.append(build_generic_node(node_spec))
            else:
                constants_node.append(build_generic_node({"tag": name, "attributes": {"value": value}}))
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
        geometry_node.append(self._build_geometry_definition(geometry_cfg))
        commands = self._build_geometry_commands(geometry_cfg)
        if commands is not None:
            geometry_node.append(commands)
        for spec in geometry_cfg.get("extra", []):
            geometry_node.append(build_generic_node(spec))
        return geometry_node

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

    def _build_geometry_definition(self, geometry_cfg: Dict[str, Any]) -> ET.Element:
        definition_cfg = geometry_cfg.get("definition")
        if definition_cfg is None:
            dp = geometry_cfg.get("dp")
            if dp is None:
                raise ValueError("geometry.definition or geometry.dp must be provided")
            domain = geometry_cfg.get("domain", {})
            definition_cfg = {
                "attributes": {"dp": dp},
                "children": []
            }
            if "min" in domain:
                definition_cfg["children"].append({"tag": "pointmin", "vector": domain["min"]})
            if "max" in domain:
                definition_cfg["children"].append({"tag": "pointmax", "vector": domain["max"]})
        if isinstance(definition_cfg, dict) and (definition_cfg.get("tag") or definition_cfg.get("name")):
            definition_node = build_generic_node(definition_cfg)
        else:
            attributes = dict(definition_cfg.get("attributes", {})) if isinstance(definition_cfg, dict) else {}
            children_specs: List[Dict[str, Any]] = []
            if isinstance(definition_cfg, dict):
                for key, value in definition_cfg.items():
                    if key in {"attributes", "children"}:
                        continue
                    if looks_like_vector(value):
                        children_specs.append({"tag": key, "vector": value})
                    elif isinstance(value, dict) and (value.get("tag") or value.get("name")):
                        children_specs.append(value)
                    elif isinstance(value, list):
                        for item in value:
                            children_specs.append({"tag": key, "text": item})
                    else:
                        attributes[key] = value
                children_specs.extend(definition_cfg.get("children", []))
            else:
                raise TypeError("geometry.definition must be a dict when provided")
            definition_node = element_with_attributes("definition", attributes)
            for child_spec in children_specs:
                definition_node.append(build_generic_node(child_spec))
        if "dp" not in definition_node.attrib:
            raise ValueError("definition.dp attribute is required")
        return definition_node

    def _build_geometry_commands(self, geometry_cfg: Dict[str, Any]) -> Optional[ET.Element]:
        commands_cfg = geometry_cfg.get("commands")
        objects_cfg = geometry_cfg.get("objects")
        if not commands_cfg and not objects_cfg:
            return None
        node = ET.Element("commands")
        if commands_cfg:
            for list_cfg in commands_cfg.get("lists", []):
                list_attributes = {
                    key: value
                    for key, value in list_cfg.items()
                    if key not in {"commands", "children"}
                }
                list_node = element_with_attributes("list", list_attributes)
                for command in list_cfg.get("commands", []):
                    list_node.append(self._build_command(command))
                for child_spec in list_cfg.get("children", []):
                    list_node.append(build_generic_node(child_spec))
                node.append(list_node)
            mainlist_commands = commands_cfg.get("mainlist")
        else:
            mainlist_commands = None
        if mainlist_commands is None and objects_cfg:
            mainlist_commands = self._objects_to_commands(objects_cfg)
        if mainlist_commands:
            mainlist_node = ET.SubElement(node, "mainlist")
            for command in mainlist_commands:
                mainlist_node.append(self._build_command(command))
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
            box_children = [
                {"tag": "boxfill", "text": obj.get("fill_mode", "solid")},
                {"tag": "point", "vector": obj.get("position", {})},
                {"tag": "size", "vector": obj.get("size", {})},
            ]
            commands.append({"type": "drawbox", "children": box_children})
        return commands

    def _build_command(self, command_config: Dict[str, Any]) -> ET.Element:
        if not isinstance(command_config, dict):
            raise TypeError(f"Command specification must be a dict, got {type(command_config)!r}")
        command_type = command_config.get("type")
        if not command_type:
            raise ValueError(f"Command specification missing 'type': {command_config}")
        node = element_with_attributes(command_type, command_config.get("attributes", {}))
        for child_spec in command_config.get("children", []):
            node.append(build_generic_node(child_spec))
        for extra_spec in command_config.get("extra", []):
            node.append(build_generic_node(extra_spec))
        if command_config.get("text") is not None:
            node.text = stringify(command_config["text"])
        return node

    def _build_section_list(self, section_key: str) -> Optional[ET.Element]:
        specs_config = self.config.get(section_key)
        if not specs_config:
            return None
        if isinstance(specs_config, dict):
            entries = specs_config.get('entries')
            if entries is None:
                entries = [specs_config]
        else:
            entries = specs_config
        node = ET.Element(section_key)
        for spec in entries:
            node.append(build_generic_node(spec))
        return node

    def _build_execution(self) -> ET.Element:
        execution = element_with_attributes("execution", self.config.get("execution_attributes", {}))
        exec_config = self.config.get("execution", {})
        parameters = exec_config.get("parameters")
        if parameters:
            execution.append(self._build_parameters(parameters))
        special_node: Optional[ET.Element] = None
        gauges = exec_config.get("gauges")
        if gauges:
            if special_node is None:
                special_node = ET.Element("special")
            special_node.append(self._build_gauges(gauges))
        timeout_cfg = exec_config.get("timeout")
        if timeout_cfg:
            if special_node is None:
                special_node = ET.Element("special")
            special_node.append(self._build_timeout(timeout_cfg))
        for spec in exec_config.get("special", []):
            if special_node is None:
                special_node = ET.Element("special")
            special_node.append(build_generic_node(spec))
        special_sections = {
            "wavepaddles": exec_config.get("wavepaddles"),
            "activeabsorption": exec_config.get("active_absorption") or exec_config.get("activeabsorption"),
            "passiveabsorption": exec_config.get("passive_absorption") or exec_config.get("passiveabsorption"),
            "relaxationzones": exec_config.get("relaxation_zones") or exec_config.get("relaxationzones"),
            "particlefilter": exec_config.get("particle_filters") or exec_config.get("particlefilter"),
        }
        for tag, cfg in special_sections.items():
            if cfg:
                if special_node is None:
                    special_node = ET.Element("special")
                special_node.append(self._build_special_section(tag, cfg))
        if special_node is not None and len(special_node):
            execution.append(special_node)
        for spec in exec_config.get("extra_nodes", []):
            execution.append(build_generic_node(spec))
        return execution

    def _build_parameters(self, parameters_config: Any) -> ET.Element:
        node = ET.Element("parameters")
        if isinstance(parameters_config, dict):
            for key, value in parameters_config.items():
                if value is None:
                    continue
                if isinstance(value, dict):
                    attributes = {"key": key}
                    attributes.update(value)
                else:
                    attributes = {"key": key, "value": value}
                node.append(element_with_attributes("parameter", attributes))
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
            if "start" in gauge:
                gauge_element.append(build_generic_node({"tag": "point0", "vector": gauge["start"]}))
            if "end" in gauge:
                gauge_element.append(build_generic_node({"tag": "point2", "vector": gauge["end"]}))
            for child_spec in gauge.get("children", []):
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
    rough = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="    ")


def write_case(config_path: Path, output_path: Path) -> None:
    config = load_config(config_path)
    builder = CaseBuilder(config)
    xml_string = serialize_xml(builder.build())
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