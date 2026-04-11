---
name: print-preparation
description: Use when slicing rocket parts for FDM printing, or when choosing print orientation and settings for a specific part
---

# Print Preparation

## Overview

Slicing converts STEP files into printer-ready gcode. Settings vary significantly by part — structural components need full infill and strong layer orientation; fairings and nose cones can use partial infill to save mass.

**Core principle:** Mass is the enemy of apogee. Use the minimum infill and wall count that still meets structural requirements for each part.

## When to Use

- STEP files are generated and verified
- User asks to prepare parts for printing
- Choosing orientation, infill, or material for a specific part

## Steps

### 1. Confirm STEP Files Exist

Verify all parts listed in `<project_dir>/component_tree.json` have corresponding STEP files in `<project_dir>/parts/step/`. If any are missing, use `rocketsmith:generate-structures` (Pass 1) and `rocketsmith:modify-structures` (Pass 2) to produce them from the manifest.

### 2. Choose Settings Per Part

| Part | Orientation | Infill | Perimeters | Notes |
|------|------------|--------|-----------|-------|
| Body tubes (all sections) | Vertical (tube axis = Z) | 40–60% | 4–6 | Layer lines along stress axis |
| Motor mount | Vertical | 60–80% | 4–6 | High thermal load near motor |
| Centering rings | Flat (ring in XY) | 100% | 4 | Print ×2 |
| Nose cone | Tip-up or tip-down | 20–40% | 3–4 | No supports if shoulder at base |
| Lower airframe with fins | Vertical | 40–60% | 4–6 | Fins will have cross-grain layers — acceptable at model scale |

### 2.5. Check the Reference Collection for Print Gotchas

For parts with unusual geometry (thin walls, overhanging fin tips, large bridges), query `rag_reference(action="search", collection="print_gotchas", query=f"{part_name} {distinctive_feature}", n_results=3)`. Fall back to the heuristic table above if no results; proceed silently on errors. Skip for simple parts that match the table cleanly.

### 3. Slice Each Part

```
prusaslicer_slice(model_file_path=<step_path>)
```

If `out_path` is omitted, gcode saves alongside the STEP file with `.gcode` extension.

Slice parts one at a time. Batch slicing with different settings per part isn't supported in a single call.

### 4. Verify Output

After each slice, confirm the gcode file was created:
```
ls <project_dir>/parts/*.gcode
```

Report the file path and estimated print time/mass to the user if PrusaSlicer returns that information.

### 5. Calibrate the Design Against Real Weights

Once every part is sliced, the `filament_used_g` values are the *real* printed weights. Feed them back into the OpenRocket design as mass overrides and re-run the simulation to confirm stability still holds — printed parts routinely weigh 2–4× OpenRocket's material defaults. Use the `rocketsmith:mass-calibration` skill to close this loop. Do not treat the design as flight-ready until this step passes.

## Material Guidance

**PETG** (recommended for all structural parts):
- Density at 100% infill: ~1250 kg/m³
- Better UV and temperature resistance than PLA
- Print temp: 230–245 °C nozzle, 70–85 °C bed
- Slightly flexible — good impact resilience on landing

**PLA** (acceptable for nose cones and non-structural fairings):
- Lighter than PETG at same infill
- Poor UV/heat resistance — not suitable for motor bay or fins
- Easier to print cleanly for complex nose cone geometries

## Mass Penalty Reminder

Thick PETG walls carry 3–4× the mass of equivalent fiberglass parts. If the simulated apogee is marginal, consider:
- Reducing wall thickness on the nose cone (it carries no structural load)
- Using 20% gyroid infill on the nose cone instead of rectilinear
- Checking whether the motor class should step up one level

## Red Flags — Stop and Check

- Slicing a body tube flat (horizontal) — layer lines will be perpendicular to hoop stress, dramatically reducing burst strength
- 100% infill on a nose cone — unnecessary mass, costs apogee
- Infill below 40% on motor mount or centering rings — insufficient strength near the motor
- Missing centering ring in the parts list — it must be printed ×2 (fore and aft of motor mount)
