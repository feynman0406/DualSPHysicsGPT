# Plan to ensure auto-generated XML passes GenCase

Goal
- Produce JSON-to-XML outputs that comply with the DualSPHysics XML schema and run through GenCase without errors.
- Adjust the LLM prompt and, if needed, harden the generator to tolerate common agent mistakes.

Summary diagnosis (why current output may fail GenCase)
- Missing constantsdef block: The current JSON used top-level "constantsdef" key; the generator expects "constants", so the generated XML lacks <constantsdef> entirely.
- Wrong tag for runlist: Generated <GeometryForNormals type="runlist"/> instead of <runlist name="GeometryForNormals"/>.
- Attribute naming mismatches:
  - setdrawmode should use attribute mode="full" (official) but we generated value="full".
  - setshapemode is typically text content (e.g., <setshapemode>actual | bound</setshapemode>) not an attribute.
- Normals structure: Official XML nests normals under <normals><norgeometry>…</norgeometry></normals>; simplified flat attributes may not be accepted by GenCase.
- Minor command shape mismatches: Official XML often prefers child elements (e.g., <boxfill>left</boxfill>) versus attributes (boxfill="left"). Some attribute names are strict.

Action plan
1) Lock a strict JSON “contract” for the agent to follow
   - Top-level keys:
     - constants (not constantsdef)
     - mkconfig
     - geometry
       - definition: dp, pointmin, pointmax (vectors)
       - commands:
         - lists: array of { name, items[] } where each item is a command object
         - mainlist: array of command objects
     - casedef_extra: array of generic nodes (for normals use official structure)
     - execution.parameters: key/value map where:
       - Simple numeric/string params become <parameter key="K" value="V"/>
       - Vector-like values become <parameter key="PeriodicDomain" x=".." y=".." z=".."/>
   - Command object schema:
     - Always include type (e.g., "setmkfluid", "drawbox", "fillbox", "runlist", "shapeout", "setdrawmode", "setshapemode", "layers", "resetdraw")
     - For commands with official attribute names, use those names explicitly:
       - setdrawmode: { "type": "setdrawmode", "mode": "full" }
       - setshapemode: { "type": "setshapemode", "text": "actual | bound" }  // text content preferred
       - runlist: { "type": "runlist", "name": "GeometryForNormals" }         // this should render <runlist …/>
       - layers: { "type": "layers", "vdp": "0,1,2" }
       - shapeout: { "type": "shapeout", "file": "hdp" }
       - setactive: { "type": "setactive", "drawpoints": 0, "drawshapes": 1 }
       - setmkbound / setmkfluid: { "type": "setmkbound", "mk": 10 }
     - Boxes and fills prefer child structure, not attributes:
       - drawbox example:
         {
           "type": "drawbox",
           "children": [
             { "tag": "boxfill", "text": "left" },
             { "tag": "point", "vector": { "x": -0.5, "y": -1.0, "z": 0.0 } },
             { "tag": "size",  "vector": { "x": 0.5,  "y": 2.0,  "z": 3.0 } }
           ]
         }
       - fillbox example (include point/size; modefill optional):
         {
           "type": "fillbox",
           "children": [
             { "tag": "modefill", "text": "void" },
             { "tag": "point", "vector": { "x": 0.01, "y": -0.1, "z": 0.01 } },
             { "tag": "size",  "vector": { "x": 0.98, "y": 0.2,  "z": 1.98 } }
           ]
         }
   - Normals (official structure):
     - In casedef_extra, produce:
       {
         "tag": "normals",
         "children": [
           {
             "tag": "norgeometry",
             "children": [
               { "tag": "geometryfile", "attributes": { "file": "[CaseName]_hdp_Actual.vtk" } },
               { "tag": "distanceh", "attributes": { "v": 2.0 } }
             ]
           }
         ]
       }

2) Provide a hardened prompt template for the web-based agent (copy/paste)
Use the following as the system or top-of-chat instruction:

-----
You must output a single JSON object that will be transformed into DualSPHysics XML via a deterministic generator. Follow this contract strictly:

- No comments; valid JSON only.
- Top-level keys must be exactly: constants, mkconfig, geometry, casedef_extra, execution.
- constants: key/value map. Vectors use { "x": .., "y": .., "z": .. }. Example:
  "constants": {
    "gravity": { "x": 0, "y": 0, "z": -9.81 },
    "rhop0": 1000,
    "gamma": 7,
    "speedsystem": 1,
    "coefsound": 10,
    "hdp": 2,
    "cflnumber": 0.2
  }
