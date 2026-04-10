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
3. **Render** via `build123d_render(step_file_path=<step_dir>/<name>.step)` and `Read` the resulting PNG. The tool auto-routes renders of STEPs in `CAD/` to the sibling `visualizations/` directory — you don't need to pass `out_path` for standard project layouts. For non-standard locations, pass `out_path=<visualizations_dir>/<name>.png` explicitly.
4. **Verify** via `build123d_extract` that the bounding box matches `features["length_mm"]` and `features["od_mm"]`.

Do not proceed if a part fails verification. Fix the script and re-run.

### 4. Generate the Full Assembly

After all individual parts are verified, produce `assemblies/full_assembly.step` (well, `CAD/full_assembly.step` per the layout convention). Each entry in `manifest["assemblies"]` becomes one assembly STEP:

1. Write a composition script in `build123d/<assembly_name>.py` that imports each part in the `parts_fore_to_aft` list.
2. Position each part along Z by cumulative offsets derived from each part's `features["length_mm"]`.
3. Compose via `Compound` and export to the assembly's `step_path`.
4. Render with `build123d_render` and `Read` the result. The assembly render is the **first check for cross-part issues** — shoulder alignment, visible gaps, off-axis fins. Spend more time looking at this one than at any individual part render.

## Script Structure

Every generated script should follow this shape so it's readable, debuggable, and **portable across machines**:

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

# --- Resolve output path relative to this script's location ---
# This script lives at <project_root>/build123d/<name>.py
# STEP file goes to <project_root>/CAD/<name>.step
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT = PROJECT_ROOT / "CAD" / "<name>.step"

# --- Build ---
with BuildPart() as part:
    # geometry
    pass

# --- Export ---
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
export_step(part.part, str(OUTPUT))
```

Key rules:

- **OUTPUT is a relative path resolved from `__file__`**, not an absolute path hardcoded into the script. The script assumes it lives at `<project_root>/build123d/<name>.py` and writes to `<project_root>/CAD/<name>.step`. This keeps the script **portable** — the project directory can be moved, renamed, or checked out on a different machine and the script still works without editing.
- **Never embed an absolute path** like `/Users/someone/rockets/my_rocket/CAD/...` in a script. That breaks the moment anyone else opens the repo.
- **Parameters are named constants at the top** — match the manifest's feature block exactly.
- **Imports limited to `build123d`, `pathlib`, `math`, `typing`** — `build123d_script` runs in isolated mode.
- **No hole patterns, no pocket subtractions, no retention features.** Those are Pass 2.

## Part Orientation Convention

**Each part is built in print-ready orientation.** This is the most important rule in this skill — get it wrong and PrusaSlicer will reject the part with errors like *"There is an object with no extrusions in the first layer"*.

### The rule

Every part is built in its own **local frame**, with the **print-bed face at the lowest Z value**. PrusaSlicer slices STEP files in their as-built orientation — the CLI does NOT auto-orient — so the orientation in the script is the orientation that gets printed.

This is **part-local**, not assembly-global. The part's local Z is "the printer's build axis", not "the rocket's fore-aft axis." The two only sometimes align.

### Per-part-type rules

| Part type | Build orientation | Bed face | Why |
|---|---|---|---|
| **Nose cone** (any shape, with integral shoulder) | **Shoulder bottom at Z=0**, shoulder extends to Z=shoulder_length, then ogive extends to Z=shoulder_length+nose_length | Shoulder bottom (a solid circle slightly smaller than the body tube ID) | The shoulder bottom is a solid closed circle, giving plenty of bed contact. Nose cones are built **solid by default** for AM (no hollowing) — the mass penalty is small for typical sizes and the structural benefit is significant. Tip-down nose cones fail to slice with "no extrusions in the first layer". |
| **Body tube** (no aft shoulder) | Either face at Z=0 — pick **fore at Z=0** by convention | Either circular face | Both ends are the same. Picking fore is just for consistency with parts that DO have an aft shoulder. |
| **Body tube with integral aft shoulder** | **Fore at Z=0**, body extends to Z=length, shoulder extrudes from Z=length to Z=length+shoulder_length | Fore face (the wider face) | The shoulder is narrower than the body — printing on the shoulder end gives a smaller bed-contact area. Print on the wider face. |
| **Motor mount tube (when separate)** | Either face at Z=0 — pick the fore face by convention | Either circular face | Same reasoning as plain body tubes. |
| **Coupler (when separate)** | One face at Z=0 | Either circular face | Symmetric. |
| **Centering ring (when separate)** | One face at Z=0, ring lies flat in XY | The flat circular face | The ring's natural print orientation is flat — much better than standing it on edge. |

### Why this isn't the same as the rocket's coordinate system

In the rocket assembly's logical frame, the "fore" end of the rocket is at one extreme and the "aft" end (motor) is at the other. OpenRocket measures positions from the nose tip going aft.

In a part's **local print frame**, the "low Z" end is whatever face will sit on the build plate. For a nose cone, that's the base — but the base is the **aft** side of the cone in rocket terms (the side that mates with the airframe below it). The local Z direction in the nose cone script is **opposite** the rocket's "fore-to-aft" direction.

That's fine. Each part script lives in its own local frame. The assembly composition (next section) handles transforms back into the rocket's logical orientation as needed for visualization. Critically: **don't try to make the part script's Z axis match the rocket's Z axis. Match the printer's build axis instead.**

### Quick mental check before writing a script

Before you write any script, ask: *"If I sliced this part right now in PrusaSlicer, what's the very first layer?"* The answer should be the largest stable face of the part. If it's a single point, a small circle, an edge, or "the inside of a hollow shell," the orientation is wrong — fix it before going any further.

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

### Tangent ogive nose cone with integral shoulder (solid, shoulder-down for printing)

This is the canonical nose cone recipe for AM. The part has two regions stacked along Z:

- **Shoulder** at the bottom (Z=0 to Z=SHOULDER_LEN_MM): a short solid cylinder sized to the body tube ID. This is what plugs into the upper airframe at assembly time, and it's the print-bed face during printing.
- **Ogive** above the shoulder (Z=SHOULDER_LEN_MM to Z=SHOULDER_LEN_MM+NOSE_LEN_MM): the visible cone shape. The base sits flush with the airframe's fore face when assembled.

The whole thing is **solid** by default. For AM the mass penalty of a solid nose cone is small for typical sizes, and the benefits are real: no first-layer issues, no thin walls to delaminate, no inner spline tessellation artifacts. If you specifically need a hollow nose cone (very large diameter, weight-sensitive design), opt in via `fusion_overrides={"nose_cone_hollow": True}` and the recipe below grows a subtraction pass.

```python
import math
from build123d import (
    BuildPart, BuildSketch, BuildLine, Plane, Axis, Mode,
    Polyline, Circle, make_face, revolve, extrude, export_step,
)
from pathlib import Path

