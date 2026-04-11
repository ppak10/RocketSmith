[![pytest](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml)
[![macos](https://github.com/ppak10/RocketSmith/actions/workflows/macos.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/macos.yml)
[![ubuntu](https://github.com/ppak10/RocketSmith/actions/workflows/ubuntu.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/ubuntu.yml)
[![windows](https://github.com/ppak10/RocketSmith/actions/workflows/windows.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/windows.yml)
[![codecov](https://codecov.io/github/ppak10/RocketSmith/graph/badge.svg?token=CODECOV_TOKEN)](https://codecov.io/github/ppak10/RocketSmith)

# <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.iconify.design/lucide/rocket.svg?color=white&width=32&height=32"><img src="https://api.iconify.design/lucide/rocket.svg?color=black&width=32&height=32" width="32" height="32" /></picture> RocketSmith

Let agents design, simulate, and build your rocket.

RocketSmith is an end-to-end model-rocket toolchain exposed as an MCP extension. It orchestrates **OpenRocket** (flight simulation), **build123d** (parametric CAD), and **PrusaSlicer** (FDM slicing) behind a single agent, and closes the loop by feeding real printed-part weights back into the simulation for post-build stability verification.

## Install

RocketSmith integrates with AI coding tools through their native plugin/extension interfaces for MCP. A `uv` package is also available for CLI usage and direct API access.

### Gemini CLI (extension)

```bash
gemini extensions install https://github.com/ppak10/RocketSmith
```

The extension registers the MCP server, orchestrator agent, domain subagents (`openrocket`, `manufacturing`, `cadsmith`, `prusaslicer`), and action skills automatically.

### Claude Code (plugin)

Register the RocketSmith marketplace and install the plugin:

```bash
/plugin marketplace add ppak10/RocketSmith
/plugin install rocketsmith@rocketsmith
```

This installs the full plugin — MCP server, orchestrator agent, domain subagents (`openrocket`, `manufacturing`, `cadsmith`, `prusaslicer`), action skills, and session hooks. Update with `/plugin update rocketsmith`.

#### Local development

To test from a local clone, start Claude Code with `--plugin-dir` pointing at the repo:

```bash
claude --plugin-dir .
```

Use `/reload-plugins` to pick up changes without restarting.

### CLI / API

```bash
uv tool install rocketsmith
```

This installs the `rocketsmith` CLI for direct command-line usage and makes the Python API available for scripting. The CLI is independent of any AI coding tool — use it for automation, CI, or standalone workflows.

### First run

```
@rocketsmith design and build a stable rocket for a D12 motor
```

The orchestrator will walk through simulation → CAD → slicing → mass calibration, pausing for user feedback during the interactive CAD phase.

## Documentation

Full documentation lives in the [wiki](https://github.com/ppak10/RocketSmith/wiki):

- [Home](https://github.com/ppak10/RocketSmith/wiki/Home) — pipeline overview, domain agents, and MCP tool list
- [OpenRocket](https://github.com/ppak10/RocketSmith/wiki/OpenRocket) — component tree generation, stability calculations, dimension models
- [Manufacturing](https://github.com/ppak10/RocketSmith/wiki/Manufacturing) — DFAM rules, component tree annotations, fusion overrides
- [CADSmith](https://github.com/ppak10/RocketSmith/wiki/CADSmith) — script execution, part extraction, preview pipeline, assembly
- [Skills](https://github.com/ppak10/RocketSmith/wiki/Skills) — stability analysis, motor selection, print preparation, mass calibration
- [Installation](https://github.com/ppak10/RocketSmith/wiki/Installation) — plugin/extension setup and dependency troubleshooting
- [Hooks](https://github.com/ppak10/RocketSmith/wiki/Hooks) — session-start dependency checks and other hooks

## Building the GUI

The GUI frontend (React/TypeScript) must be compiled before changes are reflected in production mode. The built files live in `src/rocketsmith/data/gui/` and are committed to the repo so users don't need to build them.

```bash
cd src/rocketsmith/gui/web
npm install
npm run build
```

A pre-commit hook automatically rebuilds the GUI when frontend source files change.

## Requirements

- **Java runtime** — required by OpenRocket
- **OpenRocket 23.09** — RocketSmith uses [orhelper](https://github.com/SilentSys/orhelper), which targets the `net.sf.openrocket` package present in OpenRocket 23.09 and earlier. OpenRocket 24+ is not currently supported.
- **PrusaSlicer** (optional, only needed for the CAD → print → calibration loop)

## License

See [LICENSE](LICENSE).