- mkconfig: include "boundcount" and "fluidcount" (integers).
- geometry:
  - definition: must include "dp", "pointmin", "pointmax" vectors.
  - commands:
    - lists: array of { "name": string, "items": [command, ...] }.
      Each list item is a command object (see Commands below).
    - mainlist: array of command objects executed in order (see Commands below).
- casedef_extra: array of nodes. For normals, use official nested structure:
  {
    "tag": "normals",
    "children": [
      {
        "tag": "norgeometry",
        "children": [
          { "tag": "geometryfile", "attributes": { "file": "[CaseName]_hdp_Actual.vtk" } },
          { "tag": "distanceh", "attributes": { "v": 2.0 } }
        ]
      }
    ]
  }
- execution.parameters: map of parameters. Scalars become <parameter key="K" value="V"/>; vectors become <parameter key="K" x="..." y="..." z="..."/>.

Commands (use these exact patterns):
- { "type": "setactive", "drawpoints": 0|1, "drawshapes": 0|1 }
- { "type": "setshapemode", "text": "actual | bound" }      // prefer text content
- { "type": "setdrawmode", "mode": "full" }                 // use "mode", not "value"
- { "type": "setmkbound", "mk": N }
- { "type": "setmkfluid", "mk": N }
- { "type": "shapeout", "file": "hdp" }
- { "type": "layers", "vdp": "0,1,2" }                      // comma-separated
- { "type": "resetdraw" }
- Run an existing list: { "type": "runlist", "name": "ListName" } // becomes <runlist name="ListName"/>
- drawbox with children:
  { "type": "drawbox", "children": [
      { "tag": "boxfill", "text": "all|left|right|bottom|..." },
      { "tag": "point", "vector": { "x": ..., "y": ..., "z": ... } },
      { "tag": "size",  "vector": { "x": ..., "y": ..., "z": ... } },
      // optional: { "tag": "layers", "vdp": "0,1,2" }
  ]}
- fillbox with children:
  { "type": "fillbox", "children": [
      { "tag": "modefill", "text": "void|..." },
      { "tag": "point", "vector": { "x": ..., "y": ..., "z": ... } },
      { "tag": "size",  "vector": { "x": ..., "y": ..., "z": ... } }
  ]}

Validation preflight (the JSON you output must satisfy all):
- No "constantsdef" key; must be "constants".
- geometry.definition includes "dp", "pointmin", "pointmax".
- commands.lists[].items is an array of command objects, not a string.
- mainlist is an array of command objects; to run a list, use { "type": "runlist", "name": "..." }.
- For setdrawmode, use "mode", not "value".
- For setshapemode, use "text".
- Normals use the official nested structure shown above.
- No comments or trailing commas. All numbers are numbers, not strings.
-----

3) Patch the generator for robustness (optional but recommended)
- Accept "constantsdef" as an alias for "constants":
  - On load, if config.get("constants") is missing and config.get("constantsdef") is present, set config["constants"] = config.pop("constantsdef").
- Fix runlist tag emission in mainlist:
  - In _build_geometry_commands, instead of building mainlist via build_generic_node, build an explicit mainlist node and append self._build_command(child_spec) for each entry to ensure <runlist name="..."/> is produced (not <GeometryForNormals type="runlist"/>).
- Attribute fallbacks:
  - setdrawmode: accept both { mode: "full" } and { value: "full" } but emit mode when present.
  - setshapemode: accept { text: "..." } or { value: "..." }, prefer text content output.
- Normals shape:
  - If a simplified normals node with { distanceh, geometryfile } is provided, normalize it to the official <normals><norgeometry>…</norgeometry></normals> structure internally.

4) Sanity-check delta against official case
Compare against AutoXml_script/CaseSloshingHR_Def.xml and other official cases to ensure:
- All required sections appear in this order: constantsdef, mkconfig, geometry (definition + commands), [normals/motion/… as needed].
- For commands, attribute names conform to official (e.g., setdrawmode@mode).

5) Verification steps
- Unit tests:
  - Add tests to assert runlist serialization and constants aliasing.
  - Roundtrip tests for list/items and mainlist commands.
- Local validation:
  - Generate XML from a sample JSON built from the contract.
  - If GenCase binary is available, run: GenCase <xml> <out> (or your project’s runner) and confirm no schema/parse errors.
