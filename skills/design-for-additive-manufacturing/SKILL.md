---
name: design-for-additive-manufacturing
description: Use when translating an OpenRocket logical design into a physical parts manifest for FDM/SLA 3D printing. Decides per-component fate (print, fuse, purchase, skip), applies AM-specific geometry patterns, and emits parts_manifest.json.
---

# Design for Additive Manufacturing (DFAM)

## Overview

OpenRocket describes a rocket as a **logical design** — a tree of abstract components (nose cone, body tubes, inner tubes, couplers, fin sets, centering rings) that captures aerodynamic and mass properties. That description is manufacturing-agnostic.

The physical parts list — what actually gets produced and assembled — is a function of the chosen manufacturing method applied to that logical design. This skill handles the **additive manufacturing** case: converting OpenRocket components into a printable parts manifest that the `generate-structures` skill and `build123d` subagent use as their authoritative source.

**Core principle:** OpenRocket components don't map 1:1 to printed parts. A centering ring in OR becomes "localised wall thickening" in AM. A tube coupler in OR becomes "integral shoulder on the forward section" in AM. A fin set in OR becomes "fused geometry on the lower airframe" in AM. The translation is the whole point of this skill.

## When to Use

- The CAD phase is starting and the chosen manufacturing method is **additive** (FDM or SLA)
- A `parts_manifest.json` is missing or stale for the current `.ork` file
- The user changed the design and the existing manifest needs to be regenerated
- A user explicitly asks "what parts do I actually print for this rocket?"

## Inputs

1. The component tree from `openrocket_cad_handoff(rocket_file_path=<path>)` — authoritative mm-scaled geometry and the derived motor mount / body tube ID
2. The **default policy** (passed by the orchestrator): `"additive"` means print everything that can be printed and fuse aggressively; `"hybrid"` means print the nose cone and fin can but purchase body tubes and motor mount; `"traditional"` falls back to a separate skill not yet implemented
3. Optional user overrides on specific fusion decisions

## Output

A single JSON file written to `<project_dir>/parts_manifest.json` by the **`manufacturing_manifest` MCP tool**. The schema is enforced by Pydantic models at tool-call time, so malformed manifests are rejected before they reach disk. This file is the authoritative handoff to `generate-structures` and `build123d` — they consume it and produce STEP files from it. The mass-calibration skill also reads it to map `filament_used_g` back to OR components via `component_to_part_map`.

## Steps

### 1. Decide the Fusion Overrides (If Any)

For most designs, the tool's defaults are correct and you can call it with no overrides. Review the design to identify whether any of the following ask-user conditions apply:

**Motor mount fate** — default is `fuse` (as local wall thickening).
- **Ask user to confirm `separate`** if: motor total impulse ≥ 320 Ns (H-class+) **AND** the design has a payload bay or dual-deploy configuration suggesting the user might want motor swap-outs between flights.

**Coupler fate** — default is `fuse` (as integral aft shoulder).
- **Ask user to confirm `separate`** if: the design has a dedicated payload bay, dual-deploy, or any suggestion that the user plans to disassemble between flights.

**Retention mechanism** — default is `m4_heat_set` for body diameters ≥ 38 mm, `friction_fit` below.
- **Ask the user** when the design is borderline (38–54 mm) to pick between heat-set and friction fit.

If the user has answered any of these, collect the answers into a `fusion_overrides` dict. Otherwise skip to step 2 and pass nothing.

### 2. Check the Reference Collection for Edge Cases

Before generating the manifest for non-standard designs (transitions, boattails, multi-stage, cluster mounts, unusual nose cone shapes), query the reference collection:

```
rag_reference(
    action="search",
    collection="cad_examples",
    query=f"DFAM {distinctive_feature} {body_diameter_class}",
    n_results=3,
)
```

Hits may surface fusion decisions other users have made for similar designs. **If no results**, fall through to the defaults. **If the search errors** (collection not indexed), proceed silently.

### 3. Generate the Manifest

Call the `manufacturing_manifest` MCP tool with `action="generate"`:

```
manufacturing_manifest(
    action="generate",
    project_root="<project_dir>",
    rocket_file_path="<project_dir>/<rocket_name>.ork",
    method="additive",
    fusion_overrides=<dict if any, else omit>,
)
```

The tool:

1. Calls `openrocket_cad_handoff` internally to get the mm-scaled component tree
2. Walks the tree, applies the DFAM fusion rules (defaults + any overrides you passed), and builds the part list
3. Validates the result against the `PartsManifest` Pydantic schema
4. Writes `<project_root>/parts_manifest.json`
5. Returns the manifest dict

**Do not use the `Write` tool to hand-craft the manifest.** The Python implementation is the source of truth for the fusion rules; hand-writing is both slower (more context tokens) and error-prone (schema drift, typos, missing fields). The `manufacturing_manifest` tool is the only way to produce a manifest.

### 4. Translation Rules Reference

These are the rules the tool applies. Documented here for understanding — do not re-implement them in the agent's reasoning. If you think the tool has applied a rule incorrectly, regenerate with a corrected `fusion_overrides` rather than post-editing the JSON.

