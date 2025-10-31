# UI MVP XML Common Mistakes

This living note tracks high-severity mistakes observed when the UI MVP pipeline generates DualSPHysics XML. Add new patterns as they surface so future agents can apply the same guardrails.

## Fluid Fillbox Must Stay Void

- Mistake: generating `<modefill>` values such as `solid` inside a fluid injection `<fillbox>`.
- Why it matters: non-void fillboxes suppress inflow particles, breaking scenarios that rely on continuous fluid generation.
- Detection guardrail: for every `<fillbox>` inside a `<setmkfluid>` block, assert `<modefill>void</modefill>` before emitting the XML.
- Fix guidance: overwrite incoming `modefill` requests to `void` for fluid fillboxes and document the override in logs if the UI supplied something else.
- Prompt reminder:

```text
When emitting <fillbox> inside a <setmkfluid> block, hardcode <modefill>void</modefill>. Never emit solid/any other value or leave it blank.
```

## Fillbox Coordinates Must Live Inside the Fluid Volume

- Mistake: placing the `<fillbox>` origin outside the fluid definition cuboid described by `<point>` (origin) and `<size>` (extent).
- Why it matters: an out-of-bounds fillbox spawns particles in invalid locations or outside the computational domain, leading to empty inflows.
- Detection guardrail: when a `<fillbox>` belongs to a `<setmkfluid>` block, check each axis before writing the XML: `point.axis <= fillbox.axis <= point.axis + size.axis` for axis in {x, y, z}. Reject or correct values that fall outside this range, but skip this bound check for non-fluid fillboxes.
- Fix guidance: clamp the fillbox coordinates or raise a validation error so the UI can request a new location within bounds.
- Prompt reminder:

```text
Before writing any fluid <fillbox>, ensure its x/y/z lie within [point.axis, point.axis + size.axis]. Skip the check for boundary or void-only fillboxes outside fluid sections. If a fluid fillbox fails, stop and fix the inputs.
```

## 2D Geometry Y Alignment

- Mistake: in 2D scenarios (where `geometry.definition.pointmin.y == pointmax.y`), the `<fillbox>` y coordinate does not match the geometry plane.
- Why it matters: the 2D solver expects all fluid sources to sit on the single geometry plane; any offset puts the source outside the simulated slice.
- Detection guardrail: detect 2D mode (`pointmin.y == pointmax.y`) and enforce `fillbox.y == pointmin.y`. In 3D, continue to validate `pointmin.y <= fillbox.y <= pointmax.y`.
- Fix guidance: overwrite the fillbox y coordinate with the geometry plane value (or flag a validation error) whenever a mismatch is found.
- Prompt reminder:

```text
If geometry.definition is 2D (pointmin.y == pointmax.y), lock fillbox.y to that shared value. In 3D, require fillbox.y to stay within [pointmin.y, pointmax.y].
```

## Combined Prompt Snippet

Copy this block into prompts or checklists when handing work to another agent:

```text
Critical XML rules for UI MVP work:
- For every <setmkfluid>/<fillbox>, force <modefill>void</modefill>.
- For fluid <fillbox> commands, enforce point.axis <= fillbox.axis <= point.axis + size.axis for axis x/y/z before emitting XML (skip non-fluid fillboxes).
- When geometry.definition.pointmin.y == pointmax.y (2D), set fillbox.y to that plane; otherwise keep fillbox.y within the geometry bounds.
```

