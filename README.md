[![pytest](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml)
[![macos](https://github.com/ppak10/RocketSmith/actions/workflows/macos.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/macos.yml)
[![ubuntu](https://github.com/ppak10/RocketSmith/actions/workflows/ubuntu.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/ubuntu.yml)
[![windows](https://github.com/ppak10/RocketSmith/actions/workflows/windows.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/windows.yml)
[![codecov](https://codecov.io/github/ppak10/RocketSmith/graph/badge.svg?token=CODECOV_TOKEN)](https://codecov.io/github/ppak10/RocketSmith)

# <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.iconify.design/lucide/rocket.svg?color=white&width=32&height=32"><img src="https://api.iconify.design/lucide/rocket.svg?color=black&width=32&height=32" width="32" height="32" /></picture> RocketSmith

Let agents design, simulate, and build your rocket.

## Installation

```bash
uv add rocketsmith
```

### OpenRocket

RocketSmith uses [orhelper](https://github.com/SilentSys/orhelper) to interface with OpenRocket. orhelper 0.1.x targets the `net.sf.openrocket` Java package, which was present in **OpenRocket 23.09 and earlier**. OpenRocket 24+ reorganized its packages to `info.openrocket` and is not currently supported.

Install OpenRocket 23.09 and a Java runtime with a single command:

```bash
rocketsmith openrocket install
```

This will:
1. Install a Java runtime if none is found (via `brew install openjdk` on macOS, `apt` on Linux, `winget` on Windows)
2. Download the OpenRocket 23.09 JAR to `~/.local/share/openrocket/` (macOS/Linux) or `~/AppData/Local/OpenRocket/` (Windows)

To verify the installation:

```bash
rocketsmith openrocket version
```

## Agent Setup

### Claude Code (Plugin — recommended)

Add the rocketsmith marketplace and install the plugin:

```bash
/plugin marketplace add ppak10/RocketSmith
/plugin install rocketsmith@rocketsmith
```

This registers the MCP server and installs the rocketsmith agent automatically. No additional steps required.

To update:

```bash
/plugin marketplace update rocketsmith
```

### Claude Code (manual install)

If you prefer to manage the installation yourself:

```bash
rocketsmith mcp install
```

To upgrade the package and refresh the agent file:

```bash
rocketsmith update
```

### Claude Desktop

```bash
rocketsmith mcp install claude-desktop --project-path /path/to/RocketSmith
```

Note: Restart Claude Desktop after installation for changes to take effect.

## MCP Tools

The following tools are exposed to agents via the MCP server.

| Tool | Description |
|---|---|
| `rocketsmith_setup` | Check or install dependencies (Java, OpenRocket, PrusaSlicer) |
| `workspace_create` | Create a new workspace |
| `openrocket_new` | Create a new empty `.ork` file |
| `openrocket_inspect` | Return the full component tree of an `.ork` file |
| `openrocket_component` | Create, read, update, or delete a component (`action` parameter) |
| `openrocket_database` | Query the OpenRocket built-in database for motors, presets, or materials |
| `openrocket_flight` | Create or delete a simulation entry with a motor assignment (`action` parameter) |
| `openrocket_simulate` | Run all simulations in an `.ork` file and return flight summaries |
| `prusaslicer_slice` | Slice a model with PrusaSlicer |

The standard agent workflow is:

```
openrocket_new → openrocket_component (×N) → openrocket_flight (create) → openrocket_simulate
```

### `openrocket_component` actions

The `openrocket_component` tool accepts an explicit `action` parameter:

| Action | Required params | Description |
|---|---|---|
| `create` | `component_type` | Add a new component. Valid types: `nose-cone`, `body-tube`, `inner-tube`, `transition`, `fin-set`, `parachute`, `mass` |
| `read` | `component_name` | Return properties of a named component |
| `update` | `component_name` | Modify one or more properties of a named component |
| `delete` | `component_name` | Remove a named component |

`inner-tube` represents a motor mount tube — the standard way to house a motor inside a larger airframe. It is placed inside a body tube and its diameter determines the motor size.

All dimensional properties are in SI units (metres, kilograms).

**Preset and material support (`create` and `update`):**

| Parameter | Description |
|---|---|
| `preset_part_no` | Part number from `openrocket_database` (e.g. `BT-20`). Loads manufacturer geometry and material as a baseline. |
| `preset_manufacturer` | Optional manufacturer filter when the same part number appears across brands. |
| `material_name` | Material name from `openrocket_database` (e.g. `Aluminum`, `Carbon fiber`). Overrides the preset's material when combined with `preset_part_no`. |
| `material_type` | Narrows material lookup to `bulk`, `surface`, or `line`. Optional. |

Explicit dimension params (e.g. `length`, `diameter`) always override the loaded preset. The precedence is: preset baseline → dimension overrides → material override.

### `openrocket_database` actions

| Action | Required params | Optional filters | Description |
|---|---|---|---|
| `motors` | — | `manufacturer`, `impulse_class`, `diameter_mm`, `motor_type` | List ~1,900 motors. Returns manufacturer, name, impulse, thrust, burn time, and `digest` (used internally by OpenRocket to identify a thrust curve). |
| `presets` | `preset_type` | `manufacturer` | List manufacturer component presets. Valid types: `body-tube`, `nose-cone`, `transition`, `tube-coupler`, `bulk-head`, `centering-ring`, `engine-block`, `launch-lug`, `rail-button`, `streamer`, `parachute`. |
| `materials` | `material_type` | — | List structural materials. Valid types: `bulk` (kg/m³), `surface` (kg/m²), `line` (kg/m). |

Use the `limit` parameter (default `50`, pass `None` for all results) to control response size.

### `openrocket_flight` actions

| Action | Required params | Description |
|---|---|---|
| `create` | `motor_designation` | Assign a motor to a mount, create a flight configuration, and add a simulation entry. The file is ready to pass to `openrocket_simulate`. |
| `delete` | `sim_name` | Remove a named simulation entry. |

**Motor lookup:** `motor_designation` is matched against the common name (e.g. `D12`, `H128W`) or full designation. Use `openrocket_database(action="motors")` to find valid designations.

**Motor mount selection:** Automatically uses the first `inner-tube` in the rocket, falling back to the first `body-tube`. Pass `mount_name` to target a specific component.

**Launch condition parameters (`create` only):**

| Parameter | Default | Description |
|---|---|---|
| `sim_name` | motor designation | Name for the simulation entry |
| `mount_name` | auto-detected | Named component to use as motor mount |
| `launch_rod_length_m` | `1.0` | Launch rod length in metres |
| `launch_rod_angle_deg` | `0.0` | Rod angle from vertical in degrees |
| `launch_altitude_m` | `0.0` | Launch site altitude in metres ASL |
| `launch_temperature_c` | ISA standard | Launch temperature in °C |
| `wind_speed_ms` | `0.0` | Average wind speed in m/s |

### `openrocket_simulate` output

Each simulation summary includes:

| Field | Description |
|---|---|
| `max_altitude_m` | Peak altitude in metres |
| `max_velocity_ms` | Peak velocity in m/s |
| `time_to_apogee_s` | Time to apogee in seconds |
| `flight_time_s` | Total flight time in seconds |
| `min_stability_cal` | Minimum stability margin over the flight in calibers |
| `max_stability_cal` | Maximum stability margin over the flight in calibers |

A stability margin above ~1.5 calibers is generally considered stable for most hobby rockets.

## CLI Reference

### Workspace

Workspaces are project folders that organize your `.ork` design files and simulation outputs.

**Create a workspace:**

```bash
rocketsmith workspace create <workspace-name>
```

**Create a workspace with example files:**

```bash
rocketsmith workspace create <workspace-name> --include-examples
```

This copies `simple.ork` into the `openrocket/` subfolder of the workspace, ready to run simulations.

---

### OpenRocket

All OpenRocket commands resolve `.ork` files from `<workspace>/openrocket/<filename>`. Use `--workspace` / `-w` to specify a workspace, or `--openrocket-path` to point to a non-standard JAR location.

**Install OpenRocket 23.09 and Java:**

```bash
rocketsmith openrocket install
```

**Check installed version:**

```bash
rocketsmith openrocket version
```

**Create a new empty `.ork` file:**

```bash
rocketsmith openrocket new <name> --workspace <workspace-name>
```

**Inspect the component tree of an `.ork` file:**

```bash
rocketsmith openrocket inspect <filename.ork> --workspace <workspace-name>
```

**Run all simulations in an `.ork` file:**

```bash
rocketsmith openrocket run-simulation <filename.ork> --workspace <workspace-name>
```

Example:

```bash
rocketsmith workspace create my-rocket --include-examples
rocketsmith openrocket run-simulation simple.ork --workspace my-rocket
```

---

#### Components

**Add a component:**

```bash
rocketsmith openrocket create-component <filename.ork> <type> [options] --workspace <workspace-name>
```

Valid types: `nose-cone`, `body-tube`, `inner-tube`, `transition`, `fin-set`, `parachute`, `mass`

| Option | Description |
|---|---|
| `--name` | Component name |
| `--parent` | Named parent component (defaults to first stage or last body tube) |
| `--preset` | Manufacturer part number to load as a preset baseline (e.g. `BT-20`) |
| `--preset-manufacturer` | Manufacturer filter for preset lookup |
| `--material` | Material name to apply (e.g. `Aluminum`, `Carbon fiber`) |
| `--material-type` | Material type for lookup: `bulk`, `surface`, or `line` |
| `--length` | Length in metres |
| `--diameter` | Diameter in metres (base for nose-cone, outer for body-tube) |
| `--fore-diameter` | Fore diameter in metres (transition only) |
| `--aft-diameter` | Aft diameter in metres (transition only) |
| `--thickness` | Wall thickness in metres |
| `--shape` | Nose-cone/transition shape: `ogive`, `conical`, `ellipsoid`, `power`, `parabolic`, `haack` |
| `--count` | Fin count (fin-set only) |
| `--root-chord` | Fin root chord in metres |
| `--tip-chord` | Fin tip chord in metres |
| `--span` | Fin span in metres |
| `--sweep` | Fin sweep length in metres |
| `--cd` | Parachute drag coefficient |
| `--mass` | Mass in kg (mass component only) |

When `--preset` is provided, it loads the manufacturer's geometry and material as a baseline. Any additional options (e.g. `--length`) override the preset values.

Examples:

```bash
# Build from scratch and simulate
rocketsmith openrocket new my-rocket --workspace my-workspace
rocketsmith openrocket create-component my-rocket.ork nose-cone --name "Nose" --length 0.15 --diameter 0.064 --shape ogive --workspace my-workspace
rocketsmith openrocket create-component my-rocket.ork body-tube --name "Body" --length 0.4 --diameter 0.064 --workspace my-workspace
rocketsmith openrocket create-component my-rocket.ork inner-tube --name "Motor Mount" --diameter 0.029 --length 0.1 --workspace my-workspace
rocketsmith openrocket create-component my-rocket.ork fin-set --count 3 --root-chord 0.08 --tip-chord 0.04 --span 0.06 --workspace my-workspace

# Build from manufacturer presets
rocketsmith openrocket create-component my-rocket.ork body-tube --preset BT-20 --workspace my-workspace
rocketsmith openrocket create-component my-rocket.ork body-tube --preset BT-20 --length 0.5 --workspace my-workspace  # preset diameter, custom length
rocketsmith openrocket create-component my-rocket.ork body-tube --preset BT-20 --material "Carbon fiber" --workspace my-workspace  # swap material
```

**Read a component's properties:**

```bash
rocketsmith openrocket read-component <filename.ork> "<component-name>" --workspace <workspace-name>
```

**Update a component:**

```bash
rocketsmith openrocket update-component <filename.ork> "<component-name>" [options] --workspace <workspace-name>
```

Accepts the same options as `create-component` including `--preset` and `--material`. Only the provided options are changed. Note: providing `--preset` resets the component's geometry to the preset's defaults before applying any other options.

**Delete a component:**

```bash
rocketsmith openrocket delete-component <filename.ork> "<component-name>" --workspace <workspace-name>
```

---

#### Database

Browse or query the OpenRocket built-in database of motors, manufacturer component presets, and structural materials.

**Interactive browser:**

```bash
rocketsmith openrocket database
```

Opens a drill-down menu: select a category (Motors, Recovery, Airframe, Hardware, Materials), apply filters, and pick an item to view its full spec.

**List motors:**

```bash
rocketsmith openrocket list-motors [--class <letter>] [--diameter <mm>] [--manufacturer <name>] [--type <single-use|reloadable|hybrid>]
```

**List component presets:**

```bash
rocketsmith openrocket list-presets <type> [--manufacturer <name>]
```

Valid types: `body-tube`, `nose-cone`, `transition`, `tube-coupler`, `bulk-head`, `centering-ring`, `engine-block`, `launch-lug`, `rail-button`, `streamer`, `parachute`

**List materials:**

```bash
rocketsmith openrocket list-materials <type>
```

Valid types: `bulk` (density in kg/m³), `surface` (area density in kg/m²), `line` (linear density in kg/m)
