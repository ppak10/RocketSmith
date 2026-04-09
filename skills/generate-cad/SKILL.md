---
name: generate-cad
description: Use when turning a parts manifest into STEP files via build123d. Covers folder structure, script generation, the build123d_script execution workflow, common build123d API patterns, and verification. Rocketry-agnostic — knows about parts and assemblies, not about nose cones and fins.
---

# Generate CAD

## Overview

`generate-cad` is the **build123d execution skill**. It takes a parts manifest produced by a design-for-X skill (today: `design-for-additive-manufacturing`) and turns it into STEP files by writing parametric build123d Python scripts, executing them in an isolated environment, and verifying each output.

This skill is deliberately **rocketry-agnostic**. It does not know what a nose cone is, what a coupler is, or what an ogive is. Those are the DFx skill's concern. `generate-cad` knows:

- How to lay out a project directory so scripts, STEP files, and gcode each have a clean home
- How to write a build123d script that's self-contained and idempotent
- How to invoke `build123d_script` correctly and recover from failures
- Common build123d API patterns (revolve, extrude, boolean, polar array, assembly)
- How to verify a generated STEP file visually and dimensionally before moving on
- When to reach for the `cad_examples` reference collection for tricky API questions

**Core principle:** Read the manifest, trust the manifest. Every geometric decision — which parts exist, what features they have, which components they're derived from — was made by the DFx skill. `generate-cad`'s job is faithful execution, not design judgement.

## When to Use

- A `parts_manifest.json` exists at `<project_dir>/parts_manifest.json` and needs to become STEP files
- The user asks to generate CAD, generate STEP files, or produce build123d output
- A manifest was updated and some parts need to be regenerated
- A single part needs to be regenerated from an existing manifest (e.g. after a geometry tweak)

## Inputs

1. `<project_dir>/parts_manifest.json` — the authoritative parts list, produced by a DFx skill (see `design-for-additive-manufacturing`)
2. Optionally: the raw `openrocket_cad_handoff` output, if a feature block needs a lookup not captured in the manifest (rare)

Never infer parts or features from the source `.ork` file directly. The manifest is the contract; if it's wrong, fix the manifest and regenerate, don't work around it in the build123d scripts.

## Output

- `<project_dir>/build123d/<name>.py` — one parametric build123d script per part
- `<project_dir>/CAD/<name>.step` — the STEP file produced by each script
- Optionally, `<project_dir>/CAD/<assembly>.step` — multi-part assembly STEP for visual verification

## Project Layout

```
<project_dir>/
├── <rocket_name>.ork          (OpenRocket design, owned by openrocket subagent)
├── parts_manifest.json        (DFx output, the input to this skill)
├── build123d/                 (scripts owned by this skill)
│   ├── nose_cone.py
│   ├── upper_airframe.py
│   └── lower_airframe.py
├── CAD/                       (STEP outputs produced by this skill)
│   ├── nose_cone.step
│   ├── upper_airframe.step
│   └── lower_airframe.step
└── gcode/                     (gcode outputs produced later by prusaslicer)
    └── ...
```

`generate-cad` writes to `build123d/` and `CAD/`. It does not touch the other directories. The `directories` block in the manifest documents these paths; treat them as fixed.

**Create the directories** before the first script runs:

```
Bash("mkdir -p <project_dir>/build123d <project_dir>/CAD")
```

## Steps

### 1. Load the Manifest

```
manifest = read_json("<project_dir>/parts_manifest.json")
```

Verify the manifest is well-formed: it has `schema_version`, `parts`, `directories`, and `component_to_part_map`. If any are missing, stop and report — do not guess. Ask the DFx skill to regenerate the manifest.

### 2. Create Directories

```
Bash("mkdir -p <project_dir>/build123d <project_dir>/CAD")
```

### 3. Generate Each Part

For each entry in `manifest["parts"]`:

1. **Write the script** using the `Write` tool. The script writes its STEP file to the `step_path` from the manifest (resolved to absolute against `project_root`).
2. **Execute** via the `build123d_script` MCP tool:
   ```
   build123d_script(
       script_path="<project_dir>/build123d/<name>.py",
       out_dir="<project_dir>/CAD",
   )
   ```
   The tool runs the script with `uv run --isolated --with build123d`. No host Python or virtualenv required.
3. **Render** via `build123d_render(step_file_path="<project_dir>/CAD/<name>.step")` to get a 3-panel PNG.
4. **Read** the PNG with the `Read` tool to visually inspect the geometry.
5. **Extract** via `build123d_extract` to verify bounding box and volume match what the features block specifies.

Do not proceed to the next part if the current one fails any check. Fix the script and re-run before moving on.

### 4. (Optional) Generate Assemblies

If `manifest["assemblies"]` is non-empty, write one additional script per assembly that imports all its parts and composes them fore-to-aft into a single build123d `Compound`. Export as a combined STEP file to the assembly's `step_path`. Verify with `build123d_render` as with individual parts.

Assembly generation is optional for this release — skip if the manifest's `assemblies` block is empty.

