---
name: motor-selection
description: Use when choosing a motor for a rocket design, or when the user asks what motor to use to reach a target apogee
---

# Motor Selection

## Overview

Motor selection balances impulse (altitude), diameter (fit), and thrust curve (stability off the rod). A motor that fits the mount and hits the target apogee is not enough — it must also produce enough thrust to clear the launch rod stably.

**Core principle:** Always verify the motor exists in the database before assigning it. Never guess a designation.

## When to Use

- Initial motor selection for a new design
- User wants to reach a specific apogee
- Current motor undershoots or overshoots the target
- Motor diameter doesn't match the motor mount

## Steps

### 1. Gather Constraints

Before querying, establish:
- **Rocket mass** — from `openrocket_inspect` component weights, or user-provided
- **Target apogee** — what the user wants to achieve
- **Motor mount ID** — inner diameter of the motor mount inner-tube
- **Motor class ceiling** — any certification or field limits (e.g. Estes field = max D)

### 2. Estimate Required Impulse

Rule of thumb: **30–50 m of apogee per newton-second**, depending on mass and drag.

```
required_Ns ≈ target_apogee_m / 40    (midpoint estimate)
```

Map to impulse class:

| Class | Total Impulse | Rough apogee (500g rocket) |
|-------|-------------|---------------------------|
| C | 10 Ns | ~100 m |
| D | 20 Ns | ~200 m |
| E | 40 Ns | ~350 m |
| F | 80 Ns | ~600 m |
| G | 160 Ns | ~1000 m |
| H | 320 Ns | ~1500 m |

This is a starting point only — simulate to confirm.

### 3. Query the Database

```
openrocket_database(action="motors", impulse_class="D", diameter_mm=18)
```

Useful filter combinations:
- `impulse_class` + `diameter_mm` — most common starting point
- `name="H100"` — when you know the approximate designation (matches H100W-DMS, H100T, etc.)
- `manufacturer="Estes"` — when field or certification requires a specific brand

Review `avg_thrust_n` and `burn_time_s` in the results. A high average thrust with short burn (spike profile) vs. a lower average with longer burn (progressive) affects flight character.

### 4. Check Thrust-to-Weight

Minimum thrust-to-weight ratio off the rod: **5:1** recommended.

```
thrust_to_weight = avg_thrust_n / (rocket_mass_kg × 9.81)
```

If below 5:1, the rocket will leave the rod slowly and be vulnerable to weathercocking. Choose a higher-thrust variant or longer launch rod.

### 5. Check the Reference Collection for Known Issues

Query `rag_reference(action="search", collection="motor_reviews", query=f"{motor_designation} {manufacturer}", n_results=3)` for real-world reports (delay reliability, ignition problems, CATO reports, observed vs. predicted apogee). Weigh any hits against the theoretical numbers. Proceed if no results or on errors.

### 6. Simulate Candidates

For each candidate motor:
1. `openrocket_flight(action="create", motor=<designation>)` — assign motor
2. `openrocket_simulation` — run simulation
3. Note `max_altitude_m` and `min_stability_cal`
4. `openrocket_flight(action="delete")` before trying the next candidate

Pick the motor that hits the target apogee while keeping stability ≥ 1.0 cal throughout flight.

### 7. Confirm Fit

After selecting a motor, verify:
- Motor diameter ≤ motor mount inner tube ID
- Motor length ≤ motor mount tube length
- If using a reloadable case, the reload length matches the mount

## Red Flags — Stop and Check

- Assigning a motor designation not returned by `openrocket_database` — it won't load
- Skipping simulation and trusting the rule-of-thumb estimate alone
- Thrust-to-weight < 2:1 — unsafe launch, not just sub-optimal
- Changing motor class without re-checking stability (heavier motors shift CG aft)

## Quick Reference

```
Impulse needed ≈ target_apogee / 40
Motor must fit: diameter ≤ mount ID, length ≤ mount length
Thrust-to-weight ≥ 5:1 recommended off the rod
Always simulate — rule of thumb is a starting point only
```
