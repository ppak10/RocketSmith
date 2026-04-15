[![pytest](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml)
[![claude](https://github.com/ppak10/RocketSmith/actions/workflows/claude.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/claude.yml)
[![gemini](https://github.com/ppak10/RocketSmith/actions/workflows/gemini.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/gemini.yml)
[![codecov](https://codecov.io/github/ppak10/RocketSmith/graph/badge.svg?token=CODECOV_TOKEN)](https://codecov.io/github/ppak10/RocketSmith)

# <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.iconify.design/lucide/rocket.svg?color=white&width=32&height=32"><img src="https://api.iconify.design/lucide/rocket.svg?color=black&width=32&height=32" width="32" height="32" /></picture> RocketSmith

Let agents design, simulate, and build your rocket.

RocketSmith is an end-to-end model-rocket toolchain exposed as an MCP extension. It orchestrates **OpenRocket** (flight simulation), **build123d** (parametric CAD), and **PrusaSlicer** (FDM slicing) behind a single agent, and closes the loop by feeding real printed-part weights back into the simulation for post-build stability verification.

## Install

### Claude Code (plugin)

```bash
claude plugin install ppak10/RocketSmith
```

Registers the MCP server, agents, and skills automatically. Start a session in your project directory:

```
Use rocketsmith to design and build a stable rocket for a D12 motor
```

The agent calls `rocketsmith_setup` automatically, which starts the GUI server and opens the dashboard in your browser.

### Gemini CLI (extension)

```bash
gemini extensions install https://github.com/ppak10/RocketSmith
```

Then in a session:

```
@rocketsmith design and build a stable rocket for a D12 motor
```

## Requirements

- **Java runtime** — required by OpenRocket
- **OpenRocket 23.09** — uses [orhelper](https://github.com/SilentSys/orhelper), which targets the `net.sf.openrocket` package in OpenRocket 23.09 and earlier. OpenRocket 24+ is not supported.
- **PrusaSlicer** (optional — needed for the full CAD → print → mass calibration loop)

See [Installation](https://github.com/ppak10/RocketSmith/wiki/Installation) for platform-specific setup and troubleshooting.

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

### Building the GUI

The React/TypeScript frontend must be built before changes are reflected in production mode. The built files (`src/rocketsmith/data/gui/`) are committed to the repo so end users don't need to build them.

```bash
cd src/rocketsmith/gui/web
npm install
npm run build
```

## License

See [LICENSE](LICENSE).
