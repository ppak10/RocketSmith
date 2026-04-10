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

1. **Write the script** with the `Write` tool. Use the script structure below and build only the features in `features` — ignore `modifications` entirely at this stage. For any part with **more than one shape-producing operation** (nose cone with shoulder + ogive, airframe with integrated fins, tube with integral aft shoulder, etc.) follow the iterative per-feature loop in **Build Iteratively — Verify Each Feature** below. Single-feature parts (plain body tube, plain ring) can be written in one shot.
2. **Execute** via `build123d_script(script_path=<scripts_dir>/<name>.py, out_dir=<step_dir>)`.
3. **Render** via `build123d_render(step_file_path=<step_dir>/<name>.step)` and `Read` the resulting PNG. The tool auto-routes renders of STEPs in `CAD/` to the sibling `visualizations/` directory — you don't need to pass `out_path` for standard project layouts. For non-standard locations, pass `out_path=<visualizations_dir>/<name>.png` explicitly. The PNG has **three panels — side (eye at −X, low Z on the left → high Z on the right), end (eye at +Z, showing the high-Z face), isometric 45°** — check all three, not just the iso view. Note that panel labels describe the **part-local frame**, not the rocket-logical frame — for a nose cone built per convention, low Z is the shoulder (rocket-aft) and high Z is the tip (rocket-fore). The rocket-frame view only exists in the assembly render.
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

## Build Iteratively — Verify Each Feature

Parts built in one shot and rendered only at the end are the number-one source of orientation and side-of-body bugs. A bbox check cannot tell a shoulder-up nose cone from a shoulder-down one — same extents, same volume. An integrated-fin airframe with the fins sweeping forward looks nearly identical to one with fins sweeping aft in a single iso view. The only reliable check is **eyes on geometry**, and the earlier you look the cheaper the fix: catching a sign flip at feature 1 is a one-line edit; catching it after feature 5 means unwinding four fused operations.

### The loop

Treat each **shape-producing operation** (`extrude`, `revolve`, `add`, `offset`, `loft`, `fillet`, polar-array add) as an independent checkpoint. Profile construction, parameter assignments, and sketch setup are not checkpoints — they're setup for the next checkpoint.

For each feature in a multi-feature part:

1. **Write** the script containing every feature so far plus the new one. Use `Write` for the first feature, `Edit` to append subsequent features — do not rewrite the whole script when appending one feature.
2. **Execute**: `build123d_script(...)`.
3. **Render + Read**: `build123d_render(...)` then `Read` the PNG.
4. **Verify visually against the three panels**. The render labels describe the **part-local frame** — not the rocket's fore-aft frame. Reason in terms of "Z=0 is the part's local print-bed face" first, then translate to rocket semantics only when composing the assembly.
   - **Side panel** — Z is horizontal, low Z on the left, high Z on the right. Is the new feature in the expected local-Z range? Is it fused to the correct face of the existing geometry? For a body tube built fore-at-Z=0, left = rocket-fore. For a nose cone built shoulder-at-Z=0, left = rocket-aft (shoulder) and right = rocket-fore (tip) — the opposite. "Left = fore" is NOT a universal truth; check the per-part-type orientation table above before interpreting the side view.
   - **End panel** — camera looks down +Z toward −Z, so you see the high-Z face of the part. Symmetry counts (fin count, bolt circle count) and radial placement are obvious here.
   - **Isometric** — 3D sanity check. Is the feature on the expected side of the body? In this render's iso projection, high Z tends to appear toward the bottom-right of the panel (worth internalizing if you debug orientation issues often).
5. **Verify numerically**: `build123d_extract` and compare the bbox Z extent against what you expect after this feature. If feature 2 was supposed to grow the part by `SHOULDER_LEN_MM` in +Z, the bbox Z max should have increased by exactly that. If it decreased, the feature extruded the wrong way.
6. **If wrong, fix before adding the next feature.** Do not stack a new feature onto a broken one — the bug compounds and the diagnosis gets harder with every additional operation.
7. **Only when this feature is visually and numerically correct**, move to the next.

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
CAD_DIR = PROJECT_ROOT / "CAD"

# Import and re-orient each part into the assembly frame.
# Nose cones are built shoulder-down for printing; flip 180° about X so
# the shoulder ends up at the high-Z end of the nose cone's local range,
# where it will mate with the fore face of the upper airframe.
nose_cone = import_step(str(CAD_DIR / "nose_cone.step")).rotate(Axis.X, 180)
upper_airframe = import_step(str(CAD_DIR / "upper_airframe.step"))
lower_airframe = import_step(str(CAD_DIR / "lower_airframe.step"))

parts = [nose_cone, upper_airframe, lower_airframe]

# Stack along +Z in the order given (fore-to-aft in this layout: nose cone
# first, motor last). The nose cone sits at low Z and the motor at high Z
# in the assembly frame — this is "fore-down" in the rocket's own frame,
# which is fine for a visual sanity render. If you want "fore-up" for the
# viewer's benefit, compose as shown and then rotate the whole assembly.
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
| `integrated_fins` | Build a single fin as a `Polyline` sketch in the XZ plane. **Root chord sits slightly INSIDE the cylinder wall** — use X = `od_mm/2 - 1.0` mm, not exactly `od_mm/2`. A root at exactly `od_mm/2` is tangent to the cylinder along a single line, producing zero volumetric overlap when fused, and the root fillet has no edges to act on. With the 1 mm inset the fin actually penetrates the wall and the fuse creates real intersection edges. Tip chord is at X = `od_mm/2 + span`, sweep applied at the leading edge. Extrude ±thickness/2 in Y. Polar-array `count` copies around Z via `add(fin_shape.rotate(Axis.Z, i * 360/count))`. **Fillet**: after the polar-array, select the Z-parallel straight edges that lie on the cylinder OD within the fin chord Z range (see snippet below) and pass them to `fillet()`. Clamp `fillet_mm` at `min(fin_thickness_mm/2 * 0.9, 3.0)` — larger values fail OCC. If `fillet_mm` is 0 or not present, skip the fillet. |
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
