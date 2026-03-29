import json
import subprocess
import sys

from pathlib import Path
from rich import print as rprint


def install(path: Path, client: str, include_agent: bool = True) -> None:
    match client:
        case "claude-code":
            cmd = [
                "claude",
                "mcp",
                "add-json",
                "rocketsmith",
                f'{{"command": "uv", "args": ["--directory", "{path}", "run", "-m", "rocketsmith.mcp"]}}',
            ]

        case "claude-desktop":
            # Determine config file path based on platform
            if sys.platform == "darwin":
                config_path = (
                    Path.home()
                    / "Library"
                    / "Application Support"
                    / "Claude"
                    / "claude_desktop_config.json"
                )
            elif sys.platform == "win32":
                config_path = (
                    Path.home()
                    / "AppData"
                    / "Roaming"
                    / "Claude"
                    / "claude_desktop_config.json"
                )
            else:  # Linux
                config_path = (
                    Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
                )

            # Ensure config directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Read existing config or create new one
            if config_path.exists():
                with open(config_path, "r") as f:
                    config = json.load(f)
                rprint(f"[blue]Found existing config at:[/blue] {config_path}")
            else:
                config = {}
                rprint(f"[yellow]Creating new config at:[/yellow] {config_path}")

            # Ensure mcpServers section exists
            if "mcpServers" not in config:
                config["mcpServers"] = {}

            # Add rocketsmith server
            rprint("[blue]Adding 'rocketsmith' MCP server to config...[/blue]")
            config["mcpServers"]["rocketsmith"] = {
                "command": "uv",
                "args": ["--directory", str(path), "run", "-m", "rocketsmith.mcp"],
            }

            # Write config back
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            rprint(
                f"[bold green]Successfully updated config at:[/bold green] {config_path}"
            )
            rprint(
                "[yellow]Note: Please restart Claude Desktop for changes to take effect.[/yellow]"
            )

            # Skip agent installation as Claude Desktop doesn't support custom agents
            if include_agent:
                rprint(
                    "[yellow]Note: Claude Desktop does not support custom agents like Claude Code does.[/yellow]"
                )

            return  # Early return since we don't need to run subprocess command

        case "gemini-cli":
            cmd = [
                "gemini",
                "mcp",
                "add",
                "rocketsmith",
                "uv",
                "--directory",
                f"{path}",
                "run",
                "-m",
                "rocketsmith.mcp",
            ]

        case "codex":
            cmd = [
                "codex",
                "mcp",
                "add",
                "rocketsmith",
                "uv",
                "--directory",
                f"{path}",
                "run",
                "-m",
                "rocketsmith.mcp",
            ]

        case _:
            rprint("[yellow]No client provided.[/yellow]")

    try:
        rprint(f"[blue]Running command:[/blue] {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        rprint(f"[red]Command failed with return code {e.returncode}[/red]")
        rprint(f"[red]Error output: {e.stderr}[/red]" if e.stderr else "")
    except Exception as e:
        rprint(f"[red]Unexpected error running command:[/red] {e}")
