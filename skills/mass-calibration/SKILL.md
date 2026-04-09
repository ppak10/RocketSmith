---
name: mass-calibration
description: Use after slicing printed parts to feed measured filament weights back into the OpenRocket design as mass overrides, then re-verify stability
---

# Mass Calibration

## Overview

OpenRocket assigns every component a mass based on its configured material (cardboard by default, typically ~680 kg/m³). Real printed parts are made of PLA or PETG and use variable wall/infill settings — their actual mass can differ from OpenRocket's estimate by 2–4×. A design that simulated stable with default material assumptions may be unstable once built.

Mass calibration closes the loop: slice each printed part, read the filament weight from the slicer, apply it back to the matching OpenRocket component as a mass override, and re-run the simulation to confirm stability still holds.

**Core principle:** A design is not flight-ready until simulation has been re-verified against the *real* printed part weights, not the material defaults.

## When to Use

- `build123d_script` has produced STEP files AND `prusaslicer_slice` has produced gcode for at least one printed part
- Before committing to a final build
- After changing any print setting (infill, wall count, material) that would change part mass
- When the user asks "will it still fly stable once printed?"

## Preconditions

1. The design has already passed an initial stability check in the 1.0–1.5 cal range with default masses. If not, run `rocketsmith:stability-analysis` first — calibrating on an already-unstable design just obscures the root cause.
2. Each printed part has a sliced `.gcode` file with a `filament_used_g` reading. If any part is missing, slice it first.

## Steps

### 1. Collect Measured Weights

For every part that will be printed, read the `filament_used_g` field from the corresponding `prusaslicer_slice` result. Build a mapping:

```
{
  "Nose Cone":       18.4,   # grams
  "Upper Airframe":  62.1,
  "Lower Airframe":  89.7,   # includes integrated fins
  "Motor Mount":     14.2,
  "Centering Ring":  4.1,    # ×2 → 8.2 total
  ...
}
```

If a part is printed as multiple copies (e.g. centering rings ×2), sum them before applying the override — OpenRocket only has one component per instance.

### 2. Apply Each Override

For each measured weight, call `openrocket_component` with **action="update"** and `override_mass_kg` in **kilograms** (divide grams by 1000):

```
openrocket_component(
    action="update",
    rocket_file_path=<path>,
    component_name="Upper Airframe",
    override_mass_kg=0.0621,   # 62.1 g → 0.0621 kg
)
```

Setting `override_mass_kg` implicitly enables the override flag. You do not need to pass `override_mass_enabled=True` separately.

**Units gotcha:** If you pass grams (62.1) instead of kilograms (0.0621), OpenRocket will treat the component as weighing 62 kg and simulated apogee will collapse to near zero. Always divide by 1000.

### 3. Re-Run the Simulation

```
openrocket_simulate(rocket_file_path=<path>)
```

Note the new `min_stability_cal`, `max_altitude_m`, and `max_velocity_ms`.

### 4. Compare Before and After

| Metric | Baseline | Calibrated | Action |
|--------|---------|-----------|--------|
| `min_stability_cal` in [1.0, 1.5] | ✓ | ✓ | Done — design is flight-ready |
| Fell below 1.0 | ✓ | ✗ | Move CG forward: add nose weight, or shorten/lighten aft parts |
| Climbed above 1.5 | ✓ | ✗ | Reduce nose weight, or increase fin area modestly |
| Apogee dropped > 25% | — | — | Consider stepping up one motor class |

Apply fixes one at a time. After each fix, re-run `openrocket_simulate` (the overrides are already in place — you don't need to re-apply them).

### 5. Confirm and Record

Once stability is back in range, report the final mass budget to the user:

```
Final calibrated mass budget:
  Nose Cone:        18.4 g  (was 12.1 g default)
  Upper Airframe:   62.1 g  (was 38.4 g)
  Lower Airframe:   89.7 g  (was 54.2 g)
  Motor Mount:      14.2 g  (was  8.9 g)
  Centering Rings:   8.2 g  (was  3.1 g, ×2)
  Total printed:   192.6 g
  Stability:        1.23 cal (was 1.41 cal baseline)
```

## Red Flags — Stop and Fix

- A filament weight was passed in grams instead of kilograms (apogee will drop to near zero — obvious in the simulation output)
- Only some printed parts had overrides applied, not all of them — mixing real and default masses skews CG
- Override was applied to a component that will not actually be printed (e.g. a parachute or cardboard component that stays as-default)
- Stability fell below 1.0 after calibration and the fix was to add override_mass_kg on the nose cone rather than adding a real nose weight mass component — the override pins the nose cone mass, it does not add ballast that moves CG forward in a physically meaningful way. Add a `mass` component with the required ballast and a realistic position.
- The override was disabled with `override_mass_enabled=False` and the file was saved — OpenRocket does not persist the stored value when the override is disabled, so the calibration is lost on the next reload. Either keep overrides enabled, or track measured weights externally (in a project note) so they can be re-applied.

## Quick Reference

```
# grams → kilograms
override_mass_kg = filament_used_g / 1000

# re-sim after every override pass
openrocket_simulate(rocket_file_path=<path>)

# check stability stayed in [1.0, 1.5]
assert 1.0 <= min_stability_cal <= 1.5
```
