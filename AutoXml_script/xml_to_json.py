"""Convert DualSPHysics Case_Def XML back into the JSON schema used by generate_xml."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from lxml import etree as ET


VECTOR_KEYS = {"x", "y", "z"}
GAUGE_POINT_MAP = {"point0": "start", "point1": "mid", "point2": "end"}


def _convert_value(text: str) -> Any:
    value = text.strip()
    if not value:
        return ""
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    # Return original string to preserve formatting like "1.20" vs "1.2"
    return value


def _convert_attrib(attributes: Dict[str, str]) -> Dict[str, Any]:
    return {key: _convert_value(value) for key, value in attributes.items()}


def _is_vector_attributes(attributes: Dict[str, Any]) -> bool:
    return bool(attributes) and set(attributes.keys()) <= VECTOR_KEYS


def _get_text(element: ET.Element) -> Optional[Any]:
    if element.text is None:
        return None
    stripped = element.text.strip()
    if not stripped:
        return None
    return _convert_value(stripped)


def _generic_from_element(element: ET.Element) -> Dict[str, Any]:
    if isinstance(element, ET._Comment):
        return {"tag": "comment", "text": element.text}

    spec: Dict[str, Any] = {"tag": element.tag}
    attributes = _convert_attrib(element.attrib)
    if attributes:
        if _is_vector_attributes(attributes):
            spec["vector"] = attributes
        else:
            spec.update(attributes)
    text_value = _get_text(element)
    if text_value is not None:
        spec["text"] = text_value
    children = [_generic_from_element(child) for child in element]
    if children:
        spec["children"] = children
    return spec


def _parse_constants(constants_elem: ET.Element) -> Dict[str, Any]:
    constants: Dict[str, Any] = {}
    for child in constants_elem:
        name = child.tag
        attrs = _convert_attrib(child.attrib)
        text_value = _get_text(child)
        if not list(child) and text_value is None:
            if "value" in attrs and len(attrs) == 1:
                constants[name] = attrs["value"]
                continue
            if _is_vector_attributes(attrs):
                constants[name] = attrs
                continue
        spec = _generic_from_element(child)
        spec.pop("tag", None)
        spec.setdefault("tag", name)
        constants[name] = spec
    return constants


def _parse_mkconfig(mk_elem: ET.Element) -> Dict[str, Any]:
    mkconfig: Dict[str, Any] = {}
    mkconfig.update(_convert_attrib(mk_elem.attrib))
    orientations: List[Dict[str, Any]] = []
    extra: List[Dict[str, Any]] = []
    for child in mk_elem:
        if child.tag.startswith("mkorient"):
            orient_type = child.tag.replace("mkorient", "")
            orientation = {"type": orient_type}
            orientation.update(_convert_attrib(child.attrib))
            orientations.append(orientation)
        else:
            extra.append(_generic_from_element(child))
    if orientations:
        mkconfig["orientations"] = orientations
    if extra:
        mkconfig["extra"] = extra
    return mkconfig


def _parse_patterns(patterns_elem: ET.Element) -> List[Dict[str, Any]]:
    patterns: List[Dict[str, Any]] = []
    for pattern_elem in patterns_elem.findall("pattern"):
        pattern_cfg: Dict[str, Any] = _convert_attrib(pattern_elem.attrib)
        for child in pattern_elem:
            tag = child.tag.lower()
            attrs = _convert_attrib(child.attrib)
            if tag in {"size", "scale", "gap", "border"} and _is_vector_attributes(attrs):
                pattern_cfg[tag] = attrs
            else:
                pattern_cfg.setdefault("children", []).append(_generic_from_element(child))
        patterns.append(pattern_cfg)
    return patterns


def _parse_predefinition(predef_elem: ET.Element) -> List[Dict[str, Any]]:
    return [_generic_from_element(child) for child in predef_elem]


def _parse_definition(definition_elem: ET.Element) -> Dict[str, Any]:
    attrs = _convert_attrib(definition_elem.attrib)
    dp_value = attrs.pop("dp", None)
    if dp_value is None:
        raise ValueError("definition element missing dp attribute")

    meta: Dict[str, Any] = {}
    comment = attrs.pop("comment", None)
    if comment is not None:
        meta["comment"] = comment
    units = attrs.pop("units_comment", None)
    if units is not None:
        meta["units_comment"] = units

    pointmin_vec = None
    pointmax_vec = None
    children: List[Dict[str, Any]] = []

    for child in definition_elem:
        if isinstance(child, ET._Comment):
            children.append(_generic_from_element(child))
            continue
        if child.tag == "pointmin":
            pointmin_vec = _convert_attrib(child.attrib)
            continue
        if child.tag == "pointmax":
            pointmax_vec = _convert_attrib(child.attrib)
            continue
        children.append(_generic_from_element(child))

    if pointmin_vec is None or pointmax_vec is None:
        raise ValueError("definition element requires pointmin and pointmax nodes")

    definition_cfg: Dict[str, Any] = {
        "dp": dp_value,
        "pointmin": pointmin_vec,
        "pointmax": pointmax_vec,
    }
    if meta:
        definition_cfg["meta"] = meta
    if children:
        definition_cfg["children"] = children
    return definition_cfg
def _parse_command(command_elem: ET.Element) -> Dict[str, Any]:
    spec = _generic_from_element(command_elem)
    command: Dict[str, Any] = {"type": spec.pop("tag")}
    attributes: Dict[str, Any] = {}
    for key in list(spec.keys()):
        if key in {"children", "extra", "vector", "text"}:
            continue
        attributes[key] = spec.pop(key)
    if attributes:
        command["attributes"] = attributes
    if "vector" in spec:
        vector_attrs = spec.pop("vector")
        command.setdefault("attributes", {}).update(vector_attrs)
    if "children" in spec:
        command["children"] = spec["children"]
    if "extra" in spec:
        command["extra"] = spec["extra"]
    if "text" in spec:
        command["text"] = spec["text"]
    return command


def _parse_commands(commands_elem: ET.Element) -> List[Dict[str, Any]]:
    """More generic parser that preserves order of lists, mainlist, and comments."""
    parsed = []
    for child in commands_elem:
        if isinstance(child, ET._Comment):
            parsed.append(_generic_from_element(child))
            continue

        if child.tag == "list":
            list_cfg = {"tag": "list", "attributes": _convert_attrib(child.attrib)}
            list_commands = [_parse_command(cmd) for cmd in child]
            if list_commands:
                list_cfg["children"] = list_commands
            parsed.append(list_cfg)
        elif child.tag == "mainlist":
            mainlist_cfg = {"tag": "mainlist"}
            mainlist_commands = [_parse_command(cmd) for cmd in child]
            if mainlist_commands:
                mainlist_cfg["children"] = mainlist_commands
            parsed.append(mainlist_cfg)
        else:
            # For any other unexpected tags
            parsed.append(_generic_from_element(child))
    return parsed


def _parse_section_list(section_elem: ET.Element) -> List[Dict[str, Any]]:
    entries = []
    for child in section_elem:
        spec = _generic_from_element(child)
        spec.setdefault("type", spec.pop("tag", child.tag))
        entries.append(spec)
    return entries


def _parse_timeout(timeout_elem: ET.Element) -> Dict[str, Any]:
    timeout_cfg: Dict[str, Any] = {"attributes": _convert_attrib(timeout_elem.attrib)}
    entries = [_convert_attrib(entry.attrib) for entry in timeout_elem.findall("tout")]
    if entries:
        timeout_cfg["entries"] = entries
    children = [child for child in timeout_elem if child.tag != "tout"]
    if children:
        timeout_cfg["children"] = [_generic_from_element(child) for child in children]
    return timeout_cfg


def _parse_gauges(gauges_elem: ET.Element) -> List[Dict[str, Any]]:
    gauges: List[Dict[str, Any]] = []
    for gauge_elem in gauges_elem:
        gauge: Dict[str, Any] = {"type": gauge_elem.tag}
        attrs = _convert_attrib(gauge_elem.attrib)
        if "name" in attrs:
            gauge["name"] = attrs.pop("name")
        if attrs:
            gauge["attributes"] = attrs
        extra_children: List[Dict[str, Any]] = []
        ordered_children: List[Dict[str, Any]] = []
        for child in gauge_elem:
            if child.tag in GAUGE_POINT_MAP:
                gauge[GAUGE_POINT_MAP[child.tag]] = _convert_attrib(child.attrib)
                ordered_children.append({"type": "mapped", "key": GAUGE_POINT_MAP[child.tag], "tag": child.tag})
            elif child.tag == "pointdp": # Handle this specific case
                spec = _generic_from_element(child)
                gauge.setdefault("children", []).append(spec)
                ordered_children.append({"type": "generic", "spec": spec})
            else:
                spec = _generic_from_element(child)
                extra_children.append(spec)
                ordered_children.append({"type": "generic", "spec": spec})
        if extra_children:
            gauge.setdefault("children", []).extend(extra_children)
        if ordered_children:
            gauge["children_plan"] = ordered_children
        gauges.append(gauge)
    return gauges


def _parse_special_section(section_elem: ET.Element) -> Dict[str, Any]:
    section_cfg: Dict[str, Any] = {}
    attrs = _convert_attrib(section_elem.attrib)
    if attrs:
        section_cfg["attributes"] = attrs
    entries = [_generic_from_element(child) for child in section_elem]
    if entries:
        section_cfg["entries"] = entries
    return section_cfg


SPECIAL_SECTION_TAGS = {
    "wavepaddles": "wavepaddles",
    "activeabsorption": "active_absorption",
    "active_absorption": "active_absorption",
    "passiveabsorption": "passive_absorption",
    "passive_absorption": "passive_absorption",
    "relaxationzones": "relaxation_zones",
    "relaxation_zones": "relaxation_zones",
    "particlefilter": "particle_filters",
    "particle_filters": "particle_filters",
}


def _parse_special(special_elem: ET.Element) -> Dict[str, Any]:
    special_cfg: Dict[str, Any] = {}
    extras: List[Dict[str, Any]] = []
    ordered_children: List[Dict[str, Any]] = []
    for child in special_elem:
        if isinstance(child, ET._Comment):
            comment_spec = _generic_from_element(child)
            extras.append(comment_spec)
            ordered_children.append({"type": "generic", "spec": comment_spec})
            continue
        mapped_key = SPECIAL_SECTION_TAGS.get(child.tag)
        if child.tag == "gauges":
            special_cfg["gauges"] = _parse_gauges(child)
            ordered_children.append({"type": "known", "key": "gauges", "tag": child.tag})
        elif child.tag == "timeout":
            special_cfg["timeout"] = _parse_timeout(child)
            ordered_children.append({"type": "known", "key": "timeout", "tag": child.tag})
        elif mapped_key == "wavepaddles":
            special_cfg[mapped_key] = _parse_special_section(child)
            ordered_children.append({"type": "known", "key": mapped_key, "tag": child.tag})
        elif mapped_key in {"active_absorption", "passive_absorption", "relaxation_zones", "particle_filters"}:
            special_cfg[mapped_key] = _parse_special_section(child)
            ordered_children.append({"type": "known", "key": mapped_key, "tag": child.tag})
        else:
            spec = _generic_from_element(child)
            extras.append(spec)
            ordered_children.append({"type": "generic", "spec": spec})
    if extras:
        special_cfg["special"] = extras
    if ordered_children:
        special_cfg["special_children"] = ordered_children
    return special_cfg


def _merge_execution_parts(base: Dict[str, Any], special_cfg: Dict[str, Any]) -> None:
    for key, value in special_cfg.items():
        if key == "gauges":
            base["gauges"] = value
        elif key == "timeout":
            base["timeout"] = value
        elif key == "special":
            base.setdefault("special", []).extend(value)
        elif key == "special_children":
            base["special_children"] = list(value)
        else:
            base[key] = value


def parse_case_xml(xml_text: str) -> Dict[str, Any]:
    parser = ET.XMLParser(remove_blank_text=True, resolve_entities=False, strip_cdata=False)
    try:
        root = ET.fromstring(xml_text.encode("utf-8"), parser=parser)
    except ET.XMLSyntaxError:
        root = ET.fromstring(xml_text, parser=parser)

    if root.tag != "case":
        raise ValueError("Root element must be <case>")

    config: Dict[str, Any] = {}
    case_attrs = _convert_attrib(root.attrib)
    if case_attrs:
        config["case_attributes"] = case_attrs

    casedef = root.find("casedef")
    casedef_children_order: List[Dict[str, Any]] = []

    if casedef is not None:
        casedef_attrs = _convert_attrib(casedef.attrib)
        if casedef_attrs:
            config["casedef_attributes"] = casedef_attrs

        for child in casedef:
            if child.tag == "constantsdef":
                constants = _parse_constants(child)
                if constants:
                    config["constants"] = constants
                casedef_children_order.append({"type": "section", "key": "constants"})
            elif child.tag == "mkconfig":
                mkconfig = _parse_mkconfig(child)
                if mkconfig:
                    config["mkconfig"] = mkconfig
                casedef_children_order.append({"type": "section", "key": "mkconfig"})
            elif child.tag == "patterns":
                patterns = _parse_patterns(child)
                if patterns:
                    config["patterns"] = patterns
                casedef_children_order.append({"type": "section", "key": "patterns"})
            elif child.tag == "geometry":
                geometry_cfg: Dict[str, Any] = {}
                for geo_child in child:
                    if geo_child.tag == "predefinition":
                        entries = _parse_predefinition(geo_child)
                        if entries:
                            geometry_cfg["predefinition"] = entries
                    elif geo_child.tag == "definition":
                        geometry_cfg["definition"] = _parse_definition(geo_child)
                    elif geo_child.tag == "commands":
                        commands_children = _parse_commands(geo_child)
                        if commands_children:
                            geometry_cfg["commands"] = {"children": commands_children}
                    else:
                        geometry_cfg.setdefault("extra", []).append(_generic_from_element(geo_child))
                if geometry_cfg:
                    config["geometry"] = geometry_cfg
                casedef_children_order.append({"type": "section", "key": "geometry"})
            elif child.tag in {"initials", "floatings", "motion"}:
                if list(child): 
                    config[child.tag] = _parse_section_list(child)
                casedef_children_order.append({"type": "section", "key": child.tag})
            elif isinstance(child, ET._Comment):
                 spec = _generic_from_element(child)
                 config.setdefault("casedef_extra", []).append(spec)
                 casedef_children_order.append({"type": "generic", "spec": spec})
            else:
                 spec = _generic_from_element(child)
                 config.setdefault("casedef_extra", []).append(spec)
                 casedef_children_order.append({"type": "generic", "spec": spec})

    if casedef_children_order:
        config["casedef_children"] = casedef_children_order

    execution_elem = root.find("execution")
    if execution_elem is not None:
        exec_attrs = _convert_attrib(execution_elem.attrib)
        if exec_attrs:
            config["execution_attributes"] = exec_attrs

        exec_cfg: Dict[str, Any] = {}
        exec_cfg["children_order"] = [child.tag for child in execution_elem]
        exec_children = []

        for child in execution_elem:
            if child.tag == "parameters":
                parameters_order: List[str] = []
                parameters_children: List[Dict[str, Any]] = []
                parameters: Dict[str, Any] = {}
                for param in child:
                    if isinstance(param, ET._Comment):
                        comment_spec = _generic_from_element(param)
                        parameters_children.append({"type": "generic", "spec": comment_spec})
                        continue
                    if param.tag != "parameter":
                        spec = _generic_from_element(param)
                        parameters_children.append({"type": "generic", "spec": spec})
                        continue
                    attrs = _convert_attrib(param.attrib)
                    key = attrs.pop("key", None)
                    if key is None:
                        continue
                    if not attrs:
                        if list(param):
                             parameters[key] = _generic_from_element(param)
                             parameters_order.append(key)
                             parameters_children.append({"type": "parameter", "key": key})
                        else:
                             continue
                    elif set(attrs.keys()) == {"value"}:
                        parameters[key] = attrs["value"]
                        parameters_order.append(key)
                        parameters_children.append({"type": "parameter", "key": key})
                    else:
                        parameters[key] = attrs
                        parameters_order.append(key)
                        parameters_children.append({"type": "parameter", "key": key})
                if parameters:
                    exec_cfg["parameters"] = parameters
                if parameters_order:
                    exec_cfg["parameters_order"] = parameters_order
                if parameters_children:
                    exec_cfg["parameters_children"] = parameters_children
            elif child.tag == "special":
                special_cfg = _parse_special(child)
                _merge_execution_parts(exec_cfg, special_cfg)
            else:
                 exec_children.append(_generic_from_element(child))

        if exec_children:
            exec_cfg.setdefault("extra_nodes", []).extend(exec_children)
        if exec_cfg:
            config["execution"] = exec_cfg

    return config


def parse_case_file(path: Path) -> Dict[str, Any]:
    xml_text = path.read_text(encoding="utf-8")
    return parse_case_xml(xml_text)


def write_config(config: Dict[str, Any], path: Path, *, indent: int = 2) -> None:
    path.write_text(json.dumps(config, indent=indent, ensure_ascii=False), encoding="utf-8")


def _parse_args(argv: Optional[List[str]] = None):
    import argparse

    parser = argparse.ArgumentParser(description="Convert DualSPHysics Case_Def XML to JSON config.")
    parser.add_argument("input", type=Path, help="Path to the Case_Def XML file")
    parser.add_argument("output", type=Path, nargs="?", help="Optional destination JSON path")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation level (default: 2)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    config = parse_case_file(args.input)
    if args.output:
        write_config(config, args.output, indent=args.indent)
    else:
        print(json.dumps(config, indent=args.indent, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
