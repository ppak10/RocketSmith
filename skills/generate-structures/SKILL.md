---
name: generate-structures
description: Use when producing base geometry (tubes, cones, integrated fins, integral shoulders, motor mount wall thickening, full assembly) from a component tree via build123d. Pass 1 of the CAD pipeline — no holes, no pockets, no detail features (those are Pass 2, see modify-structures).
---

# Generate Structures

## Overview

`generate-structures` is **Pass 1 of the CAD pipeline**. It takes a component tree and produces the base geometry for every printable part — the structural shell. Pass 2 (`modify-structures`) then adds detail features like holes, pockets, and mounts on top of these base STEPs.

The separation matters because:

- **Iteration speed** — changing a hole pattern doesn't require regenerating the structural shell
- **Review boundaries** — you can verify the base geometry is correct before committing to detail features
- **Clean mental model** — structural decisions (diameters, walls, fusion) are separate from detail decisions (retention, mounts, vents)

This skill is **rocketry-agnostic** — it knows about build123d and parts and assemblies, not about nose cones and fins. The manifest's feature blocks drive what gets built.

**Core principle:** Read the manifest, trust the manifest. Every geometric decision was made by the DFx skill. `generate-structures` is a faithful executor, not a designer.

## When to Use

- `component_tree.json` exists at `<project_root>/gui/component_tree.json` and needs Pass 1 geometry
- A base STEP file is missing or out of sync with its feature block
- The user asks to regenerate structural geometry

## Inputs

`<project_root>/gui/component_tree.json` — the authoritative parts list (populated by `manufacturing_annotate_tree`, never hand-edited). Specifically the `parts[].features` block for each part. Do not read the `modifications` block — that's `modify-structures`' job.

## Output

- `<project_root>/cadsmith/source/<name>.py` — one parametric script per part (base geometry only)
- `<project_root>/cadsmith/step/<name>.step` — the STEP file exported by each script
- `<project_root>/gui/assets/png/<name>.png` — isometric PNG thumbnail of each part for visual verification

## Steps

### 1. Load the Manifest

```
manifest = read_json("<project_root>/gui/component_tree.json")
```

Verify it has `schema_version`, `parts`, `directories`, and `assemblies`. If anything is missing, stop and ask the `design-for-additive-manufacturing` skill to regenerate the manifest — do not fill in missing fields.

### 2. Create Directories

```
Bash("mkdir -p <project_root>/cadsmith <project_root>/step <project_root>/stl <project_root>/gcode <project_root>/parts <project_root>/png <project_root>/progress")
```

### 3. Generate Each Part's Base Geometry

For each entry in `manifest["parts"]`:

1. **Write the script** with the `Write` tool. Use the script structure below and build only the features in `features` — ignore `modifications` entirely at this stage. For any part with **more than one shape-producing operation** (nose cone with shoulder + ogive, airframe with integrated fins, tube with integral aft shoulder, etc.) follow the iterative per-feature loop in **Build Iteratively — Verify Each Feature** below. Single-feature parts (plain body tube, plain ring) can be written in one shot.
2. **Execute** via `cadsmith_run_script(script_path=<scripts_dir>/<name>.py, out_dir=<step_dir>)`.
3. **Render** via `cadsmith_generate_assets(step_file_path=<step_dir>/<name>.step)` and `Read` the resulting PNG. The PNG is a single isometric view in the part's local print frame (Z=0 is the print-bed face). For a nose cone built shoulder-at-Z=0, the shoulder appears at the bottom and the tip at the top. The rocket-frame orientation is only meaningful in the assembly render.
4. **Verify** via `cadsmith_extract_part` that the bounding box matches `features["length_mm"]` and `features["od_mm"]`.

Do not proceed if a part fails verification. Fix the script and re-run.

### 4. Generate Assembly Layout

After all individual parts are verified, call `cadsmith_assembly(action="generate", project_dir=<project_root>)` to produce `gui/assembly.json`. This computes the spatial layout from the component tree and STEP bounding boxes — the GUI's 3D assembly viewer reads it directly. No STEP assembly file is needed.

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
# This script lives at <project_root>/cadsmith/source/<name>.py
# STEP file goes to <project_root>/cadsmith/step/<name>.step
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
STEP_DIR = PROJECT_ROOT / "cadsmith" / "step"
OUTPUT = STEP_DIR / "<name>.step"

