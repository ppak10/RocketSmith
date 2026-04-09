[![pytest](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml)
[![macos](https://github.com/ppak10/RocketSmith/actions/workflows/macos.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/macos.yml)
[![ubuntu](https://github.com/ppak10/RocketSmith/actions/workflows/ubuntu.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/ubuntu.yml)
[![windows](https://github.com/ppak10/RocketSmith/actions/workflows/windows.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/windows.yml)
[![codecov](https://codecov.io/github/ppak10/RocketSmith/graph/badge.svg?token=CODECOV_TOKEN)](https://codecov.io/github/ppak10/RocketSmith)

# <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.iconify.design/lucide/rocket.svg?color=white&width=32&height=32"><img src="https://api.iconify.design/lucide/rocket.svg?color=black&width=32&height=32" width="32" height="32" /></picture> RocketSmith

Let agents design, simulate, and build your rocket.

RocketSmith is an end-to-end model-rocket toolchain exposed as an MCP extension. It orchestrates **OpenRocket** (flight simulation), **build123d** (parametric CAD), and **PrusaSlicer** (FDM slicing) behind a single agent, and closes the loop by feeding real printed-part weights back into the simulation for post-build stability verification.

## Install (Gemini CLI)

```bash
gemini extensions install https://github.com/ppak10/RocketSmith
```

That's it. The extension registers the `rocketsmith` MCP server and loads the orchestrator agent, the three domain subagents (`openrocket`, `build123d`, `prusaslicer`), and the action skills.

On first use, ask the agent to run dependency setup:

```
@rocketsmith check dependencies
```

It will detect whether Java, OpenRocket 23.09, and PrusaSlicer are installed and offer to install anything missing.

### First run

```
@rocketsmith design and build a stable rocket for a D12 motor
```

The orchestrator will walk through simulation → CAD → slicing → mass calibration and report at each phase.

> **Claude Code and Codex support** — instructions are coming. For now, Gemini CLI is the supported entry point.

## Documentation

Full documentation lives in the [wiki](https://github.com/ppak10/RocketSmith/wiki):

- [Home](https://github.com/ppak10/RocketSmith/wiki/Home) — pipeline overview, domain agents, and MCP tool list
- [Installation](https://github.com/ppak10/RocketSmith/wiki/Installation) — Gemini CLI setup and dependency troubleshooting
- [Skills](https://github.com/ppak10/RocketSmith/wiki/Skills) — stability analysis, motor selection, CAD handoff, print preparation, mass calibration
- [Hooks](https://github.com/ppak10/RocketSmith/wiki/Hooks) — session-start dependency checks and other hooks

## Requirements

- **Gemini CLI** ≥ the version that supports `gemini extensions install`
- **Java runtime** (auto-installed by the agent if missing)
- **OpenRocket 23.09** — RocketSmith uses [orhelper](https://github.com/SilentSys/orhelper), which targets the `net.sf.openrocket` package present in OpenRocket 23.09 and earlier. OpenRocket 24+ is not currently supported.
- **PrusaSlicer** (optional, only needed for the CAD → print → calibration loop)

All three are auto-installable via `@rocketsmith install dependencies`.

## License

See [LICENSE](LICENSE).
