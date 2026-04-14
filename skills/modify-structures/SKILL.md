---
name: modify-structures
description: Use when applying detail features (holes, pockets, vents, mounts) to base STEP files already produced by generate-structures. Pass 2 of the CAD pipeline — reads modifications from the component tree, imports existing base STEPs, and writes modified STEPs back.
---

# Modify Structures

## Overview

`modify-structures` is **Pass 2 of the CAD pipeline**. It takes the base STEP files produced by `generate-structures` and applies detail features specified in each part's `modifications` list: radial holes for fasteners, through-holes for screws, rectangular pockets for electronics bays, cylindrical pockets for camera mounts, vent holes, weight-relief cuts, and any other subtractive or additive detail operations that aren't part of the structural shell.

The split exists because:

- **Iteration speed** — changing hole positions or adding a camera mount doesn't require regenerating the structural shell
- **Review boundaries** — you verified the base geometry in Pass 1; Pass 2 is purely "apply these details"
- **Future-proofing** — rail buttons, altimeter bay cutouts, payload mounts, and custom user requests all plug into the same modification framework

This skill is **rocketry-agnostic** — it knows about build123d boolean operations and modification recipes, not about rockets. The manifest's `modifications` list drives what gets applied.

**Core principle:** Modifications are applied to base STEPs produced by Pass 1. Do not re-generate base geometry here. If a modification requires changing the structural shell, update the manifest's `features` block and re-run Pass 1.

**Never edit `component_tree.json` directly to add or change modifications.** The modifications list is populated by `manufacturing_annotate_tree` based on DFAM rules and user-specified overrides. If the modifications list is missing entries the user wants (e.g., rail button holes, vent holes), re-run `manufacturing_annotate_tree` with the appropriate parameters — do not hand-edit the JSON.

## When to Use

- `generate-structures` has completed Pass 1 successfully
- At least one entry in `manifest["parts"]` has a non-empty `modifications` list
- The user asks to add retention hardware, accessory mounts, vent holes, or other detail features

If every part's `modifications` list is empty (which is the default for a freshly generated DFAM manifest — retention defaults to `"none"`), skip this skill entirely.

## Inputs

- `<project_root>/gui/component_tree.json` — the `parts[].modifications` lists are the authoritative spec (populated by `manufacturing_annotate_tree`, never hand-edited)
- `<project_root>/cadsmith/step/<name>.step` — base STEPs from Pass 1

## Output

- `<project_root>/cadsmith/source/<name>_modified.py` — one modification script per part with non-empty modifications (kept separate from the Pass 1 script for auditability)
- `<project_root>/cadsmith/step/<name>.step` — **overwritten** with the modified version
- `gui/assembly.json` — regenerated via `cadsmith_assembly(action="generate")` if any part was modified
- `<project_root>/gui/assets/png/<name>.png` — re-rendered after modification

## Steps

### 1. Load the Manifest

```
manifest = read_json("<project_root>/gui/component_tree.json")
```

### 2. Identify Parts Needing Modification

```
parts_to_modify = [p for p in manifest["parts"] if p["modifications"]]
```

If the list is empty, skip the rest of this skill.

### 3. For Each Part With Modifications

1. **Verify the base STEP exists** at `<project_root>/<step_path>`. If missing, run `generate-structures` first — do not fabricate a base here.
2. **Write the modification script** to `<project_root>/cadsmith/source/<name>_modified.py`. The script imports the base STEP, applies each modification in order, and exports back to the same `step_path` (overwriting).
3. **Execute** via `cadsmith_run_script`. The tool runs the script in isolated mode and returns the path of the overwritten STEP.
4. **Re-render** via `cadsmith_generate_preview(step_file_path=<step_path>, out_path=<images_dir>/<name>.png)` and `Read` to visually verify the modifications are in the right place.
5. **Re-extract** via `cadsmith_extract_part` to confirm the bounding box hasn't changed unexpectedly (modifications typically only remove material, so bounding box should match).
6. **Pause for user feedback.** Modifications are detail features that interact with the base geometry in ways that are hard to verify autonomously — hole placement relative to shoulders, pocket depth vs. wall thickness, angular alignment of through-holes with mating parts. Show the user the re-rendered PNG, describe what was modified (e.g., "Added 4× M4 heat-set holes at Z=25mm on the upper airframe shoulder"), and ask whether the placement looks correct. See **User Feedback on Modifications** below.

### 4. Regenerate the Full Assembly

If any part was modified, the assembly layout is stale — regenerate it via `cadsmith_assembly(action="generate", project_dir=<project_root>)`. The GUI's 3D viewer will update automatically.

## Modification Script Structure

Unlike Pass 1 scripts which build geometry from scratch, Pass 2 scripts import an existing STEP and apply operations to it. Like Pass 1, the paths are resolved **relative to the script's own location** so the project stays portable:

