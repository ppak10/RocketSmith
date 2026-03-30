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

### Claude Code

```bash
rocketsmith mcp install
```

### Claude Desktop

```bash
rocketsmith mcp install claude-desktop --project-path /path/to/RocketSmith
```

Note: Restart Claude Desktop after installation for changes to take effect.

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

**Install OpenRocket 23.09 and Java:**

```bash
rocketsmith openrocket install
```

**Check installed version:**

```bash
rocketsmith openrocket version
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

The `--workspace` / `-w` flag resolves the `.ork` file from `<workspace>/openrocket/<filename.ork>`. If your OpenRocket JAR is in a non-standard location, use `--openrocket-path` to point to it directly.
