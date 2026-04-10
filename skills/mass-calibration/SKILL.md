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

- `cadsmith_script` has produced STEP files AND `prusaslicer_slice` has produced gcode for at least one printed part
- Before committing to a final build
- After changing any print setting (infill, wall count, material) that would change part mass
- When the user asks "will it still fly stable once printed?"

## Preconditions

1. The design has already passed an initial stability check in the 1.0–1.5 cal range with default masses. If not, run `rocketsmith:stability-analysis` first — calibrating on an already-unstable design just obscures the root cause.
2. `<project_dir>/parts_manifest.json` exists (produced earlier by the `design-for-additive-manufacturing` skill or a sibling DFx skill). This is the authoritative mapping from printed parts back to OR components.
3. Each printed part listed in the manifest has a sliced `.gcode` file with a `filament_used_g` reading. If any part is missing, slice it first.

## Steps

### 1. Load the Parts Manifest

```
manifest = read_json("<project_dir>/parts_manifest.json")
```

The two sections you care about are:

- **`parts`** — each entry has a `name`, a `gcode_path`, and a `derived_from` list of the OR components the part was assembled from (post-fusion)
- **`component_to_part_map`** — the inverse lookup: for every OR component in the `.ork` file, it tells you which printed part absorbed it, or that the component was `"skipped"` or `"purchased"` and does not need calibration

If the manifest is missing, stop and ask the cadsmith subagent to regenerate it. Do not guess the mapping from filenames.

### 2. Collect Measured Weights

For each entry in `manifest["parts"]`, read the `filament_used_g` value from the gcode (returned by `prusaslicer_slice`) and associate it with the `derived_from` list:

```
{
  "nose_cone":       {"grams": 18.4, "derived_from": ["NoseCone"]},
  "upper_airframe":  {"grams": 62.1, "derived_from": ["BodyTube:Upper", "TubeCoupler:UpperAft"]},
  "lower_airframe":  {"grams": 89.7, "derived_from": ["BodyTube:Lower", "TrapezoidFinSet",
                                                       "InnerTube:MotorMount",
                                                       "CenteringRing:Fore", "CenteringRing:Aft"]}
}
```

If a part is printed as multiple copies (centering rings printed ×2, booster fins printed ×3), the manifest's `features` block records the quantity — sum the weights before applying.

### 3. Apply the Overrides — Fused Parts Need Special Handling

Because the DFAM skill fuses components aggressively, one printed part often corresponds to **multiple OR components**. The override strategy depends on how many components a part was derived from.

#### Case A: One printed part → one OR component (simple)

```
openrocket_component(
    action="update",
    rocket_file_path=<path>,
    component_name="Nose Cone",
    override_mass_kg=0.0184,   # 18.4 g → 0.0184 kg
)
```

#### Case B: One printed part → multiple OR components (fused)

When `derived_from` has multiple entries, distribute the printed weight proportionally across all fused components to preserve CG distribution:

```
# Read each component's OR-default mass via openrocket_component(action="read")
defaults = {"BodyTube:Lower": 0.0541, "TrapezoidFinSet": 0.0082, "InnerTube:MotorMount": 0.0089}
total_default = sum(defaults.values())
measured = 0.0897   # printed weight in kg (89.7 g / 1000)

for component, default_mass in defaults.items():
    openrocket_component(
        action="update",
        rocket_file_path=<path>,
        component_name=component,
        override_mass_kg=(default_mass / total_default) * measured,
    )
```

For small LPR parts where CG shift is negligible, you can instead apply the full weight to the primary component and zero the rest — but **default to proportional distribution for mid-power and above.**

#### Case C: OR component → skipped or purchased

Components marked `"skipped"` or `"purchased"` in `component_to_part_map` are not printed. For **skipped** components (parachutes, ballast), leave their OR-default mass alone — it reflects the actual physical item. For **purchased** components (COTS body tubes, motor tubes in hybrid builds), apply the vendor's published mass as an override if available, otherwise leave the OR-default in place and flag it.

**Units gotcha (always):** If you pass grams (62.1) instead of kilograms (0.0621), OpenRocket will treat the component as weighing 62 kg and simulated apogee will collapse to near zero. Always divide by 1000.

### 4. Re-Run the Simulation

```
openrocket_simulate(rocket_file_path=<path>)
```

Note the new `min_stability_cal`, `max_altitude_m`, and `max_velocity_ms`.

### 5. Compare Before and After

| Metric | Baseline | Calibrated | Action |
|--------|---------|-----------|--------|
| `min_stability_cal` in [1.0, 1.5] | ✓ | ✓ | Done — design is flight-ready |
| Fell below 1.0 | ✓ | ✗ | Move CG forward: add nose weight, or shorten/lighten aft parts |
| Climbed above 1.5 | ✓ | ✗ | Reduce nose weight, or increase fin area modestly |
| Apogee dropped > 25% | — | — | Consider stepping up one motor class |

Apply fixes one at a time. After each fix, re-run `openrocket_simulate` (the overrides are already in place — you don't need to re-apply them).

### 6. Confirm and Record

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
- The parts manifest was ignored and the mapping was guessed from filenames — always use `component_to_part_map`, never improvise
- A fused part's mass was pinned entirely to a single OR component when `derived_from` has multiple entries — use Option B1 (proportional distribution) for mid-power and above, or Option B2 (pin primary, zero secondaries) only for small LPR parts
- Only some parts in the manifest had overrides applied — every printed part in the manifest must be covered, otherwise you're mixing real and default masses and skewing CG
- An override was applied to a component whose `component_to_part_map` entry is `"skipped"` or `"purchased"` — these should not receive mass overrides from printed-part weights
- Stability fell below 1.0 after calibration and the fix was to add `override_mass_kg` on the nose cone rather than adding a real nose-weight `mass` component — the override pins the nose cone mass, it does not add ballast that moves CG forward. Add a `mass` component with the required ballast and a realistic position.
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
