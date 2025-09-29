# DualSPHysics JSON to XML Generator

This package converts structured JSON into the XML layout consumed by DualSPHysics GenCase. It mirrors the hierarchy documented in `XML_GUIDE_v5.4.pdf` (March 2025) and the `_FmtXML_*` reference snippets that ship with DualSPHysics. The generator lives in `AutoXml_script/generate_xml.py`; this README explains how to run it, extend it, and test it.

## Quick Start

1. Prepare JSON input: edit `config.json` or create your own file that follows the schema below.
2. Generate XML:
   ```bash
   python AutoXml_script/generate_xml.py --config path/to/config.json --output AutoXml_script/case.xml
   ```
   This writes a fully formatted `<case>` document ready for GenCase and DualSPHysics.
3. Validate (requires `pytest`):
   ```bash
   pytest tests/test_generate_xml.py
   ```

## Config Library & Smoke Tests

A curated JSON library lives in `AutoXml_script/config_library/`. Each file captures a focused scenario drawn from our regression tests (geometry fallbacks, mkconfig patterns, gauges, motion, and execution specials). Use the `scripts/smoke_test_configs.py` helper to regenerate XML and optionally invoke the DualSPHysics harness:

```bash
# Dry-run: generate XML only
python scripts/smoke_test_configs.py --skip-solver \
       --output-dir AutoXml_script/generated_cases \
       --results AutoXml_script/generated_cases/results.json

# Full run (requires DualSPHysics binaries configured in tools/exec.py)
python scripts/smoke_test_configs.py --output-dir AutoXml_script/generated_cases
```

The script logs one line per config and writes a JSON summary when `--results` is supplied. Solver invocations capture any missing-binary errors so the run can proceed across the whole library.

## XML ⇄ JSON Round-Trips

The inverse converter `AutoXml_script/xml_to_json.py` reconstructs the JSON schema from an existing `Case_Def.xml`:

```bash
python AutoXml_script/xml_to_json.py AutoXml_script/_FmtXML__Parameters.xml \
       AutoXml_script/config_library/parameters_from_xml.json
```

`tests/test_generator_json_pipeline.py` now asserts a bijective round-trip across the JSON library: every `config → XML → config → XML` cycle produces identical XML and stable JSON, guaranteeing the two representations stay in sync.

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `config.json` | Path to the JSON configuration file. |
| `--output` | `case.xml` | Destination for the generated XML. |

Example with custom paths:
```bash
python AutoXml_script/generate_xml.py \
    --config configs/wave_tank.json \
    --output build/wave_tank_case.xml
```

## JSON Schema Overview

Every JSON file maps directly onto the DualSPHysics XML tree. Sections can use simple key/value pairs or detailed node specifications with nested children. The helper `build_generic_node()` accepts dictionaries like:
```json
{
  "type": "velocity",
  "attributes": {"mkfluid": 0, "x": 0.2},
  "vector": {"x": 1, "y": 0, "z": 0},
  "text": "optional text",
  "children": [ { "type": "onlypos", ... } ],
  "extra": [ ... ],
  "customKey": { "attributes": {"foo": 1} }
}
```
Scalar leftovers become attributes. Nested dicts/lists become child nodes. This matches the examples in the DualSPHysics guide, so you can translate XML snippets into JSON with minimal effort.

The subsections below highlight the top level keys that `CaseBuilder` understands (see `AutoXml_script/generate_xml.py`). For deep detail and guide page references, see `docs/json_schema.md`.

### Global Metadata

- `case_attributes`: copied onto `<case ...>`.
- `casedef_attributes`: applied to `<casedef ...>`.
- `execution_attributes`: applied to `<execution ...>`.

### `constants`

Dictionary of SPH constants under `<casedef><constantsdef>`:
```json
"constants": {
  "gravity": {"x": 0, "y": 0, "z": -9.81},
  "rhop0": 1000,
  "coefsound": {
    "attributes": {"value": 20, "comment": "Multiplier"}
  },
  "custom": {
    "type": "hswl",
    "attributes": {"value": 0, "auto": true}
  }
}
```
Vector style dicts (x, y, z) become attributes automatically. Complex dicts may add attributes, text, or children.

### `mkconfig`

Defines label and orientation metadata:
```json
"mkconfig": {
  "boundcount": 2,
  "fluidcount": 1,
  "orientations": [
    {"type": "bound", "mk": 0, "orient": "YxZ"},
    {"type": "fluid", "mk": 0, "orient": "Xyz"}
  ],
  "extra": [ {"type": "mkorientvoid", "mk": 5, "orient": "zyx"} ]
}
```