```python
"""
<Part name> — detail feature modifications.
Pass 2 (modify-structures): applies holes / pockets / mounts to the
base STEP produced by generate-structures.
"""
from build123d import *
from pathlib import Path
from math import cos, sin, radians

# --- Resolve paths relative to this script's location ---
# This script lives at <project_root>/cadsmith/source/<name>_modified.py
# Base STEP and output STEP are at <project_root>/cadsmith/step/<name>.step
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BASE_STEP = PROJECT_ROOT / "step" / "<name>.step"
OUTPUT = BASE_STEP  # overwrite in place

# Import the base
base = import_step(str(BASE_STEP))

# Apply each modification in order
with BuildPart() as modified:
    add(base)
    # ... modification operations below, in manifest order ...

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
export_step(modified.part, str(OUTPUT))
```

Key rules:

- **Paths are relative to `__file__`.** Resolve `PROJECT_ROOT` from the script's own location. This keeps the script portable across machines and checkouts — never hardcode an absolute path like `/Users/someone/rockets/...` in a modification script.
- **Import the base STEP, don't rebuild the shell.** If you find yourself re-declaring `LENGTH_MM` and `OD_MM` to rebuild a cylinder, you're in the wrong skill.
- **Apply modifications in manifest order.** Some modifications interact (e.g. a pocket inside a heat-set boss region); order matters.
- **Overwrite the base STEP in place.** The manifest's `step_path` is the canonical location; don't emit a separate `_modified.step` file.
- **Imports limited to `build123d`, `bd_warehouse`, `pathlib`, `math`, `typing`.** Same isolated-mode constraint as Pass 1. Use `bd_warehouse.fastener` for spec-correct fastener geometry in boolean cuts (heat-set pockets, counterbores, nut traps).

## Modification Recipe Reference

Each `modification` entry in the manifest has a `kind` field that identifies the recipe. Below are the supported kinds and their build123d implementations.

### `radial_holes` — cylindrical holes drilled radially inward from a tube surface

**Fields:**
- `count` — number of holes in the polar array
- `angular_positions_deg` — explicit list of angles in degrees, or omit to evenly space
- `z_mm` — Z position of the hole centres (single value for all holes in this modification)
- `radius_mm` — radial distance from the Z axis (where the hole axis passes through; typically the shoulder OD / 2)
- `hole_diameter_mm` — diameter of each hole
- `hole_depth_mm` — blind depth (for heat-set inserts) or pass 0 for through-wall

**Recipe:**

```python
positions = modification.get("angular_positions_deg") or [
    i * (360 / modification["count"]) for i in range(modification["count"])
]
for angle_deg in positions:
    ang = radians(angle_deg)
    cx = modification["radius_mm"] * cos(ang)
    cy = modification["radius_mm"] * sin(ang)
    hole_plane = Plane(
        origin=(cx, cy, modification["z_mm"]),
        x_dir=(-sin(ang), cos(ang), 0),
        z_dir=(-cos(ang), -sin(ang), 0),
    )
    with BuildSketch(hole_plane):
        Circle(modification["hole_diameter_mm"] / 2)
    extrude(amount=modification["hole_depth_mm"], mode=Mode.SUBTRACT)
```

Use this for heat-set insert receivers and shear pin holes. For heat-set inserts, prefer using `bd_warehouse` for spec-correct pocket dimensions — call `cadsmith_bd_warehouse_info(generator_class="HeatSetNut", generator_params={"size": "M4-0.7-8", "fastener_type": "Hilitchi"})` to get exact `nut_diameter` and `nut_thickness`, then subtract the geometry directly:

```python
from bd_warehouse.fastener import HeatSetNut
insert = HeatSetNut("M4-0.7-8", "Hilitchi", simple=True, mode=Mode.PRIVATE)
# Use insert.nut_diameter and insert.nut_thickness for the pocket,
# or subtract the insert geometry directly with mode=Mode.SUBTRACT
```

### `radial_through_holes` — through-wall clearance holes

Same fields as `radial_holes` except `hole_depth_mm` is ignored (the hole passes all the way through the wall). Use this for screw clearance holes on the mating side of a heat-set joint.

**Recipe:** identical to `radial_holes` but use a large extrude depth (e.g. 2× tube OD) to ensure the hole passes through both walls if the tube is hollow. Alternatively, use `Hole(...)` which automatically extends through material.

```python
positions = modification.get("angular_positions_deg") or [
    i * (360 / modification["count"]) for i in range(modification["count"])
]
for angle_deg in positions:
    ang = radians(angle_deg)
    cx = modification["radius_mm"] * cos(ang)
    cy = modification["radius_mm"] * sin(ang)
    hole_plane = Plane(
        origin=(cx, cy, modification["z_mm"]),
        x_dir=(-sin(ang), cos(ang), 0),
        z_dir=(-cos(ang), -sin(ang), 0),
    )
    with BuildSketch(hole_plane):
        Circle(modification["hole_diameter_mm"] / 2)
    # Extrude far enough to punch through both walls of a hollow tube
    extrude(amount=200.0, mode=Mode.SUBTRACT)
```