- Regression:
  - Ensure older configs in AutoXml_script/config_library still pass.

Reference example JSON (conforming)
{
  "constants": {
    "gravity": { "x": 0, "y": 0, "z": -9.81 },
    "rhop0": 1000,
    "gamma": 7,
    "speedsystem": 1,
    "coefsound": 10,
    "hdp": 2,
    "cflnumber": 0.2
  },
  "mkconfig": { "boundcount": 240, "fluidcount": 10 },
  "geometry": {
    "definition": {
      "dp": 0.01,
      "pointmin": { "x": -3.0, "y": 0.0, "z": -3.0 },
      "pointmax": { "x": 7.0, "y": 0.0, "z": 5.0 }
    },
    "commands": {
      "lists": [
        {
          "name": "GeometryForNormals",
          "items": [
            { "type": "setactive", "drawpoints": 0, "drawshapes": 1 },
            { "type": "setshapemode", "text": "actual | bound" },
            { "type": "setmkbound", "mk": 0 },
            {
              "type": "drawbox",
              "children": [
                { "tag": "boxfill", "text": "all" },
                { "tag": "point", "vector": { "x": -0.5, "y": -1.0, "z": 0.0 } },
                { "tag": "size",  "vector": { "x":  0.5, "y":  2.0, "z": 3.0 } }
              ]
            },
            { "type": "shapeout", "file": "hdp" },
            { "type": "resetdraw" }
          ]
        }
      ],
      "mainlist": [
        { "type": "runlist", "name": "GeometryForNormals" },
        { "type": "setdrawmode", "mode": "full" },
        { "type": "setmkfluid", "mk": 0 },
        {
          "type": "fillbox",
          "children": [
            { "tag": "modefill", "text": "void" },
            { "tag": "point", "vector": { "x": 0.01, "y": -0.1, "z": 0.01 } },
            { "tag": "size",  "vector": { "x": 0.98, "y":  0.2, "z": 1.98 } }
          ]
        },
        { "type": "setmkbound", "mk": 10 },
        { "type": "setshapemode", "text": "bound" },
        { "type": "layers", "vdp": "0,1,2" },
        {
          "type": "drawbox",
          "children": [
            { "tag": "boxfill", "text": "bottom" },
            { "tag": "point", "vector": { "x": -0.5, "y": -1.0, "z": -1.0 } },
            { "tag": "size",  "vector": { "x":  5.0, "y":  2.0, "z":  1.0 } }
          ]
        }
      ]
    }
  },
  "casedef_extra": [
    {
      "tag": "normals",
      "children": [
        {
          "tag": "norgeometry",
          "children": [
            { "tag": "geometryfile", "attributes": { "file": "[CaseName]_hdp_Actual.vtk" } },
            { "tag": "distanceh", "attributes": { "v": 2.0 } }
          ]
        }
      ]
    }
  ],
  "execution": {
    "parameters": {
      "TimeMax": 3.0,
      "SaveInterval": 0.01,
      "Boundary": 2,
      "Kernel": 2,
      "StepAlgorithm": 2,
      "Visco": 0.01,
      "ViscoTreatment": 1,
      "SlipMode": 1,
      "PeriodicDomain": { "x": 0, "y": 0, "z": 0 }
    }
  }
}

Status Update (Sept 2025)
- JSON Mode added with OpenAI Structured Outputs (Responses API) using a strict schema at docs/auto_xml_jsonschema.json (Strictness S1; constants=require-full).
- chains/generator.py switches to JSON-only prompting when GENERATOR_JSON_MODE=1 and uses prompts/auto_xml_contract.md.
- llm/client.py passes response_format.type=json_schema so the model must return schema-valid JSON.
- chains/json_normalizer.py accepts geometry.commands.lists[].items (alias for legacy commands) and normalizes to items.
- prompts/auto_xml_contract.md clarified setshapemode example (no “actual | bound” ambiguity).
- AutoXml_script/generate_xml.py now always attempts geometry.definition fallback when dp + domain.min/max are on the geometry object.
- Test suite: 44 passed, 2 warnings.

Next steps
- Optional: extend the JSON Schema to cover more command types (drawcylinder, fillmesh, etc.) or relax constants “require-full” if desired.
- Optional: add dedicated unit tests for schema strictness/error messaging and JSON-mode retries.
- Documentation: see docs/json_mode_usage.md for activation and end-to-end behavior.
