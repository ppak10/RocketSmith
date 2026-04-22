[![pytest](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml)
[![claude](https://github.com/ppak10/RocketSmith/actions/workflows/claude.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/claude.yml)
[![gemini](https://github.com/ppak10/RocketSmith/actions/workflows/gemini.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/gemini.yml)
[![codecov](https://codecov.io/github/ppak10/RocketSmith/graph/badge.svg?token=CODECOV_TOKEN)](https://codecov.io/github/ppak10/RocketSmith)

# <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.iconify.design/lucide/rocket.svg?color=white&width=32&height=32"><img src="https://api.iconify.design/lucide/rocket.svg?color=black&width=32&height=32" width="32" height="32" /></picture> RocketSmith

Let agents design, simulate, and build your rocket.

RocketSmith is an end-to-end model-rocket toolchain exposed as an MCP extension. It orchestrates **OpenRocket** (flight simulation), **build123d** (parametric CAD), and **PrusaSlicer** (FDM slicing) behind a single agent, and closes the loop by feeding real printed-part weights back into the simulation for post-build stability verification.

## Install

**Prerequisites (all platforms):**
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — RocketSmith uses `uv` to manage its Python environment. Install it before proceeding.
- A GitHub SSH key added to your account — required to clone the plugin repository. See [Generating a new SSH key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent).

### Claude Code (plugin)

Inside a Claude Code session, add the marketplace and install the plugin at **user scope**:

```
/plugin marketplace add ppak10/RocketSmith
```

```
/plugin install rocketsmith@rocketsmith --scope user
```

After installing, reload plugins and verify the MCP server is connected with `/reload-plugins` and `/mcp`

**Updating to a new version:** Uninstall the existing plugin first, then reinstall:

```
/plugin uninstall rocketsmith@rocketsmith
```

```
/plugin install rocketsmith@rocketsmith --scope user
```

### [Gemini CLI (extension)](https://geminicli.com/extensions/?name=ppak10RocketSmith)

```bash
gemini extensions install https://github.com/ppak10/RocketSmith
```

## Requirements

- **Java runtime** — required by OpenRocket
- **OpenRocket 23.09** — uses [orhelper](https://github.com/SilentSys/orhelper), which targets the `net.sf.openrocket` package in OpenRocket 23.09 and earlier. OpenRocket 24+ is not supported.
- **PrusaSlicer** (optional — needed for the full CAD → print → mass calibration loop)

See [Installation](https://github.com/ppak10/RocketSmith/wiki/Installation) for platform-specific setup and troubleshooting.

## Troubleshooting

### Windows — OpenRocket calls are very slow or appear to hang

OpenRocket runs on a JVM. On Windows, the first `openrocket_*` call in a session pays a JVM cold-start cost of **67 seconds to 6 minutes**. This is normal — the tool will eventually return. Do not cancel the call or retry early; let it finish. Subsequent calls in the same session are faster once the JVM is warm.

### Windows — `rocketsmith_setup` fails with `[WinError 87] The parameter is incorrect`

This was a bug in path resolution on Windows where `Path.resolve()` raised `OSError` for certain path types. It is fixed in the current version. If you hit it on an older version, call `rocketsmith_setup(action="check")` first (no `project_dir`), confirm `ready: true`, then call again with `project_dir`.

### Claude Code — agent continuation fails ("SendMessage not found")

Claude Code requires **v2.1.77 or later** for inter-agent `SendMessage` to work. On older versions, attempting to continue a spawned subagent by `agentId` will fail because the tool doesn't exist yet. Update Claude Code to the latest release to resolve this.

### MCP server disconnects mid-session

Rejecting a pending rocketsmith tool call can cause the MCP server to disconnect, disabling all rocketsmith tools for the rest of the session. If this happens, restart the MCP server: in Claude Code run `/mcp`, find the rocketsmith server, and reconnect. In Gemini CLI, restart the session.

## Documentation

- [Home](https://github.com/ppak10/RocketSmith/wiki/Home) — pipeline overview, domain agents, MCP tool list
- [GUI](https://github.com/ppak10/RocketSmith/wiki/GUI) — dashboard, offline mode, navigation, Agent Feed
- [OpenRocket](https://github.com/ppak10/RocketSmith/wiki/OpenRocket) — component tree, stability, dimension models
- [Manufacturing](https://github.com/ppak10/RocketSmith/wiki/Manufacturing) — DFAM rules, component tree annotations
- [CADSmith](https://github.com/ppak10/RocketSmith/wiki/CADSmith) — script execution, part extraction, preview pipeline, assembly
- [Skills](https://github.com/ppak10/RocketSmith/wiki/Skills) — stability analysis, motor selection, print preparation, mass calibration
- [Installation](https://github.com/ppak10/RocketSmith/wiki/Installation) — setup and dependency troubleshooting
- [Hooks](https://github.com/ppak10/RocketSmith/wiki/Hooks) — Gemini CLI session hooks

## Development

### Local setup

```bash
git clone https://github.com/ppak10/RocketSmith
cd RocketSmith
uv sync
```

#### Claude Code

```bash
claude --plugin-dir .
```

#### Gemini CLI

```bash
gemini extensions install .
```

## License

See [LICENSE](LICENSE).