# --- Build ---
with BuildPart() as part:
    # geometry
    pass

# --- Export ---
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
export_step(part.part, str(OUTPUT))
```

Key rules:

- **OUTPUT is a relative path resolved from `__file__`**, not an absolute path hardcoded into the script. The script assumes it lives at `<project_root>/cadsmith/source/<name>.py` and writes to `<project_root>/cadsmith/step/<name>.step`. This keeps the script **portable** — the project directory can be moved, renamed, or checked out on a different machine and the script still works without editing.
- **Never embed an absolute path** like `/Users/someone/rockets/my_rocket/step/...` in a script. That breaks the moment anyone else opens the repo.
- **Parameters are named constants at the top** — match the manifest's feature block exactly.
- **Imports limited to `build123d`, `bd_warehouse`, `pathlib`, `math`, `typing`** — `cadsmith_run_script` runs in isolated mode.
- **No hole patterns, no pocket subtractions, no retention features.** Those are Pass 2.
- **Script filename is always `<name>.py`.** Never add a pass number, suffix, or version tag (`_pass1`, `_pass2`, `_modified`, `_v2`, `_revised`, etc.) to the filename. One canonical file per part — git history provides the audit trail if you need to see what changed.

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

## Build Iteratively — Verify Each Feature

Parts built in one shot and rendered only at the end are the number-one source of orientation and side-of-body bugs. A bbox check cannot tell a shoulder-up nose cone from a shoulder-down one — same extents, same volume. An integrated-fin airframe with the fins sweeping forward looks nearly identical to one with fins sweeping aft in a single iso view. The only reliable check is **eyes on geometry**, and the earlier you look the cheaper the fix: catching a sign flip at feature 1 is a one-line edit; catching it after feature 5 means unwinding four fused operations.

### The loop

Treat each **shape-producing operation** (`extrude`, `revolve`, `add`, `offset`, `loft`, `fillet`, polar-array add) as an independent checkpoint. Profile construction, parameter assignments, and sketch setup are not checkpoints — they're setup for the next checkpoint.

For each feature in a multi-feature part:

1. **Write** the script containing every feature so far plus the new one. Use `Write` for the first feature, `Edit` to append subsequent features — do not rewrite the whole script when appending one feature.
2. **Execute**: `cadsmith_run_script(...)`.
3. **Render + Read**: `cadsmith_generate_assets(...)` then `Read` the PNG.
4. **Verify visually**. The render is a single isometric view in the part-local frame (Z=0 = print-bed face). Check: does the overall shape match the feature block? Is the new feature on the expected face? Is the part inside-out? Is the bore visible? For symmetrical features (fin arrays, bolt circles), count the instances. If anything looks wrong, fix before adding the next feature.
5. **Verify numerically**: `cadsmith_extract_part` and compare the bbox Z extent against what you expect after this feature. If feature 2 was supposed to grow the part by `SHOULDER_LEN_MM` in +Z, the bbox Z max should have increased by exactly that. If it decreased, the feature extruded the wrong way.
6. **Ask the user for feedback on complex features.** See the **User Feedback Checkpoints** section below for which features require a pause and what to show the user. Simple features (plain extrudes, basic cylinders) do not need user confirmation — proceed autonomously.
7. **If wrong (or the user flags an issue), fix before adding the next feature.** Do not stack a new feature onto a broken one — the bug compounds and the diagnosis gets harder with every additional operation.
8. **Only when this feature is visually and numerically correct (and user-approved, if applicable)**, move to the next.

For simple parts this collapses: a plain body tube is one feature, one render — same as before. A nose cone with shoulder + ogive is two renders. An airframe with integrated fins + aft shoulder is three or four. The marginal cost per extra render is small; the cost of unwinding a compounded orientation bug is large.

### Orientation bug decision tree

When a checkpoint render shows the just-added feature on the wrong side or in the wrong place, the fix is almost always one of the following. Diagnose, make a one-line edit, re-run — resist the urge to rewrite the script.

| Symptom | Likely cause | Fix |
|---|---|---|
| Extruded solid extends in −Z when you expected +Z (or vice versa) | `extrude` direction | Flip the sign of `amount`, or toggle `both=True` |
| Revolved body rotates around the wrong axis | `axis` mismatched with sketch plane | Profile in `Plane.XZ` → `revolve(axis=Axis.Z)`. Profile in `Plane.YZ` → `revolve(axis=Axis.Z)` also, but mirrored. Check the sketch plane first. |
| Feature appears at the origin instead of offset along Z | Sketch plane has no Z offset | Use `Plane.XY.offset(z)` or wrap with `Pos(0, 0, z) *` instead of plain `Plane.XY` |
| Feature subtracts from the parent when it should fuse (or vice versa) | Wrong `mode` | Inside `BuildPart`, the default is `Mode.ADD`. Pass `mode=Mode.SUBTRACT` explicitly if needed — but remember Pass 1 never subtracts, so if you're reaching for SUBTRACT here you're probably in the wrong skill. |
| In an assembly, a part sits at the wrong Z | Cursor sign or bbox-extent direction | Check `Pos(0, 0, cursor_z) * part`. Stacking fore-to-aft from Z=0: cursor should grow positive. Stacking aft-to-fore: cursor decreases. Match whichever convention the assembly script declares. |
| Nose cone ends up tip-down | Profile walks from tip down instead of base up | Rewrite the profile to start at the base (`Z = SHOULDER_LEN_MM`) and end at the tip (`Z = SHOULDER_LEN_MM + NOSE_LEN_MM`). See the canonical recipe below. |
| Fins sweep the wrong direction | Leading-edge sweep sign | Fins sweep *aft* by convention — the leading edge's tip is further aft than its root. Flip the X offset applied to the tip chord. |
| Integral aft shoulder appears on the fore end | Extruded from Z=0 instead of Z=length | The second extrude must sketch on `Plane.XY.offset(LENGTH_MM)` and extrude +Z, not sketch on `Plane.XY` and extrude −Z. |
| Integrated fins render correctly but the root fillet is missing / the fillet call raised "Failed creating a fillet" | Fin root chord sits at exactly `OD/2` (tangent to the cylinder, not penetrating) so the fuse produced no intersection edges for `fillet()` to act on | Inset the fin profile's root X from `OD_MM/2` to `OD_MM/2 - 1.0`. The fin now actually penetrates the wall and the broad faces meet the cylinder surface in straight Z-parallel edges that the fillet filter can select. See the *Fin root fillet* recipe in the Common build123d API Patterns section. |
| `fillet()` raises "Failed creating a fillet with radius of X" on fin root edges even though the edges exist | Manifest `fillet_mm` exceeds what OCC can build for this fin geometry — the fillet on one broad face of the fin collides with the fillet on the opposite broad face | Clamp at `min(FIN_THICK/2 * 0.9, 3.0)` before calling `fillet()`. This should be enforced upstream by the `design-for-additive-manufacturing` skill when the manifest is authored, but Pass 1 clamps defensively and prints a warning. |

The common thread: **the fix is almost always one line**. Read the bbox Z extent before and after the bad feature, identify which of the above categories the bug falls into, edit one line, re-run.

### When the loop is overkill

- **Trivial single-feature parts** — plain tube, plain ring, plain coupler. One feature, one render. No loop needed.
- **Known-good recipes** — if you've already built five nose cones this session with the shoulder + ogive recipe and none needed correction, you can build the sixth in one shot and only iterate if the final render looks off. The loop exists to surface bugs in unfamiliar compositions, not to gate every known-good pattern.

The loop is mandatory when:

- A part has ≥2 shape-producing ops and you haven't rendered this exact composition in the current session.
- A previous one-shot render was wrong and you're rebuilding the part — iterate the rebuild to catch where the bug entered.
- The manifest introduces a new feature type or a feature variant (e.g., first time seeing `forward_stop_lip` on a given body).

## User Feedback Checkpoints

CAD generation is **interactive**. After rendering complex features, pause and ask the user whether the geometry looks correct before moving on. This catches design-intent mismatches early — a fillet radius that's technically valid but visually wrong, fins that sweep the right direction but look too aggressive, a shoulder that's geometrically correct but shorter than the user expected.

### When to pause for feedback

Pause after rendering any of the following feature types:

| Feature | Why it needs user eyes |
|---|---|
| **Fillets** (fin root, edge) | Radius trade-offs are subjective; OCC clamping may produce a smaller fillet than the user expected |
| **Lofts and revolves** (nose cones, transitions, boattails) | Profile shape is hard to verify numerically — the user needs to see if the curve "looks right" |
| **Polar arrays** (integrated fins, bolt circles) | Count and angular placement are easy to get right numerically but wrong visually (e.g., fins clocking) |
| **Fused geometry** (fins into body, shoulders into tubes) | The merge seam, wall intersection, and overall proportions need a human sanity check |
| **Full assembly composition** | Cross-part alignment, gaps, and proportions — always pause here |

### When NOT to pause

Do not pause for simple, unambiguous features that are fully determined by the manifest:

- Plain hollow cylinders (body tubes, couplers, motor mounts)
- Simple solid extrudes (shoulders, stop lips)
- Parameter-only changes (wall thickness, bore diameter)

These are verified autonomously via render + extract. Only pause if something looks wrong.

### What to show the user

When pausing for feedback, present:

1. **The render** — show the PNG path so the user can view it, or include the ASCII storyboard inline for quick feedback
2. **A brief description** of what was just added — e.g., "Added 3-fin polar array with 2.5 mm root fillets to the lower airframe"
3. **A specific question** — not just "does this look good?" but targeted:
   - For fillets: "The root fillet was clamped to 2.5 mm (manifest requested 3.0 mm). Does this radius look acceptable, or would you like to adjust?"
   - For nose cones: "Here's the tangent ogive profile. Does the curve shape match what you had in mind?"
   - For assemblies: "Here's the full stack. Do the proportions and joint alignments look right?"
4. **Wait for a response** before proceeding to the next feature or part.

### Handling user feedback

- **"Looks good" / approval** — proceed to the next feature.
- **"Change X"** — update the script (or the manifest if it's a design-level change), re-run, re-render, and ask again.
- **"I'm not sure"** — offer to render from additional angles (`cadsmith_generate_assets` with `format="ascii"` and different `angle_deg` values) or provide dimensional details from `cadsmith_extract_part`.

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
OUTPUT = PROJECT_ROOT / "step" / "nose_cone.step"

# --- Tangent ogive profile ---
BASE_R_MM = BASE_OD_MM / 2
rho = (BASE_R_MM**2 + NOSE_LEN_MM**2) / (2 * BASE_R_MM)

def outer_r(z_from_base: float) -> float:
    """Radius at z above the base. r(0)=R, r(L)=0.
    IMPORTANT: the argument inside sqrt is ``rho**2 - z**2``, NOT
    ``rho**2 - (L - z)**2`` — the latter mirrors the profile and
    produces a bowtie shape.
    """
    return max(
        math.sqrt(max(rho**2 - z_from_base**2, 0.0)) + BASE_R_MM - rho,
        0.0,
    )

# Polyline profile: base centre → base edge → curve to tip → close.
# 40 samples avoids Spline closure issues while looking smooth.
N_SAMPLES = 40
profile = [(0.0, SHOULDER_LEN_MM), (BASE_R_MM, SHOULDER_LEN_MM)]
for i in range(1, N_SAMPLES + 1):
    z_from_base = i * NOSE_LEN_MM / N_SAMPLES
    profile.append((outer_r(z_from_base), SHOULDER_LEN_MM + z_from_base))
profile[-1] = (0.0, SHOULDER_LEN_MM + NOSE_LEN_MM)  # force tip to axis

with BuildPart() as nose_cone:
    # 1. Solid shoulder (print-bed face at Z=0)
    with BuildSketch(Plane.XY):
        Circle(SHOULDER_OD_MM / 2)
    extrude(amount=SHOULDER_LEN_MM)
    # 2. Ogive revolved above shoulder
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

### Nose cone profile functions by shape type

OpenRocket supports six nose cone shapes: **ogive** (default), **conical**, **ellipsoid**, **parabolic**, **power**, and **haack**. The manifest carries the shape name in `features.shape` (e.g. `"shape": "haack"`). Everything in the canonical recipe above stays the same — shoulder, profile walk, revolve, export — except the `outer_r(z_from_base)` function. Swap it according to the table below.

All formulas below use:
- `z` = `z_from_base` = distance above the cone base, measured from Z=SHOULDER_LEN_MM
- `L` = `NOSE_LEN_MM` = ogive/cone length from base to tip
- `R` = `BASE_R_MM` = `BASE_OD_MM / 2` = base radius

All formulas use z from base (`x = L - z` converts to the standard tip-origin convention). At z=0 every formula returns R; at z=L every formula returns 0. Read `SHAPE` from `features.get("shape", "ogive")` and `SHAPE_PARAM` from `features.get("shape_parameter")`.

| Shape      | `outer_r(z)` (z from base)                           | Parameter        | Default |
|------------|-------------------------------------------------------|------------------|---------|
| conical    | `R * (L - z) / L`                                     | none             | —       |
| ogive      | `sqrt(rho² - z²) + R - rho`  where  `rho=(R²+L²)/(2R)` | none          | —       |
| ellipsoid  | `R * sqrt(L² - z²) / L`                               | none             | —       |
| parabolic  | `R * (2u - K'u²) / (2 - K')` where `u = (L-z)/L`     | K' ∈ [0, 1]     | 1.0     |
| power      | `R * ((L-z) / L)^n`                                   | n ∈ [0, 1]      | 0.5     |
| haack      | `R * sqrt((θ - sin(2θ)/2 + C·sin³θ) / π)` where `θ = arccos(1 - 2(L-z)/L)` | C (0=VK, 1/3=LV)| 0.0 |

For parabolic/power/haack, if `SHAPE_PARAM` is None use the default above. Visual check: conical → straight edges, ellipsoid → half-ellipse, parabolic → gentler than ogive, power(n<1) → blunt/concave, haack → similar to ogive (minimum-drag).

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

### Fin root fillet (integrated fins only)

After a fin has been polar-arrayed and fused into a cylindrical body, the root fillet is applied to the straight edges where each fin's two broad faces meet the cylinder's OD. Two prerequisites:

1. **The fin must penetrate the wall**, not sit tangent to it. The fin profile's root chord X coordinate is `OD_MM/2 - FIN_ROOT_INSET_MM` with `FIN_ROOT_INSET_MM = 1.0`. A root at exactly `OD_MM/2` is tangent along a single line, the fuse has no volumetric overlap, and the fillet has no edges to act on.
2. **The fillet radius must be geometrically feasible.** OCC refuses any radius approaching the fin half-thickness. Clamp at `min(FIN_THICK/2 * 0.9, 3.0)` before calling `fillet()`. A manifest `fillet_mm` larger than that ceiling should be clamped (and the clamp printed as a warning), not passed through.

Edge selection pattern — inside the `BuildPart() as airframe:` context, after the fin array loop:

```python
if FIN_FILLET_MM > 0:
    body_r = OD_MM / 2
    z_parallel_edges = airframe.edges().filter_by(Axis.Z)
    fin_root_edges = [
        e for e in z_parallel_edges
        if abs(math.sqrt(e.center().X ** 2 + e.center().Y ** 2) - body_r) < 0.5
        and 0.1 < e.center().Z < FIN_ROOT
        and 1.0 < e.length < FIN_ROOT
    ]
    if fin_root_edges:
        # Clamp to the largest value OCC actually accepts for this fin
        max_feasible = min(FIN_THICK / 2 * 0.9, 3.0)
        applied = min(FIN_FILLET_MM, max_feasible)
        if applied < FIN_FILLET_MM:
            print(
                f"[fillet] manifest fillet_mm={FIN_FILLET_MM} exceeds "
                f"geometric limit; applied {applied} mm"
            )
        fillet(fin_root_edges, radius=applied)
