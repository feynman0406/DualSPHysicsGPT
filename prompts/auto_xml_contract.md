System prompt: Produce JSON that our generator converts into valid DualSPHysics XML which compiles with GenCase

Output format requirements
- Return exactly one JSON object. No comments. No trailing commas.
- Top-level keys must include: constants, mkconfig, geometry, execution. Use optional sections like floatings, initials, motion, and casedef_extra only when you have data to populate them, and mirror every emitted section in casedef_children using {"type": "section", "key": "<section>"}.
- When external dependencies exist, populate `files` with repo-relative paths and concise purposes so downstream manifests can copy assets.
- All numbers should be numbers (not strings). Vectors use objects with x,y,z.

Schema contract
1) constants
   - A map of constant names to values.
   - Scalars become <name value="..."/>.
   - Vectors become <name x="..." y="..." z="..."/>.
   Example:
   "constants": {
     "gravity": { "x": 0, "y": 0, "z": -9.81 },
     "rhop0": 1000,
     "gamma": 7,
     "speedsystem": 1,
     "coefsound": 10,
     "hdp": 2,
     "cflnumber": 0.2
   }

2) mkconfig
   - Keys: "boundcount" (int), "fluidcount" (int).
   Example: "mkconfig": { "boundcount": 240, "fluidcount": 10 }

3) geometry
   - definition: must include
     - "dp": number
     - "pointmin": { "x": ..., "y": ..., "z": ... }
     - "pointmax": { "x": ..., "y": ..., "z": ... }
   - commands:
     - lists: array of list objects
       - { "name": "ListName", "items": [command, ...] }
     - mainlist: array of command objects executed in order.
   Command objects must follow these patterns exactly:
   - Run an existing list:
     { "type": "runlist", "name": "ListName" }  // becomes <runlist name="ListName"/>
   - Activate point/shape drawing:
     { "type": "setactive", "drawpoints": 0|1, "drawshapes": 0|1 }
   - Set shape mode (text content preferred):
     { "type": "setshapemode", "text": "actual | bound" }
   - Set draw mode:
     { "type": "setdrawmode", "mode": "full" }  // use "mode", not "value"
   - Marker selection:
     { "type": "setmkfluid", "mk": N }, { "type": "setmkbound", "mk": N }
   - Layers:
     { "type": "layers", "vdp": "0,1,2" }  // comma-separated string
   - Export shape:
     { "type": "shapeout", "file": "hdp" }
   - Reset draw:
     { "type": "resetdraw" }
   - drawbox with children (prefer child nodes over attributes):
     {
       "type": "drawbox",
       "children": [
         { "tag": "boxfill", "text": "all|left|right|bottom|..." },
         { "tag": "point", "vector": { "x": ..., "y": ..., "z": ... } },
         { "tag": "size",  "vector": { "x": ..., "y": ..., "z": ... } }
       ]
     }
   - fillbox with children:
     {
       "type": "fillbox",
       "children": [
         { "tag": "modefill", "text": "void|..." },
         { "tag": "point", "vector": { "x": ..., "y": ..., "z": ... } },
         { "tag": "size",  "vector": { "x": ..., "y": ..., "z": ... } }
       ]
     }

3b) files array
   - Document every external dependency that must accompany the case (uploaded STLs, normals archives, motion scripts, etc.).
   - Use repo-relative paths in each entry, for example { "path": "logs/mvp/uploads/<run_id>/paddle.stl", "purpose": "external_geometry" }.
   - Keep `purpose` short but descriptive so Stage 3 can build manifests automatically.

4) floatings
   - Optional list of floating-body definitions emitted under <casedef><floatings>.
   - Each entry must set "type": "floating" and can include inline attributes (e.g., mkbound) or nested children for mass/inertia nodes.
   - Never embed Chrono/`bodyfloating` nodes here; omit Chrono couplings entirely.
   Example:
   "floatings": [
     {
       "type": "floating",
       "attributes": {"mkbound": 1},
       "children": [
         {"type": "massbody", "attributes": {"value": 1.3}}
       ]
     }
   ]

5) casedef_children
   - Ordered list describing <casedef> sections and inline comments.
   - Provide a {"type": "section", "key": "<section>"} entry for every top-level section you emit.
   - Typical order: constants, mkconfig, geometry, normals (when present), initials, floatings, motion, casedef_extra, execution.
   - When you emit floatings, ensure {"type": "section", "key": "floatings"} appears in the list. The normalizer will position it after initials or geometry as needed.
   - Use {"type": "generic", "spec": <node>} entries for inline comments or bespoke content.
   Example:
   "casedef_children": [
     {"type": "section", "key": "constants"},
     {"type": "section", "key": "mkconfig"},
     {"type": "section", "key": "geometry"},
     {"type": "section", "key": "normals"},
     {"type": "section", "key": "initials"},
     {"type": "section", "key": "floatings"},
     {"type": "section", "key": "motion"},
     {"type": "section", "key": "casedef_extra"},
     {"type": "section", "key": "execution"}
   ]

6) casedef_extra
   - Array of generic nodes appended inside <casedef>.
   - For normals, use official nested structure:
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
7) execution
   - parameters: an object map.
     - Scalar becomes <parameter key="K" value="V"/>.
     - Vector becomes <parameter key="K" x="..." y="..." z="..."/>.
   Example:
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

Validation checklist (must all be satisfied before returning JSON)
- [ ] Top-level keys include constants, mkconfig, geometry, execution, and only add optional sections like floatings, initials, motion, or casedef_extra when requested.
- [ ] casedef_children lists every emitted section in order; whenever a floatings block exists, ensure {"type": "section", "key": "floatings"} is included.
- [ ] Floatings entries omit Chrono-specific children such as `bodyfloating`, `schemescale`, or `chrono`.
- [ ] No comments; valid JSON only.
- [ ] geometry.definition has dp, pointmin (x,y,z), pointmax (x,y,z).
- [ ] commands.lists is an array of { name, items[] } and items[] are command objects (not strings).
- [ ] commands.mainlist is an array of command objects.
- [ ] To run a list in mainlist use { "type": "runlist", "name": "..." }.
- [ ] setdrawmode uses "mode": "full" (not "value").
- [ ] setshapemode uses "text": "...".
- [ ] drawbox/fillbox use children nodes for boxfill/modefill/point/size.
- [ ] normals use the nested norgeometry structure under casedef_extra.
- [ ] Numbers are numbers; vectors are objects with x,y,z.
- [ ] `files` lists every external dependency with repo-relative `path` and human-readable `purpose` when assets exist.

Reference example JSON
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




