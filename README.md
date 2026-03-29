[![pytest](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml)

# <picture><source media="(prefers-color-scheme: dark)" srcset="https://api.iconify.design/lucide/rocket.svg?color=white&width=32&height=32"><img src="https://api.iconify.design/lucide/rocket.svg?color=black&width=32&height=32" width="32" height="32" /></picture> RocketSmith

Let agents design, simulate, and build your rocket.

## Getting Started
### Installation

```bash
uv add rocketsmith
```

### Agent
#### Claude Code

1. Install MCP tools and Agent

```bash
rocketsmith mcp install
```

#### Claude Desktop

1. Install MCP tools

```bash
rocketsmith mcp install claude-desktop --project-path /path/to/RocketSmith
```

Note: After installation, restart Claude Desktop for the changes to take effect.

### CLI (`rocketsmith --help`)
#### Create Workspace (via `workspace-agent`)
```bash
rocketsmith workspace create <workspace-name>
```
