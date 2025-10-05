# AutoXML JSON Schema Notes

This document describes the JSON structures produced by `xml_to_json.py` and consumed by `generate_xml.py`. The goal is a lossless XML → JSON → XML roundtrip for DualSPHysics case files.

## Conventions
- All attribute and text values are stored as strings; booleans remain booleans. Preserve original formatting (e.g., `"1.20"`).
- Comments and element order are kept using generic node specs (`{"tag": "comment", "text": "…"}`) and explicit ordering lists.
- Element names should remain XML-safe. Use the JSON dict key as the canonical tag name, and put human-readable descriptions or units in a `label` field rather than in `tag`.
- Generic node spec fields:
  - `tag` / `type` / `name`: XML element name.
  - `attributes`: dict of attributes.
  - `vector`: dict with some subset of `x`, `y`, `z`.
  - `text`: textual content.
  - `children`: ordered list of nested specs.
  - `extra`: additional child specs inserted after `children`.

## Top-Level Keys
| Key | Meaning |
| --- | --- |
| `case_attributes` | Attributes from `<case>`.
| `casedef_attributes` | Attributes from `<casedef>`.
| `casedef_children` | Ordered list describing sections/comments inside `<casedef>`.
| `execution_attributes` | Attributes from `<execution>`.
| `execution` | Dict describing parameters, special sections, and extras.

## `<casedef>` Structure
- `constants`: mapping `name` → scalar/vector/object. The JSON key becomes the XML element name. Optional `label` strings are split into `comment` (text before brackets) and `units_comment` (text inside brackets). You can provide `comment`, `units_comment`, or `auto` explicitly to override inferred values. Avoid supplying a `tag` override unless it already matches the XML naming pattern (`[A-Za-z_][A-Za-z0-9_.-]*`); otherwise it will be sanitized.
- `mkconfig`: attributes plus `orientations` (each `{type, …}`) and optional `extra` list.
- `patterns`: list of pattern dicts with vector children (`size`, `scale`, `gap`, `border`) and optional generic `children`.
- `geometry`:
  - `predefinition`: list of generic specs or a dict with `entries`.
  - `definition`: dict with `attributes`, optional vector children (`pointmin`, etc.), and `children` list.
  - `commands`: `{"children": [ ... ]}` where each child is a generic node; comments and order preserved.
  - `extra`: additional nodes under `<geometry>`.
- `initials`, `floatings`, `motion`: list (or dict with `entries` / `children`) of generic specs.
- `casedef_extra`: generic specs for unexpected nodes or top-level comments.
- `casedef_children`: list preserving original order. Entries:
  - `{"type": "section", "key": "constants" | "mkconfig" | … }`
  - `{"type": "generic", "spec": <generic node>}`

## `<execution>` Structure
```
execution = {
  "children_order": ["parameters", "special", "extra_nodes", ...],
  "parameters": { ... },
  "parameters_order": [ ... ],
  "parameters_children": [ ... ],
  "gauges": [ ... ],
  "timeout": { ... },
  "wavepaddles": { ... },
  "active_absorption": { ... },
  "passive_absorption": { ... },
  "relaxation_zones": { ... },
  "particle_filters": { ... },
  "special": [ ... ],
  "special_children": [ ... ],
  "extra_nodes": [ ... ]
}
```

### Parameters
- Stored as dict `key -> value`.
- `parameters_order`: preserves original parameter order.
- `parameters_children`: ordered plan mixing parameters and generic nodes:
  - `{"type": "parameter", "key": "TimeOut"}`
  - `{"type": "generic", "spec": <generic>}` (comments, custom nodes such as `<simulationdomain>`)
- Generator uses this plan to rebuild `<parameters>` exactly.

### Special Block
- `special_children`: ordered sequence of known sections and generic nodes. Entries:
  - `{"type": "known", "key": "gauges", "tag": "gauges"}`
  - `{"type": "generic", "spec": <generic>}`
- Known keys map normalized names to XML tags:
  - `active_absorption` ↔ `<activeabsorption>`
  - `passive_absorption` ↔ `<passiveabsorption>`
  - `relaxation_zones` ↔ `<relaxationzones>`
  - `particle_filters` ↔ `<particlefilter>`
- If `special_children` is absent, generator falls back to the legacy ordering list.

### Gauges
- Each gauge dict contains:
  - `type`: XML element name (e.g., `swl`).
  - `name`: optional; moves into attributes.
  - `attributes`: remaining attributes.
  - `start`, `mid`, `end`: vector dicts corresponding to `<point0>`, `<point1>`, `<point2>`.
  - `children`: list of generic nodes (e.g., `<pointdp>`).
  - `children_plan`: ordered plan mixing mapped points and generic nodes:
    - `{"type": "mapped", "key": "start", "tag": "point0"}`
    - `{"type": "generic", "spec": <generic>}`
- Generator uses `children_plan` to emit points/comments in the original order and still ensures optional `mid`→`point1` support.

### Timeout and Other Sections
- `timeout`: `{"attributes": {...}, "entries": [{...}, ...], "children": [generic...]}`
- `wavepaddles`, `active_absorption`, etc.: dicts with `attributes`, `entries` or `children`, and optional `extra` list of generic nodes.

### Extra Nodes
- `extra_nodes`: generic specs appended inside `<execution>` when nodes do not match known sections.

## Generic Node Reference
Example for a comment:
```
{"tag": "comment", "text": " generator hint "}
```
Example for a plain element with attributes and text:
```
{
  "tag": "setmkfluid",
  "attributes": {"mk": "0"},
  "text": "optional"
}
```

## Roundtrip Guarantee
- `python -m pytest -q tests/test_xml_roundtrip.py` must pass (one aggregate test; failures list offending XML files).
- Ensure any new parser changes keep order/plan data in sync with generator expectations.

## References
- Official template: `AutoXml_script/GenCase_CaseTemplate.xml`
- Detailed rules: `AutoXml_script/XML_GUIDE_v5.4.pdf`

## Extending Flexible Sections
- Update `schemas/dualsphysics_config_schema.json` to mark the section as flexible (set `additionalProperties` to `true` or remove the flag) while keeping `constants`, `mkconfig`, and `geometry.definition` locked.
- Extend the synonym maps in `scripts/mvp_direct_file_search.py` so the post-generation diff guard can treat explicitly mentioned keys as allowable changes.
- If the new section should bypass the locked-section diff, add an entry to `_extract_allowed_fixed_section_changes` describing how to detect explicit requests for that area.
