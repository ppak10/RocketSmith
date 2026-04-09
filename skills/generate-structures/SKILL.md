---
name: generate-structures
description: Use when producing base geometry (tubes, cones, integrated fins, integral shoulders, motor mount wall thickening, full assembly) from a parts manifest via build123d. Pass 1 of the CAD pipeline — no holes, no pockets, no detail features (those are Pass 2, see modify-structures).
---

# Generate Structures

## Overview

`generate-structures` is **Pass 1 of the CAD pipeline**. It takes a parts manifest and produces the base geometry for every printable part — the structural shell. Pass 2 (`modify-structures`) then adds detail features like holes, pockets, and mounts on top of these base STEPs.

The separation matters because:

- **Iteration speed** — changing a hole pattern doesn't require regenerating the structural shell
- **Review boundaries** — you can verify the base geometry is correct before committing to detail features
- **Clean mental model** — structural decisions (diameters, walls, fusion) are separate from detail decisions (retention, mounts, vents)

This skill is **rocketry-agnostic** — it knows about build123d and parts and assemblies, not about nose cones and fins. The manifest's feature blocks drive what gets built.

**Core principle:** Read the manifest, trust the manifest. Every geometric decision was made by the DFx skill. `generate-structures` is a faithful executor, not a designer.

## When to Use

- `parts_manifest.json` exists at `<project_root>/parts_manifest.json` and needs Pass 1 geometry
- A base STEP file is missing or out of sync with its feature block
- The user asks to regenerate structural geometry

## Inputs

`<project_root>/parts_manifest.json` — the authoritative parts list. Specifically the `parts[].features` block for each part. Do not read the `modifications` block — that's `modify-structures`' job.

## Output

- `<project_root>/build123d/<name>.py` — one parametric script per part (base geometry only)
- `<project_root>/CAD/<name>.step` — the STEP file exported by each script
- `<project_root>/CAD/full_assembly.step` — composed from all individual parts if `manifest["assemblies"]` is non-empty
- `<project_root>/visualizations/<name>.png` — 3-panel render of each part for visual verification

## Steps

### 1. Load the Manifest

```
manifest = manufacturing_manifest(action="read", project_root="<project_root>")
```

Verify it has `schema_version`, `parts`, `directories`, and `assemblies`. If anything is missing, stop and ask the `design-for-additive-manufacturing` skill to regenerate the manifest — do not fill in missing fields.

### 2. Create Directories

```
Bash("mkdir -p <project_root>/build123d <project_root>/CAD <project_root>/visualizations")
```

### 3. Generate Each Part's Base Geometry

For each entry in `manifest["parts"]`:

1. **Write the script** with the `Write` tool. Use the script structure below and build only the features in `features` — ignore `modifications` entirely at this stage.
2. **Execute** via `build123d_script(script_path=<scripts_dir>/<name>.py, out_dir=<step_dir>)`.
3. **Render** via `build123d_render(step_file_path=<step_dir>/<name>.step, out_path=<visualizations_dir>/<name>.png)` and `Read` the resulting PNG.
4. **Verify** via `build123d_extract` that the bounding box matches `features["length_mm"]` and `features["od_mm"]`.

Do not proceed if a part fails verification. Fix the script and re-run.

### 4. Generate the Full Assembly

After all individual parts are verified, produce `assemblies/full_assembly.step` (well, `CAD/full_assembly.step` per the layout convention). Each entry in `manifest["assemblies"]` becomes one assembly STEP:

1. Write a composition script in `build123d/<assembly_name>.py` that imports each part in the `parts_fore_to_aft` list.
2. Position each part along Z by cumulative offsets derived from each part's `features["length_mm"]`.
3. Compose via `Compound` and export to the assembly's `step_path`.
4. Render with `build123d_render` and `Read` the result. The assembly render is the **first check for cross-part issues** — shoulder alignment, visible gaps, off-axis fins. Spend more time looking at this one than at any individual part render.

## Script Structure

Every generated script should follow this shape so it's readable and debuggable:

```python
"""
<Part name> — base structural geometry.
Derived from: <OR components>
Manifest entry: parts[<index>]
Pass 1 (generate-structures): base shell only, no modifications.
"""
from build123d import *
from pathlib import Path

# --- Parameters (from manifest features block — do not hardcode) ---
LENGTH_MM = 400.0
OD_MM = 64.0
ID_MM = 58.0
# ... other parameters from features ...

OUTPUT = Path("<absolute path to CAD/<name>.step>")

# --- Build ---
with BuildPart() as part:
    # geometry
    pass

# --- Export ---
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
export_step(part.part, str(OUTPUT))
```

Key rules:

- **OUTPUT is an absolute path** resolved from `project_root` + the manifest's `step_path`.
- **Parameters are named constants at the top** — match the manifest's feature block exactly.
- **Imports limited to `build123d`, `pathlib`, `math`, `typing`** — `build123d_script` runs in isolated mode.
- **No hole patterns, no pocket subtractions, no retention features.** Those are Pass 2.

## Coordinate Convention

Z is the primary build axis. Positive Z extends aft. The manifest's feature blocks express positions in Z; translate them directly to build123d Z coordinates.

## Common build123d API Patterns

### Hollow cylinder (tube)

```python
with BuildPart() as tube:
    with BuildSketch(Plane.XY):
        Circle(OD_MM / 2)
        Circle(ID_MM / 2, mode=Mode.SUBTRACT)
    extrude(amount=LENGTH_MM)
```

### Revolve around the Z axis (nose cones, transitions, boattails)

```python
with BuildPart() as revolved:
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Spline(*profile_points)
            Line(profile_points[-1], (0, PART_LENGTH))
            Line((0, PART_LENGTH), (0, 0))
        make_face()
    revolve(axis=Axis.Z)
```

### Polar-array a feature around Z

```python
# Build one instance
with BuildPart() as feature:
    # single-instance geometry
    pass

feature_shape = feature.part
with BuildPart() as array:
    for i in range(COUNT):
        add(feature_shape.rotate(Axis.Z, i * (360 / COUNT)))
```

### Fuse a feature into a parent body

```python
with BuildPart() as airframe:
    # Parent hollow tube
    with BuildSketch(Plane.XY):
        Circle(OD_MM / 2)
        Circle(ID_MM / 2, mode=Mode.SUBTRACT)
    extrude(amount=LENGTH_MM)

    # Fused feature (add mode, same BuildPart context)
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline(*feature_points, close=True)
        make_face()
    extrude(amount=FEATURE_THICK / 2, both=True, mode=Mode.ADD)
```

### Assembly composition

```python
from build123d import import_step, Compound

parts = [
    import_step("CAD/nose_cone.step"),
    import_step("CAD/upper_airframe.step"),
    import_step("CAD/lower_airframe.step"),
]

# Position fore-to-aft along Z using each part's bounding box Z extent
positioned = []
cursor_z = 0.0
for p in parts:
    positioned.append(p.translate((0, 0, cursor_z)))
    cursor_z += p.bounding_box().size.Z

assembly = Compound(label="full_assembly", children=positioned)
export_step(assembly, "<absolute path to CAD/full_assembly.step>")
```

## Feature Recipe Reference

The DFAM manifest uses named feature types. Below are the Pass-1 compositions of the generic build123d patterns above. Feature types that involve holes or pockets belong to `modify-structures` — they are NOT listed here.