# --- Parameters (from manifest features block) ---
NOSE_LEN_MM = 120.0          # ogive length, base to tip
BASE_OD_MM  = 64.0           # ogive base diameter (matches airframe OD)
SHOULDER_OD_MM = 60.0        # shoulder OD (matches airframe ID, zero clearance)
SHOULDER_LEN_MM = 30.0       # shoulder length (from manifest features.shoulder.length_mm)

# --- Resolve output path relative to this script's location ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT = PROJECT_ROOT / "CAD" / "nose_cone.step"

# --- Tangent ogive profile ---
BASE_R_MM = BASE_OD_MM / 2
rho = (BASE_R_MM**2 + NOSE_LEN_MM**2) / (2 * BASE_R_MM)

def outer_r(z_from_base: float) -> float:
    """Outer radius of the ogive at distance ``z_from_base`` above the cone base.

    z_from_base = 0 is the base (radius BASE_R_MM); z_from_base = NOSE_LEN_MM
    is the tip (radius 0). The cone base sits at Z = SHOULDER_LEN_MM in the
    final part frame; there is a solid shoulder below it.
    """
    return max(
        math.sqrt(max(rho**2 - (NOSE_LEN_MM - z_from_base)**2, 0.0))
        + BASE_R_MM
        - rho,
        0.0,
    )

# Build a closed polyline for the ogive cross-section in the XZ plane.
# Walk: base centre → base edge → up the curve to the tip → back down
# the central axis to the base centre. close=True closes the loop.
#
# At N_SAMPLES = 40 the polyline is visually indistinguishable from a
# spline; this also avoids the Spline+Line closure subtleties that can
# silently produce a degenerate face.
N_SAMPLES = 40
profile = [(0.0, SHOULDER_LEN_MM)]                 # base centre
profile.append((BASE_R_MM, SHOULDER_LEN_MM))       # base edge (start of curve)
for i in range(1, N_SAMPLES + 1):
    z_from_base = i * NOSE_LEN_MM / N_SAMPLES
    z_world = SHOULDER_LEN_MM + z_from_base
    profile.append((outer_r(z_from_base), z_world))