```

Filter rationale:

- **`filter_by(Axis.Z)`** — the fin-root edges we want are straight lines parallel to Z (the intersection of the fin's flat broad faces, which contain the Z direction, with the cylinder surface). The base tube's top and bottom edges are circles, not Z-parallel lines, so this excludes them.
- **Radial distance ≈ `body_r`** — the selected edges must lie on the cylinder's outer surface.
- **`0.1 < center.Z < FIN_ROOT`** — keeps the selection to the fin's Z range. Excludes the OCC cylinder seam line artifact (a Z-parallel topological edge OCC inserts on every cylindrical surface where its u-parameter wraps) that gets split by the fin fuse into pieces above and below the fin.
- **`e.length < FIN_ROOT`** — the seam-line fragment that happens to fall within the fin Z range is slightly longer than `FIN_ROOT` because OCC splits the seam slightly past the fin boundary due to tolerance; this length filter excludes it.

The selection intentionally skips the short fore/aft arcs at the root chord endpoints (where the fin's slanted fore and aft faces meet the OD). Including them caps the achievable fillet at ~1.5 mm because those arcs are only 6–13 mm long. Z-parallel-only selection gets us up to ~2–3 mm at the cost of leaving the fore/aft corners sharp — a good trade-off for visible fillets on printed rockets in the typical 64–80 mm body tube range. If you need the full closed loop (continuous fillet all the way around each fin root), extend the selector to include the OD arcs, but expect the max feasible radius to drop.

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

The assembly frame stacks parts along +Z. Each part was built in its own local print frame (`Part Orientation Convention` section above) and most local frames can be stacked directly — body tubes, couplers, rings — because their Z=0 face is already the face that mates with the next part in the stack.

**Nose cones are the exception.** They are built shoulder-at-Z=0 for printing, so their local +Z points from shoulder → tip, which is the **opposite** of the rocket's fore-to-aft direction. Stacked as-is, the tip would be at low assembly-Z and the shoulder at high assembly-Z, and the shoulder would be pressed against the wrong face of the upper airframe. Rotate the nose cone 180° about X before inserting it into the stack so its shoulder sits at the high-Z end of its local range and mates correctly with the upper airframe's fore face (local Z=0).

If any other part type turns out to have this kind of local-vs-assembly mismatch in the future, handle it the same way — rotate at import time, before the cursor-z stacking loop runs.

```python
from build123d import import_step, Compound, Axis
from pathlib import Path