| OR component type | Default fate (additive policy) | Notes |
|---|---|---|
| `NoseCone` | `print` | One standalone part. Shoulder is always integral to the nose cone itself; retention mechanism is a separate decision. |
| `BodyTube` | `print` | One part per section. Integrated features come from children (see below). |
| `TubeCoupler` | `fuse` into parent section | Default fuse; overridable via `coupler_fate: "separate"`. |
| `InnerTube` (motor mount) | `fuse` into parent body tube | Default fuse as local wall thickening; overridable via `motor_mount_fate: "separate"`. |
| `CenteringRing` | `absorb` into wall thickening | When motor mount is fused, centering rings vanish entirely. When motor mount is separate, they become standalone parts. |
| `TrapezoidFinSet` | `fuse` into parent body tube | **Always fused for AM.** Non-overridable; separate fin parts have poor layer adhesion. |
| `Parachute` | `skip` | Non-structural assembly item. |
| `MassComponent` | `skip` | Ballast, added at assembly time. |
| `LaunchLug` / `RailButton` | `skip` | Adhesive-mounted at assembly time. |

### 5. Summarise for the User

Report the manifest at a glance before handing off to `generate-structures`:

```
Parts manifest for <rocket_name>:
  Printed parts:
    - nose_cone          (from NoseCone)
    - upper_airframe     (from BodyTube:Upper, fused TubeCoupler:UpperAft)
    - lower_airframe     (from BodyTube:Lower, fused TrapezoidFinSet, fused InnerTube:MotorMount,
                          absorbed CenteringRing:Fore, CenteringRing:Aft)
  Purchased items: (none)
  Skipped: Parachute:Main, MassComponent:Nose Weight
  Decisions:
    - Motor mount: fused (LPR, no swap-out needed)
    - Retention: M4 heat-set (64 mm diameter)
  Total printed parts: 3
```

Stop and ask the user to confirm before generating CAD if any fusion decision was non-default or if the reference collection suggested an alternative.

## Hard Rules — Do Not Violate

- **Fins are ALWAYS fused into the parent body tube.** Never emit a standalone fin set as a separate part. This is a structural requirement for FDM printing — layer lines across the fin root are weak, and a bonded fin can fail under aerodynamic load. There is no scenario in which separate fins are correct for AM.
- **A centering ring never exists as a standalone printed part when the motor mount is fused.** If the motor mount is fused into the body tube as wall thickening, centering rings are geometric artefacts of the traditional construction method and have no physical analogue. Include them in `skipped_components` with the reason `"absorbed into wall thickening"`, not in `parts`.
- **Every section that mates with another section must have a retention mechanism.** Shoulder without heat-set holes / friction fit / pins → assembly-time failure. If you can't pick a retention mechanism, ask the user.
- **Wall thickness below 1.5 mm is a red flag.** Some SLA processes allow it, but FDM below 1.5 mm is weak and warps. Flag before generating.

## AM-Specific Geometry Patterns

These are the building blocks the `generate-structures` skill will use when writing each part's script. The DFAM skill's job is to specify them in the `features` block of each part; the CAD skill's job is to implement them in build123d.

### Local wall thickening (replaces centering rings)
The body tube has a base wall thickness; in the motor mount region, the inner wall steps inward to form the motor bore directly. Outer wall unchanged, inner wall variable along Z. One solid body, no glue joints.

Feature block:
```json
{
  "from": "InnerTube:MotorMount",
  "as": "local_wall_thickening",
  "bore_mm": 29.5,
  "region_start_mm": 280,
  "region_end_mm": 380
}
```

### Integrated fins
Fins extend radially from the outer wall of the body tube, filleted at the root for stress concentration reduction, as part of a single solid body. The number of fins and their angular spacing come from `TrapezoidFinSet`.

Feature block:
```json
{
  "from": "TrapezoidFinSet",
  "as": "integrated_fins",
  "count": 3,
  "root_chord_mm": 80,
  "tip_chord_mm": 40,
  "span_mm": 60,
  "sweep_mm": 25,
  "thickness_mm": 3,
  "fillet_mm": 1.5
}
```

### Integral aft shoulder (fused coupler)
The aft end of the forward section thickens outward into a tapered shoulder that mates with the next section's inner diameter. The shoulder's OD is the next section's ID minus clearance (typically 0.2 mm).

Feature block:
```json
{
  "from": "TubeCoupler:UpperAft",
  "as": "integral_aft_shoulder",
  "od_mm": 59.6,
  "length_mm": 30,
  "retention": {"type": "m4_heat_set", "count": 4}
}
```

### Forward stop lip (motor retention)
Small internal ring at the forward end of the motor bore that prevents motor creep during flight. The motor case rests against this lip; the nozzle passes through.

Feature block:
```json
{
  "from": "InnerTube:MotorMount",
  "as": "forward_stop_lip",
  "bore_mm": 29.5,
  "stop_id_mm": 26.0,
  "thickness_mm": 3.0
}
```

### Heat-set insert boss
A slightly raised flat region around each heat-set hole, for better thread engagement and cleaner drilling with the soldering iron.

