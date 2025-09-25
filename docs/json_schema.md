# DualSPHysics Case JSON Schema Guide

This guide documents the JSON structure accepted by AutoXml_script/generate_xml.py (September 2025 build). The script mirrors the DualSPHysics XML described in XML_GUIDE_v5.4.pdf and the reference templates shipped in AutoXml_script.

## Top-Level Layout

| Key | Type | Notes |
| --- | --- | --- |
| case_attributes | object | Optional attributes copied onto <case ...> (for example pp, date). |
| casedef_attributes | object | Optional attributes for <casedef ...>. |
| constants | object | Required. Scalars become <name value="…"/>; dictionaries are treated as node specs so you can add attributes/children; vectors (x,y,z) expand automatically. Based on Guide §2.2 (pp. 9–17). |
| mkconfig | object | Optional. Accepts oundcount, luidcount, and an orientations list such as {"type": "bound", "mk": 0, "orient": "YxZ"} (see Guide p. 18). |
| patterns | array<object> | Optional <patterns> catalogue including optional size, scale, gap, and order vectors. |
| geometry | object | Required. Builds <geometry> including predefinition, definition, commands, objects (legacy), and extra. |
| initials, loatings, motion | list or dict | Optional <initials>, <floatings>, <motion> blocks. Entries can be full node specs or simplified dictionaries using 	ype/ector. |
| casedef_extra | list | Appended verbatim under <casedef> for advanced features (e.g. <normals>). |
| execution | object | Optional <execution> configuration (parameters, gauges, timeout, special features). |
| execution_attributes | object | Optional attributes applied to <execution ...>. |
| execution.extra_nodes | list | Additional nodes appended after <execution>’s special block. |

### Generic Node Specification

Any section that accepts "generic" nodes (constants, commands, initials, specials, etc.) can use the following helpers:

`json
{
  "type": "velocity",                  // or "tag" / "name"
  "attributes": {"mkfluid": 0, "x": 0.1},
  "vector": {"x": 1, "y": 0, "z": 0},    // optional convenience for x/y/z
  "text": "optional inner text",
  "children": [ { "type": "onlypos", ... } ],
  "extra": [ ... ],                      // appended after children
  "customKey": { ... }                   // promoted to child <customKey .../>
}
`

The builder automatically converts leftover scalar fields into attributes and nested dictionaries/lists into child nodes. This makes it straightforward to translate examples from the PDF directly into JSON.

## Geometry

### Definition

Specify either a ready-made definition block or the high-level dp/domain keys:

`json
"geometry": {
  "definition": {
    "attributes": {"dp": 0.01},
    "children": [
      {"type": "pointref",  "vector": {"x": 0, "y": 0, "z": 0}},
      {"type": "pointmin",  "vector": {"x": -1, "y": 0, "z": -1}},
      {"type": "pointmax",  "vector": {"x": 4.5, "y": 0, "z": 3.5}}
    ]
  }
}
`

If definition is omitted, set dp and domain.min / domain.max; the script injects <pointmin> / <pointmax> automatically (Guide §2.4.1).

### Commands

geometry.commands can declare auxiliary <list> blocks along with the <mainlist> draw pipeline. Each command dictionary must include 	ype and may declare ttributes, children, 	ext, or extra. Example:

`json
"commands": {
  "lists": [
    {
      "name": "StructureList",
      "commands": [
        {"type": "resetdraw"},
        {"type": "runlist", "attributes": {"name": "BoxList", "times": 5}}
      ]
    }
  ],
  "mainlist": [
    {"type": "setmkfluid", "attributes": {"mk": 0}},
    {
      "type": "drawbox",
      "children": [
        {"type": "boxfill", "text": "solid"},
        {"type": "point",  "vector": {"x": 0, "y": -1, "z": 0}},
        {"type": "size",   "vector": {"x": 1, "y": 2, "z": 2}}
      ]
    }
  ]
}
`

Legacy geometry.objects (list of boxes with 	ype, mk, position, size, ill_mode) is still supported and is expanded internally into the same <mainlist> commands.

### Predefinition & Extras