## Script Structure

Every generated build123d script should follow the same shape so they're debuggable and idempotent:

```python
"""
<Part name> — derived from: <OR components>
Manifest entry: parts[<index>]
"""
from build123d import *
from pathlib import Path

# --- Parameters (from manifest features block) ---
# These come straight from the DFx manifest; do not hardcode.
LENGTH_MM = 400.0
OUTER_D_MM = 64.0
INNER_D_MM = 58.0
# ... other parameters derived from manifest ...

OUTPUT = Path("<absolute path to CAD/<name>.step>")

# --- Build ---
with BuildPart() as part:
    # ... geometry ...
    pass

# --- Export ---
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
export_step(part.part, str(OUTPUT))
```

Key rules:

- **OUTPUT is an absolute path** resolved from `project_root` + the manifest's `step_path`. Do not use relative paths.
- **Parameters are named constants at the top.** The reader should be able to scan the parameter block, confirm it matches the manifest, and not have to read the geometry code.
- **No imports beyond `build123d`, `pathlib`, `math`, `typing`.** `build123d_script` runs in isolated mode with no host environment — importing `numpy`, `os.system`, or anything outside the allowlist will fail.
- **`OUTPUT.parent.mkdir(parents=True, exist_ok=True)`** makes the script idempotent against a missing `CAD/` directory.
- **Every script exports exactly one STEP file** unless it's an assembly script. Don't export multiple parts from one script.

## Coordinate Convention

All parts are built with **Z as the primary build axis**. The manifest's feature blocks express positions in Z; translate them directly to build123d Z coordinates.

Convention:
- Z = 0 at the fore (forward) end of the part
- Positive Z extends aft
- Same axis orientation as the source `.ork` file

## Common build123d API Patterns

The DFx manifest's feature blocks reference these patterns by intent (`local_wall_thickening`, `integrated_fins`, `polar_array_holes`, etc.). Below are the generic build123d implementations.

### Hollow cylinder (tube)

```python
with BuildPart() as tube:
    with BuildSketch(Plane.XY):
        Circle(OUTER_D_MM / 2)
        Circle(INNER_D_MM / 2, mode=Mode.SUBTRACT)
    extrude(amount=LENGTH_MM)
```

### Revolve around an axis

For any profile that has rotational symmetry (nose cones, boattails, transitions, fairings):

```python
with BuildPart() as revolved:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            # Profile: a closed polyline or spline in the XZ plane,
            # with Z as the axis of revolution and X as radius.
            Spline(*profile_points)
            Line(profile_points[-1], (0, PART_LENGTH))
            Line((0, PART_LENGTH), (0, 0))
        make_face()
    revolve(axis=Axis.Z)
```

### Polar array (rotate a feature around the Z axis)

For any N-fold symmetric feature (fins, vent holes, heat-set bosses):

```python
# Build one instance of the feature at angle 0
with BuildPart() as feature:
    # ... build geometry for a single instance ...
    pass

# Rotate copies around Z
feature_shape = feature.part
with BuildPart() as array:
    for i in range(COUNT):
        add(feature_shape.rotate(Axis.Z, i * (360 / COUNT)))
```

### Fused extrusion (one feature merged into a parent)

For features like fins fused into a body tube, or wall thickening regions:

```python
with BuildPart() as airframe:
    # Parent geometry (e.g. the hollow tube)
    with BuildSketch(Plane.XY):
        Circle(OUTER_D_MM / 2)
        Circle(INNER_D_MM / 2, mode=Mode.SUBTRACT)
    extrude(amount=LENGTH_MM)

    # Fused feature (add mode, same BuildPart context)
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline(*feature_points, close=True)
        make_face()
    extrude(amount=FEATURE_THICK / 2, both=True, mode=Mode.ADD)
```

### Radial hole on an arbitrary plane

For holes that go radially through a cylindrical wall (heat-set inserts, shear pins, vent holes through a tube wall):

```python
from math import cos, sin, radians

for i in range(COUNT):
    angle_rad = radians(START_ANGLE_DEG + i * (360 / COUNT))
    cx = RADIUS * cos(angle_rad)
    cy = RADIUS * sin(angle_rad)
    hole_plane = Plane(
        origin=(cx, cy, Z_POSITION),
        x_dir=(-sin(angle_rad), cos(angle_rad), 0),
        z_dir=(-cos(angle_rad), -sin(angle_rad), 0),
    )
    with BuildSketch(hole_plane):
        Circle(HOLE_DIAMETER_MM / 2)
    extrude(amount=HOLE_DEPTH_MM, mode=Mode.SUBTRACT)
```

### Assembly composition

For multi-part STEP exports (when `manifest["assemblies"]` is non-empty):

