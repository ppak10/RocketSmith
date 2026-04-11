---
name: stability-analysis
description: Use when a flight returns stability outside 1.0–1.5 calibers, or when min_stability_cal is null
---

# Stability Analysis

## Overview

Stability margin = (CP − CG) / reference diameter, measured in calibers. The target is **1.0–1.5 cal**. Outside this range the rocket is either dangerous or excessively weathercock-sensitive.

**Core principle:** Always fix the root cause — geometry or mass distribution — not the symptom. Never accept a `null` stability result; compute it manually.

## When to Use

- `min_stability_cal` < 1.0 (unstable)
- `min_stability_cal` > 1.5 (over-stable)
- `min_stability_cal` is `null` after simulation
- User reports unexpected flight path or weathercocking
- Stability was in range before `rocketsmith:mass-calibration` but fell out after applying real printed part weights — this is the expected failure mode when printed PLA/PETG is significantly heavier than OpenRocket's material defaults

## Steps

### 1. Read the Numbers

Run `openrocket_inspect` and note:
- `cg_x` — center of gravity from nose tip (m)
- `cp_x` — center of pressure from nose tip (m)
- `max_diameter_m` — reference diameter

If `min_stability_cal` returned `null`, compute manually:
```
stability_cal = (cp_x - cg_x) / max_diameter_m
```

A positive result means CP is aft of CG — stable. A negative or zero result means unstable.

### 1.5. Consult the Reference Collection

Query `rag_reference(action="search", collection="stability_notes", query=f"stability {round(current_cal, 2)} cal {symptom}", n_results=3)` for prior cases with known fixes. Cite close matches and weigh against the heuristic below. Proceed if no results or on errors — the collection is an enrichment, not a prerequisite.

### 2. Diagnose the Direction

**Under-stable (< 1.0 cal):** CP is too close to CG, or forward of it.
- Fins too small or too far forward
- Nose cone too heavy
- Body tube too short relative to fin span

**Over-stable (> 1.5 cal):** CP is too far aft of CG.
- Fins too large
- Nose cone too light
- Aft mass (motor, motor mount) dominating

### 3. Apply Fixes

Work one change at a time. Re-simulate after each.

**To increase stability (move CP aft or CG forward):**

| Fix | Tool | Notes |
|-----|------|-------|
| Increase fin span | `openrocket_component` update fin-set `span` | Most effective single change |
| Increase fin root chord | `openrocket_component` update fin-set `root_chord` | Moves CP aft |
| Move fins aft | `openrocket_component` update fin-set `axial_offset_method="bottom"`, `axial_offset_m=0` | Fins flush with aft end |
| Add nose weight | `openrocket_component` create mass component in NoseCone | Moves CG forward |

**To reduce stability (move CP forward or CG aft):**

| Fix | Tool | Notes |
|-----|------|-------|
| Reduce fin span | `openrocket_component` update fin-set `span` | Start with 10–15% reduction |
| Reduce fin root chord | `openrocket_component` update fin-set `root_chord` | |
| Add aft mass | `openrocket_component` create mass component in lower airframe | Moves CG aft |

### 4. Iterate

After each change:
1. `openrocket_flight(action="run")` — check new `min_stability_cal`
2. Also check `max_stability_cal` — stability varies over the flight as propellant burns
3. Stop when 1.0–1.5 cal across the full flight

### 5. Verify Final Design

Run `openrocket_inspect` one more time. Confirm:
- `cp_x` > `cg_x` (CP aft of CG)
- `stability_cal` in range
- No component geometry was accidentally broken

## Red Flags — Stop and Investigate

- Accepting `null` stability without manual computation
- Making two geometry changes at once (can't isolate which worked)
- Stability in range on launch but diverging later in flight — check `max_stability_cal` too
- Fin span larger than 1.5× body diameter (drag penalty outweighs stability gain — find another fix)

## Quick Reference

| Stability | Problem | Primary Fix |
|-----------|---------|-------------|
| < 0.5 cal | Severely unstable | Increase fin span significantly |
| 0.5–1.0 cal | Unstable | Increase fin span or add nose weight |
| 1.0–1.5 cal | ✓ Target range | No change needed |
| 1.5–2.0 cal | Over-stable | Reduce fin area |
| > 2.0 cal | Very over-stable | Reduce fin area + check mass distribution |