- geometry.predefinition: supply either a list of node specs or a dictionary with entries to populate <predefinition> (useful for <newvarcte> variables).
- geometry.extra: optional nodes appended after <commands> for advanced constructs such as <layers> or <redraw>.

## Initials, Floatings, Motion

Each of these sections accepts either a list of node specs or a dictionary. Examples:

`json
"initials": [
  {"type": "velocity", "mkfluid": 0, "x": 0.2, "y": 0.0, "z": 0.0},
  {
    "type": "rotateaxis",
    "attributes": {"mkbound": 0, "angle": 45, "anglesunits": "degrees"},
    "children": [
      {"type": "axisp1", "vector": {"x": 0, "y": 0, "z": 0}},
      {"type": "axisp2", "vector": {"x": 0, "y": 1, "z": 0}}
    ]
  }
],
"floatings": {
  "entries": [
    {"type": "floating", "attributes": {"mkbound": 0, "rhopbody": 1300}},
    {
      "type": "floating",
      "attributes": {"mkbound": 1, "property": "Material_1"},
      "children": [
        {"type": "massbody", "attributes": {"value": 1.3}},
        {"type": "inertia", "vector": {"x": 11, "y": 12, "z": 13}}
      ]
    }
  ]
},
"motion": [
  {
    "type": "obj",
    "children": [
      {"type": "begin", "attributes": {"mov": 1, "start": 0}},
      {
        "type": "mvrect",
        "attributes": {"id": 1, "duration": 1},
        "children": [
          {"type": "vel", "vector": {"x": 0.5, "y": 0.0, "z": 0.0}}
        ]
      }
    ]
  }
]
`

## Execution

### Parameters & Gauges

- execution.parameters: dict or list. Scalars become <parameter key="..." value="..."/>; dictionaries merge additional attributes (e.g. units_comment).
- execution.gauges: list of gauge specs where start → <point0> and end → <point2> automatically. Additional child nodes can be provided via children.
- execution.timeout: wrapper that produces <special><timeout><tout ... /></timeout></special> with optional ttributes and entries.

### Special Features

The script supports several convenience keys that expand into <execution><special>...</special></execution> content:

| JSON key | XML wrapper | Notes |
| --- | --- | --- |
| wavepaddles | <wavepaddles> | Accepts a dict ({"piston": {...}}), list, or node spec. Use children to describe piston/flap settings (Guide §3.1.4). |
| ctive_absorption / ctiveabsorption | <activeabsorption> | Provide attributes/children as needed for the absorption system. |
| passive_absorption / passiveabsorption | <passiveabsorption> | Same pattern as above. |
| elaxation_zones / elaxationzones | <relaxationzones> | Wrapper for regular/irregular/offline relaxation zones (Guide §3.1.5). Supports ttributes, entries, or direct node specs. |
| particle_filters / particlefilter | <particlefilter> | Configure output filters (ilterpos, ilterplane, operation, etc.) as documented in Guide §3.1.10. |
| special | (varies) | You can still pass a raw list of node specs if you prefer to control everything manually. |

Each entry can be expressed as a list, a dictionary with entries/children, or a single node spec ({"type": "piston", ...}). Arbitrary scalar fields are converted into attributes, and nested dicts/lists become child nodes, so JSON closely mirrors the XML examples.

### Extras

- execution.extra_nodes: appended after the special block. Handy for features like <particledata> or bespoke extensions.

## Validation & Testing

1. Unit tests in 	ests/test_generate_xml.py verify:
   - Geometry fallback (dp + domain).
   - mkconfig, patterns, timeout generation.
   - Gauges, wave paddles, relaxation zones, particle filters, and initials/floatings/motion mappings.
2. Every test spawns the generator, parses the resulting XML with ElementTree, and asserts on structure/attributes, catching schema errors early.
3. Extend coverage by adding new JSON fixtures that match worked examples from the PDF (e.g. polyhedron masks, hierarchical motions) as your projects require.

## Future Enhancements

- Provide shorthands for frequent draw commands (automatic child generation for drawtriangle, drawprism, etc.).
- Offer optional schema validation (e.g. pydantic, jsonschema) for early feedback.
- Maintain a library of ready-to-use JSON snippets covering the most common GenCase scenarios (paddles, relaxation zones, floatings, motions).