```python
from build123d import *
from pathlib import Path

parts = [
    import_step("CAD/nose_cone.step"),
    import_step("CAD/upper_airframe.step"),
    import_step("CAD/lower_airframe.step"),
]

# Optionally position each part along Z so the assembly is physically arranged
# fore-to-aft. Positions come from the manifest's feature Z values.
positioned = []
cursor_z = 0
for p in parts:
    positioned.append(p.translate((0, 0, cursor_z)))
    cursor_z += p.bounding_box().size.Z

assembly = Compound(label="full_rocket", children=positioned)
export_step(assembly, "<absolute path to CAD/full_rocket.step>")
```

## Feature Recipe Reference

The DFAM manifest uses named feature types (`local_wall_thickening`, `integrated_fins`, `integral_aft_shoulder`, `forward_stop_lip`, `heat_set_bosses`). The implementations below are starting points. **These recipes may migrate to the `cad_examples` reference collection over time so they can be curated and versioned independently.**

For a definition of each feature's `features` block fields, see the DFAM skill. `generate-cad` composes the patterns above to implement each:

| Feature type | Composition |
|---|---|
| `local_wall_thickening` | Hollow cylinder with a secondary inner `Circle` at a smaller radius subtracted only within `[region_start_mm, region_end_mm]` along Z. Build the outer shell first, then subtract an inner cylinder that changes radius along Z. |
| `integrated_fins` | Build the parent tube first. Build a single fin as a polyline-extrude sketch (root_chord, tip_chord, span, sweep) in the XZ plane, extruded ±thickness/2 in Y. Fuse with the tube. Use the polar-array pattern to rotate `count` copies around Z. Apply a root fillet of `fillet_mm`. |
| `integral_aft_shoulder` | At the aft Z position of the parent tube, extrude a second hollow cylinder (OD = shoulder OD, ID = parent ID) downward by `length_mm`. Fuse with parent. If `retention` is `m4_heat_set`, add radial holes via the radial-hole pattern at the shoulder mid-length. |
| `forward_stop_lip` | At the fore end of the motor bore, extrude a small annulus inward (OD = bore radius, ID = stop ID) by `thickness_mm` in the negative Z direction. Fuse with parent. |
| `heat_set_bosses` | For each angular position, add a small boss (cylinder) protruding outward from the tube wall at the specified Z position, then subtract the hole using the radial-hole pattern. |

If a feature type in the manifest isn't in this table, query the `cad_examples` reference collection (see below) before improvising.

## Check the Reference Collection

For feature types or build123d API patterns not covered above, query the reference collection:

```
rag_reference(
    action="search",
    collection="cad_examples",
    query=f"build123d {feature_type_or_api_question}",
    n_results=3,
)
```

Example queries: `"build123d loft between circles"`, `"build123d fillet edge selection"`, `"build123d sweep along path"`, `"build123d thicken surface"`. The collection captures API nuances that aren't in the recipe table above.

**If the search returns no results**, fall back to the build123d documentation or ask the user. **If the search errors**, proceed using the best interpretation of the feature and flag it in the verification step.

## Verification Workflow

After each successful `build123d_script` call:

1. **`build123d_render(step_file_path=<path>)`** — produces a 3-panel PNG (side, end-on, isometric)
2. **`Read(file_path=<png_path>)`** — visually inspect:
   - Does the overall shape match the feature block's intent?
   - Are any expected geometric features visible and correctly placed?
   - Is the part inside-out (walls appearing solid where there should be a bore)?
   - Is any dimension obviously wrong (a part that should be ~400 mm long appearing ~40 mm)?
3. **`build123d_extract(step_file_path=<path>)`** — returns volume, bounding box, centre of mass. Compare the bounding box dimensions to the manifest's feature block. If the Z extent doesn't match `length_mm`, something is wrong with the script.
4. If any check fails, **fix the script and re-run**. Do not accept broken geometry. Do not defer verification to "I'll check all of them at the end" — verify one, then move on.

## Red Flags — Stop and Fix

- A script imports anything outside `build123d`, `pathlib`, `math`, `typing` — `build123d_script` will fail in isolated mode
- A script uses relative paths for the STEP output — will save to a confusing location
- A script produces a STEP file whose bounding box doesn't match the manifest feature block
- A script produces a render that visually doesn't match the manifest's `derived_from` list (e.g. three fused components expected, render shows one)
- `build123d_extract` volume is zero or NaN — the part is degenerate, script has a topology bug
- A part is generated that isn't in the manifest — the script is doing design work it shouldn't
- A part in the manifest is skipped without a reported failure — verify the iteration isn't dropping entries

## Quick Reference

```
# the handoff
parts_manifest.json  →  this skill  →  <project_dir>/CAD/*.step
                                       <project_dir>/build123d/*.py

# the execution loop
for part in manifest["parts"]:
    write_script(part)                     # Write tool
    build123d_script(script_path, out_dir) # MCP tool
    build123d_render(step_file_path)       # MCP tool
    Read(png_path)                         # visual check
    build123d_extract(step_file_path)      # dimensional check
    if any_check_failed: fix_and_retry()

# the layout
<project_dir>/
├── parts_manifest.json
├── build123d/   ← .py scripts
├── CAD/         ← .step outputs
└── gcode/       ← .gcode (later, by prusaslicer)
```