# Force the last point to (0, tip) so the curve closes onto the central axis
profile[-1] = (0.0, SHOULDER_LEN_MM + NOSE_LEN_MM)

with BuildPart() as nose_cone:
    # 1. Solid shoulder at the bottom (Z = 0 to Z = SHOULDER_LEN_MM).
    #    This is a SOLID disk extruded into a cylinder — not a hollow tube.
    #    The closed flat bottom is the print-bed face.
    with BuildSketch(Plane.XY):
        Circle(SHOULDER_OD_MM / 2)
    extrude(amount=SHOULDER_LEN_MM)

    # 2. Solid ogive on top of the shoulder, fused into the same BuildPart.
    with BuildSketch(Plane.XZ):
        with BuildLine():
            Polyline(*profile, close=True)
        make_face()
    revolve(axis=Axis.Z, mode=Mode.ADD)

# --- Export ---
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
export_step(nose_cone.part, str(OUTPUT))
```

Key points:

- **Z = 0 is the shoulder bottom** — this is the print-bed face. It is a **solid closed circle** of diameter `SHOULDER_OD_MM`, giving plenty of bed contact area (~2600 mm² for a 58 mm shoulder).
- The shoulder extrudes from a solid `Circle`, not a hollow annulus. The shoulder is **not** a tube.
- The ogive sits on top of the shoulder via a second `revolve` in the same `BuildPart` context, fused with `Mode.ADD`. There is a small step in radius at Z = SHOULDER_LEN_MM where the shoulder OD (≈ airframe ID) meets the ogive base OD (= airframe OD). That step matches the airframe's wall thickness — it's exactly the geometry that lets the nose cone sit flush against the airframe at assembly time.
- The whole part is **solid**. No hollowing pass.
- The first layer when sliced is the full shoulder cross-section (a solid circle ~58 mm in diameter for a 64 mm body tube). No "no extrusions in the first layer" failures.

For non-ogive nose cone shapes (conical, parabolic, von Kármán), keep the same shoulder-down structure — only the `outer_r(z)` function changes.

**To opt into a hollow nose cone**, the manifest's `features.hollow` field is set to `true` and `features.wall_mm` is the desired wall thickness. Add a third pass to the BuildPart that subtracts the inner cavity, leaving `wall_mm` of material everywhere except a few mm of solid material at the tip. The default is solid; only do this when the manifest asks for it.

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
from pathlib import Path

# Resolve paths relative to this script's location (same pattern as per-part scripts)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CAD_DIR = PROJECT_ROOT / "CAD"

parts = [
    import_step(str(CAD_DIR / "nose_cone.step")),
    import_step(str(CAD_DIR / "upper_airframe.step")),
    import_step(str(CAD_DIR / "lower_airframe.step")),
]

# Position fore-to-aft along Z using each part's bounding box Z extent
positioned = []
cursor_z = 0.0
for p in parts:
    positioned.append(p.translate((0, 0, cursor_z)))
    cursor_z += p.bounding_box().size.Z

assembly = Compound(label="full_assembly", children=positioned)
OUTPUT = CAD_DIR / "full_assembly.step"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
export_step(assembly, str(OUTPUT))
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

- **A nose cone (or any revolved part with a clear "wide end" and "narrow end") is built tip-down.** PrusaSlicer will fail with `"There is an object with no extrusions in the first layer"`. The fix is always: rebuild with the wide face at Z=0 (see the tangent ogive recipe above). This is the single most common slice failure for fresh designs — verify orientation BEFORE handing off to the prusaslicer subagent.
- A script imports anything outside `build123d`, `pathlib`, `math`, `typing`
- A script has `Hole(...)` or `extrude(..., mode=Mode.SUBTRACT)` subtracting a hole pattern — that's a Pass 2 operation, belongs in `modify-structures`
- A script emits a STEP file whose bounding box doesn't match the manifest's feature block
- A part is generated that isn't in the manifest
- A part in the manifest is skipped without a reported failure
- `full_assembly.step` shows a visible gap between sections — check `integral_aft_shoulder.od_mm` matches the mating tube's `id_mm`
- `build123d_extract` volume is zero or NaN — degenerate geometry, script has a topology bug
- A fin is not fused into the parent body — check the feature block specifies `integrated_fins` and the script uses `Mode.ADD` rather than exporting fins as a separate part
- A part has its bed face (lowest Z) as a single point, an edge, or a small ring. PrusaSlicer needs a planar face with significant area at Z=0. If the lowest Z is sub-millimeter in cross-section, the orientation is wrong even if the rest of the geometry looks fine in the render.

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