# Resolve paths relative to this script's location (same pattern as per-part scripts)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CAD_DIR = PROJECT_ROOT / "step"

# Import and re-orient each part into the assembly frame.
# Nose cones are built shoulder-down for printing; flip 180° about X so
# the shoulder ends up at the high-Z end of the nose cone's local range,
# where it will mate with the fore face of the upper airframe.
```

**Note:** STEP assembly files (`full_assembly.step`) are no longer generated. The assembly layout is handled by `cadsmith_assembly(action="generate")` which produces `gui/assembly.json` for the 3D viewer.

## Feature Recipe Reference

The DFAM manifest uses named feature types. Below are the Pass-1 compositions of the generic build123d patterns above. Feature types that involve holes or pockets belong to `modify-structures` — they are NOT listed here.

| Feature type | Composition |
|---|---|
| base cylinder (`length_mm`, `od_mm`, `id_mm`) | Hollow cylinder pattern. |
| `local_wall_thickening` | Hollow cylinder with a secondary inner `Circle` at `bore_mm / 2` subtracted only between `[region_start_mm, region_end_mm]` along Z. Two extrusions: one for the full outer shell, one for the locally thickened inner wall. |
| `integrated_fins` | Build a single fin as a `Polyline` sketch in the XZ plane. **Root chord sits slightly INSIDE the cylinder wall** — use X = `od_mm/2 - 1.0` mm, not exactly `od_mm/2`. A root at exactly `od_mm/2` is tangent to the cylinder along a single line, producing zero volumetric overlap when fused, and the root fillet has no edges to act on. With the 1 mm inset the fin actually penetrates the wall and the fuse creates real intersection edges. Tip chord is at X = `od_mm/2 + span`, sweep applied at the leading edge. Extrude ±thickness/2 in Y. Polar-array `count` copies around Z via `add(fin_shape.rotate(Axis.Z, i * 360/count))`. **Fillet**: after the polar-array, select the Z-parallel straight edges that lie on the cylinder OD within the fin chord Z range (see snippet below) and pass them to `fillet()`. Clamp `fillet_mm` at `min(fin_thickness_mm/2 * 0.9, 3.0)` — larger values fail OCC. If `fillet_mm` is 0 or not present, skip the fillet. |
| `integral_aft_shoulder` | At Z = parent `length_mm`, extrude a second hollow cylinder with OD = `od_mm` and ID = parent `id_mm`, length = `length_mm`. The `assembly_clearance_mm` field defaults to 0 (interference fit); use the shoulder OD from the manifest verbatim rather than re-applying clearance yourself. |
| `forward_stop_lip` | At the fore end of the motor bore (Z = region_start_mm), extrude a small annulus inward (OD = bore radius, ID = stop ID) by `thickness_mm` in −Z. Fuse with parent. |

If a feature type isn't in this table, query the `cad_examples` reference collection (see below) before improvising. If the feature is hole-shaped or pocket-shaped, it belongs in `modify-structures`, not here.

## Check the Reference Collection

For feature types or build123d API patterns not covered above, query `rag_reference(action="search", collection="cad_examples", query=f"build123d {question}", n_results=3)`. Fall back to the patterns above if no results; proceed silently on errors.

## Verification Workflow

After each successful `cadsmith_run_script` call:

1. **`cadsmith_generate_assets(step_file_path, out_path=<images_dir>/<name>.png)`** — writes the PNG into `png/`
2. **`Read(file_path=<png_path>)`** — visually inspect:
   - Does the overall shape match the feature block's intent?
   - Are any expected geometric features visible and correctly placed?
   - Is the part inside-out (walls appearing solid where there should be a bore)?
   - Is any dimension obviously wrong?
3. **`cadsmith_extract_part(step_file_path)`** — compare the bounding box Z extent to `features["length_mm"]` and the max XY extent to `features["od_mm"]`. Mismatches > 1 mm indicate a script bug.
4. **Pause for user feedback** if this feature is in the feedback checkpoint list (see **User Feedback Checkpoints** above). Show the render, describe what was built, and ask a targeted question. Wait for user approval before continuing.
5. **If any check fails (or the user requests changes), fix the script and re-run.** Do not accept broken geometry, do not defer verification to "I'll check all of them at the end".

After the full assembly is generated, **always pause for user feedback** on the assembly render — this is mandatory regardless of feature complexity. Cross-part issues (visible gaps at joints, off-axis fins, shoulder mismatches) are only visible here and the user's approval of the full stack is required before handoff.

## Red Flags — Stop and Fix

- **A nose cone (or any revolved part with a clear "wide end" and "narrow end") is built tip-down.** PrusaSlicer will fail with `"There is an object with no extrusions in the first layer"`. The fix is always: rebuild with the wide face at Z=0 (see the tangent ogive recipe above). This is the single most common slice failure for fresh designs — verify orientation BEFORE handing off to the prusaslicer subagent.
- A script imports anything outside `build123d`, `bd_warehouse`, `pathlib`, `math`, `typing`
- A script has `Hole(...)` or `extrude(..., mode=Mode.SUBTRACT)` subtracting a hole pattern — that's a Pass 2 operation, belongs in `modify-structures`
- A script emits a STEP file whose bounding box doesn't match the manifest's feature block
- A part is generated that isn't in the manifest
- A part in the manifest is skipped without a reported failure
- Assembly viewer shows a visible gap between sections — check `integral_aft_shoulder.od_mm` matches the mating tube's `id_mm`
- `cadsmith_extract_part` volume is zero or NaN — degenerate geometry, script has a topology bug
- A fin is not fused into the parent body — check the feature block specifies `integrated_fins` and the script uses `Mode.ADD` rather than exporting fins as a separate part
- A part has its bed face (lowest Z) as a single point, an edge, or a small ring. PrusaSlicer needs a planar face with significant area at Z=0. If the lowest Z is sub-millimeter in cross-section, the orientation is wrong even if the rest of the geometry looks fine in the render.

## Handoff to Pass 2

Once every individual part and the full assembly are verified:

- If **any part in the manifest has a non-empty `modifications` list**, hand off to `modify-structures` to apply them.
- If **every part's `modifications` list is empty**, Pass 1 was the whole job — hand back to the cadsmith subagent for reporting.

Do not run `modify-structures` twice for the same manifest — a successful modify pass overwrites the base STEP. If the user wants to add a modification after the fact, they can edit the manifest and run both passes again.

## Quick Reference

```
# the Pass 1 loop
for part in manifest["parts"]:
    for feature in part["features"]:
        write_or_append_script(part, feature)
        cadsmith_run_script(script_path, out_dir)
        cadsmith_generate_assets(step_file_path, out_path=images_dir/<name>.png)
        Read(png_path)
        cadsmith_extract_part(step_file_path)
        if is_complex_feature(feature):  # fillets, lofts, revolves, arrays, fuses
            ask_user("Does this look right? <describe what was added>")
            wait_for_response()
        if check_failed or user_requested_change: fix_and_retry()

# then the assembly (always pause for feedback)
for asm in manifest["assemblies"]:
    write_assembly_script(asm)
    cadsmith_run_script(...)
    cadsmith_generate_assets(...) → Read → verify cross-part alignment
    ask_user("Assembly looks like <description>. Do the proportions and joints look right?")
    wait_for_response()

# handoff
if any(part.modifications for part in manifest["parts"]):
    load modify-structures and run Pass 2
else:
    report back to the orchestrator
```
