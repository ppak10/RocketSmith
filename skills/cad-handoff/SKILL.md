---
name: cad-handoff
description: Use when translating a confirmed OpenRocket design into build123d parameters for STEP file generation
---

# CAD Handoff

## Overview

The CAD handoff converts confirmed OpenRocket dimensions (metres) into build123d parameters (millimetres) and generates parametric Python scripts for each rocket part. This phase begins only after simulation confirms stability in the 1.0–1.5 cal range.

**Core principle:** Extract every dimension from `openrocket_inspect` output — never guess or estimate a measurement. One wrong number produces unfittable parts.

## When to Use

- Simulation is confirmed stable (1.0–1.5 cal)
- User asks for STEP files, CAD parts, or 3D models
- Transitioning from the OpenRocket phase to build123d

## Steps

### 1. Confirm Stability First

Do not begin CAD until `min_stability_cal` is between 1.0 and 1.5. If not confirmed, use the `rocketsmith:stability-analysis` skill first.

### 2. Run Final Inspect

```
openrocket_inspect(rocket_file_path=<path>)
```

Read every component's dimensions from the output. These are the source of truth.

### 3. Convert Units

All OpenRocket dimensions are in **metres**. All build123d parameters are in **millimetres**.

Multiply every measurement by 1000.

### 4. Map Dimensions

| OpenRocket field | build123d variable | Conversion |
|-----------------|-------------------|------------|
| body tube `outer_diameter_m` | `TUBE_OD` | × 1000 |
| body tube `inner_diameter_m` | `TUBE_ID` | × 1000 |
| body tube `length_m` | `TUBE_LEN` | × 1000 |
| nose cone `length_m` | `NOSE_LEN` | × 1000; base OD = body tube OD |
| nose cone `shape` = ogive | tangent ogive formula | see template |
| fin set `root_chord_m` | `ROOT_CHORD` | × 1000 |
| fin set `tip_chord_m` | `TIP_CHORD` | × 1000 |
| fin set `span_m` | `SPAN` | × 1000, radial from body surface |
| fin set `sweep_m` | `SWEEP` | × 1000, leading edge sweep |
| fin set `thickness_m` | `FIN_THICK` | × 1000 |
| fin set `fin_count` | `FIN_COUNT` | integer |
| motor mount `outer_diameter_m` | `TUBE_OD` | × 1000 |
| motor mount `length_m` | `TUBE_LEN` | × 1000 |

**Derived values (not in OpenRocket output):**
- `TUBE_ID` for motor mount = motor case OD + 0.5 mm clearance
- `RING_OD` for centering ring = body tube ID − 0.2 mm
- `RING_ID` for centering ring = motor tube OD + 0.2 mm
- Coupler OD = parent body tube ID; wall 2–3 mm; length 1.0–1.5× body diameter

### 5. Establish Project Directory

Parts go in `<project_dir>/parts/`. Create the directory before running scripts:

```bash
mkdir -p <project_dir>/parts
```

Each script's `OUTPUT` variable is the absolute path to the STEP file:
```python
OUTPUT = "/absolute/path/to/parts/<name>.step"
```

### 6. Generate Scripts — One Per Part

Write each script with the `Write` tool, then execute it with the `build123d_script` tool:
```
build123d_script(
    script_path="<project_dir>/parts/<script>.py",
    out_dir="<project_dir>/parts/",
)
```

The tool runs the script in an isolated `uv` environment (no host Python required) and returns the paths of any `.step` files written to `out_dir`.

**Required parts** (middle airframe only if 3 body sections):

| Script | Part |
|--------|------|
| `nose_cone.py` | Tangent ogive + shoulder + M4 heat-set holes |
| `upper_airframe.py` | Upper body tube + coupler bore + clearance holes |
| `middle_airframe.py` | *(if 3 sections)* Middle body tube |
| `lower_airframe.py` | Lower body tube + **integrated fins** |
| `motor_mount.py` | Motor tube + forward stop lip |
| `centering_ring.py` | Centering ring + vent holes (print ×2) |

**Rules that must not be broken:**
- Fins are ALWAYS integrated into `lower_airframe.py` — never a separate STEP file
- Every coupler shoulder must have 4× M4 radial heat-set holes at 90° spacing

### 7. Verify Each Part

After each script runs:
1. `build123d_render(step_file_path=<path>)` — get `png_path`
2. `Read(file_path=<png_path>)` — inspect all three panels
   - Side: correct length and diameter?
   - Aft: correct fin count and spacing?
   - Isometric: not inside-out or degenerate?
3. `build123d_extract(step_file_path=<path>)` — verify bounding box matches expected dimensions

Do not proceed to the next part if the current one looks wrong.

## Red Flags — Stop and Fix

- Any dimension estimated rather than read from `openrocket_inspect`
- `build123d_render` shows inside-out geometry (wall appears as solid, bore missing)
- Bounding box from `build123d_extract` doesn't match expected dimensions
- A `parts/fins.step` file exists — fins must be integrated into lower airframe

## Coordinate Convention

Z = 0 at fore face (nose tip direction), Z increases aft. This matches OpenRocket's axis.
