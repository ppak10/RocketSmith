import typer

from typing_extensions import Annotated
from pathlib import Path
from rich import print as rprint

from rocketsmith.mcp.install import install


def register_mcp_install(app: typer.Typer):
    @app.command(name="install")
    def mcp_install(
        client: Annotated[
            str,
            typer.Argument(
                help="Target client to install for. Options: claude-code, claude-desktop, gemini-cli, codex"
            ),
        ] = "claude-code",
        tools_only: Annotated[
            bool,
            typer.Option("--tools-only", help="Register MCP tools only; skip agent file installation."),
        ] = False,
        project_path: Annotated[str | None, typer.Option("--project-path")] = None,
        agent_path: Annotated[
            str | None,
            typer.Option(
                "--agent-path",
                help="Directory to install the agent file into. Defaults to the current working directory.",
            ),
        ] = None,
        dev: Annotated[bool, typer.Option("--dev")] = False,
    ) -> None:
        import rocketsmith

        # Determine project root path for MCP server registration
        if dev:
            rocketsmith_path = Path(rocketsmith.__file__).parents[2]
        elif project_path:
            rocketsmith_path = Path(project_path)
        else:
            # Path(rocketsmith.__file__) example:
            # /GitHub/rocketsmith-agent/.venv/lib/python3.13/site-packages/rocketsmith
            # Going up 5 levels to get to the project root
            rocketsmith_path = Path(rocketsmith.__file__).parents[5]

        # Agent file always goes into the user's current project directory
        resolved_agent_path = Path(agent_path) if agent_path else Path.cwd()

        rprint(
            f"[bold green]Using `rocketsmith` packaged under project path:[/bold green] {rocketsmith_path}"
        )

        install(rocketsmith_path, client=client, tools_only=tools_only, agent_path=resolved_agent_path)

    _ = app.command(name="install")(mcp_install)
    return mcp_install