Feature block:
```json
{
  "as": "heat_set_bosses",
  "count": 4,
  "angular_positions_deg": [45, 135, 225, 315],
  "z_mm": 395,
  "hole_diameter_mm": 5.7,
  "hole_depth_mm": 7.0,
  "boss_diameter_mm": 9.0,
  "boss_height_mm": 1.5
}
```

## Red Flags — Stop and Check

- A centering ring appears in the `parts` list while the motor mount has fate `"fuse"` → contradiction, the rings should be in `skipped_components` with reason `"absorbed into wall thickening"`
- A standalone `motor_mount` part is generated when the parent body tube has fate `"fuse"` → contradiction
- A `fin_set.step` file path appears anywhere → always wrong, fins must be integrated
- A shoulder has no retention mechanism specified → assembly-time failure mode
- `component_to_part_map` maps an OR component to no entry → the mass-calibration skill will fail to attribute its weight later
- Multiple OR components map to the same part but the `derived_from` list doesn't reflect that → auditability broken
- Any wall thickness below 1.5 mm → structural red flag for FDM, acceptable only for SLA with explicit user confirmation
- The parts list has more printed parts than the OR tree suggests should exist (e.g. 6 printed parts from a single-section LPR) → the fusion logic isn't firing, review defaults
- A `TubeCoupler` is marked `fuse` but the design is dual-deploy → may be wrong, ask the user
- The user requested `retention="m4_heat_set"` but no `radial_holes` modifications appear in the manifest → the design probably has no `TubeCoupler` to fuse into a shoulder. Retention modifications are tied to integral shoulders; without a shoulder there's nowhere to put the holes. Either add a coupler to the OR design or use a different mating strategy (friction fit on the nose cone shoulder, etc.)

## parts_manifest.json Schema

```json
{
  "schema_version": 1,
  "source_ork": "<absolute path to .ork file>",
  "project_root": "<absolute path to project directory>",
  "default_policy": "additive",
  "generated_at": "<ISO 8601 timestamp>",

  "directories": {
    "scripts": "build123d",
    "step": "CAD",
    "gcode": "gcode"
  },

  "parts": [
    {
      "name": "<snake_case part name>",
      "script_path": "build123d/<name>.py",
      "step_path": "CAD/<name>.step",
      "gcode_path": "gcode/<name>.gcode",
      "derived_from": ["<OR component identifier>", "..."],
      "fate": "print",
      "features": {
        "<feature_key>": "<value or nested object>"
      }
    }
  ],

  "purchased_items": [
    {
      "derived_from": "<OR component identifier>",
      "description": "<human-readable description>",
      "suggested_source": "<vendor and part number if known>"
    }
  ],

  "skipped_components": [
    {
      "name": "<OR component identifier>",
      "reason": "<short explanation>"
    }
  ],

  "assemblies": [
    {
      "name": "<assembly name>",
      "step_path": "CAD/<assembly name>.step",
      "parts_fore_to_aft": ["<part name>", "..."]
    }
  ],

  "decisions": [
    {
      "decision": "<decision key, e.g. motor_mount_fate>",
      "policy_default": "<what the default would have been>",
      "chosen": "<what was actually chosen>",
      "reason": "<short explanation including any user input>"
    }
  ],

  "component_to_part_map": {
    "<OR component identifier>": "<part name or 'skipped' or 'purchased'>"
  }
}
```

### Field notes

- **`derived_from`** entries use the OR component's `type` and `name` joined by a colon, e.g. `"BodyTube:Upper Airframe"`, `"TrapezoidFinSet:Trapezoidal Fin Set"`. When there's only one component of a type in the rocket, the bare type suffices.
- **`fate`** is one of `"print"`, `"purchase"`, or `"skip"`. Fused components don't appear as their own parts — they're represented in `skipped_components` with a reason pointing at the part they were fused into, and the target part's `derived_from` includes them.
- **`directories`** is fixed per the project layout convention. Don't vary it per project.
- **`component_to_part_map`** is the authoritative lookup. Every OR component in the `.ork` file must appear as a key, mapped to either the name of the printed part it contributes to, the string `"skipped"`, or the string `"purchased"`. The mass-calibration skill uses this to attribute `filament_used_g` readings back to OR component mass overrides.
- **`assemblies`** is optional for now. Leave it as an empty list if not generating assembly STEPs.

## Quick Reference

```
# the translation
openrocket_cad_handoff → {components, derived, handoff_notes}
                      ↓
                 this skill applies policy + fusion rules
                      ↓
              parts_manifest.json at project root
                      ↓
          generate-structures skill → build123d scripts → STEP files
                      ↓
              prusaslicer → gcode → filament_used_g
                      ↓
    mass-calibration reads component_to_part_map and applies
    override_mass_kg via openrocket_component
```

```
# the hard rules (reprise)
1. Fins are ALWAYS fused into the parent body tube
2. Centering rings vanish when the motor mount is fused
3. Every mated section needs a retention mechanism
4. Wall thickness ≥ 1.5 mm (FDM) or explicit user confirmation (SLA)
```