| Feature type | Composition |
|---|---|
| base cylinder (`length_mm`, `od_mm`, `id_mm`) | Hollow cylinder pattern. |
| `local_wall_thickening` | Hollow cylinder with a secondary inner `Circle` at `bore_mm / 2` subtracted only between `[region_start_mm, region_end_mm]` along Z. Two extrusions: one for the full outer shell, one for the locally thickened inner wall. |
| `integrated_fins` | After the parent hollow cylinder, build a single fin as a `Polyline` sketch in the XZ plane (root_chord on the body surface, tip_chord at body_r + span, sweep applied at the leading edge), extrude ±thickness/2 in Y, then polar-array `count` copies around Z. Apply a `fillet_mm` fillet at the root edge if `fillet_mm` > 0. |
| `integral_aft_shoulder` | At Z = parent `length_mm`, extrude a second hollow cylinder with OD = `od_mm` and ID = parent `id_mm`, length = `length_mm`. The `assembly_clearance_mm` field defaults to 0 (interference fit); use the shoulder OD from the manifest verbatim rather than re-applying clearance yourself. |
| `forward_stop_lip` | At the fore end of the motor bore (Z = region_start_mm), extrude a small annulus inward (OD = bore radius, ID = stop ID) by `thickness_mm` in −Z. Fuse with parent. |

If a feature type isn't in this table, query the `cad_examples` reference collection (see below) before improvising. If the feature is hole-shaped or pocket-shaped, it belongs in `modify-structures`, not here.

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

Example queries: `"build123d loft between circles"`, `"build123d sweep along path"`, `"build123d thicken surface"`, `"build123d fillet edge selection"`. **If the search returns no results**, fall back to the patterns above or ask the user. **If the search errors**, proceed silently.

## Verification Workflow

After each successful `build123d_script` call:

1. **`build123d_render(step_file_path, out_path=<visualizations_dir>/<name>.png)`** — writes the PNG into `visualizations/`
2. **`Read(file_path=<png_path>)`** — visually inspect:
   - Does the overall shape match the feature block's intent?
   - Are any expected geometric features visible and correctly placed?
   - Is the part inside-out (walls appearing solid where there should be a bore)?
   - Is any dimension obviously wrong?
3. **`build123d_extract(step_file_path)`** — compare the bounding box Z extent to `features["length_mm"]` and the max XY extent to `features["od_mm"]`. Mismatches > 1 mm indicate a script bug.
4. **If any check fails, fix the script and re-run.** Do not accept broken geometry, do not defer verification to "I'll check all of them at the end".

After the full assembly is generated, spend extra time on the assembly render. Cross-part issues (visible gaps at joints, off-axis fins, shoulder mismatches) are only visible here.

## Red Flags — Stop and Fix

- A script imports anything outside `build123d`, `pathlib`, `math`, `typing`
- A script has `Hole(...)` or `extrude(..., mode=Mode.SUBTRACT)` subtracting a hole pattern — that's a Pass 2 operation, belongs in `modify-structures`
- A script emits a STEP file whose bounding box doesn't match the manifest's feature block
- A part is generated that isn't in the manifest
- A part in the manifest is skipped without a reported failure
- `full_assembly.step` shows a visible gap between sections — check `integral_aft_shoulder.od_mm` matches the mating tube's `id_mm`
- `build123d_extract` volume is zero or NaN — degenerate geometry, script has a topology bug
- A fin is not fused into the parent body — check the feature block specifies `integrated_fins` and the script uses `Mode.ADD` rather than exporting fins as a separate part

## Handoff to Pass 2

Once every individual part and the full assembly are verified:

- If **any part in the manifest has a non-empty `modifications` list**, hand off to `modify-structures` to apply them.
- If **every part's `modifications` list is empty**, Pass 1 was the whole job — hand back to the build123d subagent for reporting.

Do not run `modify-structures` twice for the same manifest — a successful modify pass overwrites the base STEP. If the user wants to add a modification after the fact, they can edit the manifest and run both passes again.

## Quick Reference

```
# the Pass 1 loop
for part in manifest["parts"]:
    write_script(part, features_only=True)
    build123d_script(script_path, out_dir)
    build123d_render(step_file_path, out_path=visualizations_dir/<name>.png)
    Read(png_path)
    build123d_extract(step_file_path)
    if check_failed: fix_and_retry()

# then the assembly
for asm in manifest["assemblies"]:
    write_assembly_script(asm)
    build123d_script(...)
    build123d_render(...) → Read → verify cross-part alignment

# handoff
if any(part.modifications for part in manifest["parts"]):
    load modify-structures and run Pass 2
else:
    report back to the orchestrator
```
