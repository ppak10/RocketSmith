[![pytest](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml/badge.svg)](https://github.com/ppak10/RocketSmith/actions/workflows/pytest.yml)

# RocketSmith <img src="https://cdn.jsdelivr.net/npm/lucide-static/icons/rocket.svg" width="32" height="32" />

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