### `patterns`

Catalog of draw patterns. Entries may include vectors for `size`, `scale`, `gap`, and `border`, plus custom children.

### `geometry`

- `predefinition`: node specs inserted before `<definition>` (for example `<newvarcte>` values).
- `definition`: either a full node specification or shorthand using `dp` and `domain.min` / `domain.max`.
- `commands`: describes `<commands>` including `<list>` blocks and the `<mainlist>` draw pipeline.
- `objects`: legacy helper that converts box objects (`type`, `mk`, `position`, `size`, `fill_mode`) into `setmk*` + `drawbox` commands when no explicit `mainlist` is provided.
- `extra`: optional nodes appended after `<commands>`.

### `initials`, `floatings`, `motion`

Each section accepts a list of node specs or a dictionary containing an `entries` array. Example:
```json
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
}
```
Motion entries follow the same pattern for `<obj>`, `<objreal>`, `<mvrect>`, `<mvcir>`, file based motions, and so on.

### `casedef_extra`

Array of node specs appended under `<casedef>` for advanced features such as `<normals>` or `<properties>`.

### `execution`

- `parameters`: dictionary or list mapped to `<parameters><parameter ... /></parameters>`.
- `gauges`: list of gauge specs; `start` and `end` keys generate `<point0>` and `<point2>` automatically.
- `timeout`: dictionary describing `<timeout>` entries.
- `special`: raw list of node specs appended under `<special>`.
- Convenience keys handled by `_build_special_section`:
  - `wavepaddles`
  - `active_absorption` or `activeabsorption`
  - `passive_absorption` or `passiveabsorption`
  - `relaxation_zones` or `relaxationzones`
  - `particle_filters` or `particlefilter`
- `extra_nodes`: additional nodes appended after the `<special>` block (for example `<particledata>`).

## Code Map

- `build_generic_node()` (lines 51-106): generic dict-to-element translator.
- `CaseBuilder.build()` (lines 95-106): assembles the `<case>` root.
- `_build_constantsdef`, `_build_mkconfig`, `_build_patterns`, `_build_geometry`, `_build_section_list` (lines 114-334): create the `<casedef>` content.
- `_build_execution`, `_build_parameters`, `_build_gauges`, `_build_timeout`, `_build_special_section` (lines 326-437): produce the `<execution>` branch and special features.
- `main()` (lines 450-463): CLI entry point.

## Testing

`tests/test_generate_xml.py` contains five scenarios:

1. Geometry fallback (legacy `objects` support).
2. MK config, patterns, and timeout serialization.
3. Execution parameters and gauges with extra attributes.
4. Initials, floatings, and motion structures.
5. Special features (`wavepaddles`, `relaxationzones`, `particlefilter`).

Run all tests after modifying the generator or schema docs:
```bash
pytest tests/test_generate_xml.py
```

## Sample Configuration

`config.json` illustrates most capabilities:

- Case metadata (`app`, `date`).
- SPH constants, mkconfig orientations, and geometry definition.
- Initial velocities and boundary rotations.
- Floating bodies with mass and inertia details.
- A motion object with rectilinear movement.
- Execution parameters, gauges, timeout schedule, piston wave paddles, a relaxation zone, and a particle filter.

Use it as a template: copy, adjust sections, regenerate XML.

## Troubleshooting

- Missing required fields raise `ValueError` (for example missing `geometry.dp`).
- Legacy `geometry.objects` currently supports only `shape: "box"`; use `geometry.commands` for other shapes.
- Files are UTF-8; ensure your editor preserves that encoding.
- After generating XML, run GenCase or the DualSPHysics CLI for a full physics check.

## Extending the Generator

- Map new JSON keys to `_build_special_section` or introduce dedicated helpers in `CaseBuilder`.
- Update `docs/json_schema.md` and add pytest coverage whenever the schema changes.
- To support new XML structures, model their JSON representation on the guide examples and rely on `build_generic_node()` to handle the translation.

## Related Resources

- `docs/json_schema.md` – detailed schema reference with guide citations.
- `_FmtXML_*` and `Case*_Def.xml` – reference XML fragments bundled with DualSPHysics.
- `XML_GUIDE_v5.4.pdf` – primary specification for the XML format.

Happy case building!