### Future: `rectangular_pocket` — surface-mounted cutout for electronics, cameras, access panels

Not yet implemented. Reserved fields: `target` (Z and angular position), `width_mm`, `height_mm`, `depth_mm`, `fillet_mm`. When this lands, query the `cad_examples` reference collection for a known-good implementation before improvising.

### Future: `cylindrical_pocket` — circular recess for camera lenses, altimeter ports

Not yet implemented. Reserved fields: `target`, `diameter_mm`, `depth_mm`.

### Future: `rail_button_mount` — protruding boss for an adhesive rail button

Not yet implemented. When this lands, it will likely be an **additive** modification (the only one in this skill that adds material rather than removing it).

For any `kind` not in the recipe reference, query `rag_reference(action="search", collection="cad_examples", query=f"build123d {modification['kind']}", n_results=3)`. If no results, ask the user rather than improvising.

## Verification After Modification

After each part is modified:

1. **Re-render**: `cadsmith_generate_preview(step_file_path=<step_path>)`. The tool auto-routes to `png/<name>.png`, overwriting the Pass 1 render — the modified version is the current truth.
2. **Visual check**: does the render show the modifications in the expected positions? Heat-set holes should appear as small dark circles around the shoulder mid-length. Through-holes should appear at matching angles on the mating tube.
3. **Dimensional check**: `cadsmith_extract_part` — the bounding box should be unchanged (all current modifications are subtractive). If the volume dropped by more than ~5% of the base, flag it — you may have subtracted too much.
4. **User feedback**: pause and ask the user to confirm the modifications. See below.

## User Feedback on Modifications

All modifications require user feedback before proceeding to the next part. Unlike Pass 1 where only complex features need a pause, Pass 2 modifications are inherently detail-oriented and their correctness depends on assembly context that only the user can fully judge.

### What to show the user

1. **The re-rendered PNG** — show the path or display inline
2. **A summary of what was applied**, e.g.:
   - "Applied 4× radial heat-set holes (M4, 5.7mm × 7mm) at Z=25mm, evenly spaced at 0°/90°/180°/270° on the upper airframe shoulder"
   - "Applied 4× through-holes (4.5mm clearance) at matching positions on the lower airframe mating end"
3. **A targeted question**:
   - For hole patterns: "Do the hole positions align with where you want the retention hardware? Are the angular positions correct for your assembly?"
   - For pockets: "Does the pocket depth look right relative to the wall thickness? Is the placement where you expected?"
   - For paired modifications (heat-set + through-hole): "These two parts mate at this joint. Do the hole patterns on both sides look aligned?"

### Handling feedback

- **Approval** — proceed to the next part's modifications.
- **"Move the holes" / "Change the angle"** — update the manifest's modification entry, rewrite the script, re-run, re-render, and ask again.
- **"Skip this modification"** — remove it from the script (but leave it in the manifest for traceability), re-run, and proceed.

## Red Flags — Stop and Fix

- A modification script rebuilds the base shell instead of importing it via `import_step`
- A `modifications` list is empty but the Pass 2 script still produces output — the part should be untouched
- A hole pattern appears at the wrong Z position — cross-reference the manifest's `z_mm` against the part's `features["length_mm"]` to confirm the shoulder position was computed correctly in DFAM
- Clearance through-holes and heat-set insert holes don't align at the joint — the angular positions and Z positions must match between the shoulder-emitting part and the mating part
- The assembly render shows holes in the wrong place or missing — check each part's modification script independently before blaming the composition
- A modification adds material where the base was hollow (e.g. a pocket that punches through a fin root) — check `depth_mm` and make sure you're subtracting, not adding

## Handoff to the cadsmith Subagent

After every modified part is verified and the full assembly is regenerated, hand control back to the `cadsmith` subagent. The subagent reports to the orchestrator which then hands off to the `prusaslicer` subagent for slicing.

Do not re-run `generate-structures` after a successful modify pass. The modified STEP is the current truth; regenerating base geometry would overwrite your modifications.

## Quick Reference

```
# the Pass 2 loop
for part in manifest["parts"]:
    if not part["modifications"]:
        continue
    verify_base_step_exists(part["step_path"])
    write_modification_script(part)
    cadsmith_run_script(script_path, out_dir)
    cadsmith_generate_preview(step_file_path, out_path=images_dir/<name>.png)
    Read(png_path)
    cadsmith_extract_part(step_file_path)
    if check_failed: fix_and_retry()
    # always pause for user feedback on modifications
    ask_user("Applied <modifications> to <part>. Does the placement look correct?")
    wait_for_response()
    if user_requested_change: update_and_retry()

# regenerate the assembly if anything changed
if any_part_was_modified:
    cadsmith_assembly(action="generate", project_dir=<project_root>)
    ask_user("Regenerated assembly with modifications. Do the joints look right?")
    wait_for_response()

# then handoff
report_to_cadsmith_subagent()
```
