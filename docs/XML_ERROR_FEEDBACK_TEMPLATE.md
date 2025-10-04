# XML Validation Error Feedback Template

Use this template when you encounter errors in the generated XML file and need to request corrections from the agent.

## Template

```
The generated XML at `logs/mvp/generated_case.xml` has validation errors that need to be fixed:

## Error Description:
[Describe what's wrong - e.g., "Missing required element", "Invalid attribute value", etc.]

## Specific Error Message:
```
[Paste the exact error message from DualSPHysics/GenCase here]
```

## Expected Behavior:
[Describe what the XML should contain or how it should be structured]

## Reference Example:
[If applicable, point to a working example file, e.g., "See AutoXml_script/config_library/CaseDambreak_Def.json for correct structure"]

## Action Needed:
[ ] Update the schema to enforce correct structure
[ ] Fix the generated JSON config
[ ] Modify the XML generation logic
[ ] Other: [specify]

## Additional Context:
[Any other relevant information about the simulation requirements, parameters, etc.]
```

---

## Example Usage

```
The generated XML at `logs/mvp/generated_case.xml` has validation errors that need to be fixed:

## Error Description:
The drawbox command is missing the required 'boxfill' child element that specifies which faces to draw.

## Specific Error Message:
```
Error in geometry.commands.mainlist: drawbox requires child element <boxfill>
Expected: <boxfill>solid</boxfill> or <boxfill>bottom | left | right</boxfill>
```

## Expected Behavior:
Each drawbox command should have a boxfill child element that specifies how to fill the box. For example:
```xml
<drawbox>
  <boxfill>solid</boxfill>
  <point x="0" y="0" z="0"/>
  <size x="1" y="1" z="1"/>
</drawbox>
```

## Reference Example:
See AutoXml_script/config_library/CaseDambreak_Def.json - the geometry.commands.mainlist[5] shows proper drawbox structure with boxfill child.

## Action Needed:
[x] Update the schema to enforce boxfill as a required child in drawbox commands
[ ] Fix the generated JSON config
[ ] Modify the XML generation logic

## Additional Context:
This is for a 2D dambreak simulation. The boundaries need solid box fills while fluid regions need selective face fills.
```

---

## Quick Feedback Format

For simple issues, you can use this shorter format:

```
Fix needed in logs/mvp/generated_case.xml:

ERROR: [error message]
LOCATION: [which section/element]
FIX: [what needs to change]
REFERENCE: [optional - point to working example]
```

Example:
```
Fix needed in logs/mvp/generated_case.xml:

ERROR: geometry.commands.mainlist is empty
LOCATION: geometry.commands section
FIX: Add drawing commands (setmkbound, setmkfluid, drawbox, fillbox, etc.)
REFERENCE: See AutoXml_script/config_library/CaseDambreak_Def.json geometry.commands.mainlist
