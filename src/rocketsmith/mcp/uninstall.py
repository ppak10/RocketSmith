import json
import subprocess
import sys

from pathlib import Path
from rich import print as rprint


def uninstall(client: str) -> None:
    cmd = None
    match client:
        case "claude-code":
            cmd = ["claude", "mcp", "remove", "rocketsmith"]

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

            # Check if config file exists
            if not config_path.exists():
                rprint(f"[yellow]Config file not found at:[/yellow] {config_path}")
                rprint("[yellow]Nothing to uninstall.[/yellow]")
                return

            # Read existing config
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
            except json.JSONDecodeError:
                rprint(f"[red]Error reading config file at:[/red] {config_path}")
                return

            # Remove rocketsmith server
            if "mcpServers" in config and "rocketsmith" in config["mcpServers"]:
                del config["mcpServers"]["rocketsmith"]
                rprint("[blue]Removed 'rocketsmith' MCP server from config[/blue]")
            else:
                rprint(
                    "[yellow]'rocketsmith' MCP server not found in config[/yellow]"
                )

            # Write config back
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            rprint(
                f"[bold green]Successfully updated config at:[/bold green] {config_path}"
            )
            rprint(
                "[yellow]Note: Please restart Claude Desktop for changes to take effect.[/yellow]"
            )
            return

        case "gemini-cli":
            cmd = ["gemini", "mcp", "remove", "rocketsmith"]

        case "codex":
            cmd = ["codex", "mcp", "remove", "rocketsmith"]

        case _:
            rprint("[yellow]No client provided.[/yellow]\n")

    if cmd is not None:
        try:
            rprint(f"[blue]Running command:[/blue] {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

        except subprocess.CalledProcessError as e:
            rprint(f"[red]Command failed with return code {e.returncode}[/red]")
            rprint(f"[red]Error output: {e.stderr}[/red]" if e.stderr else "")
        except Exception as e:
            rprint(f"[red]Unexpected error running command:[/red] {e}")
