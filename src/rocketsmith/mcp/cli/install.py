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
        include_agent: Annotated[bool, typer.Option("--include-agent")] = False,
        project_path: Annotated[str | None, typer.Option("--project-path")] = None,
        dev: Annotated[bool, typer.Option("--dev")] = False,
    ) -> None:
        import rocketsmith

        # Determine project root path
        if dev:
            rocketsmith_path = Path(rocketsmith.__file__).parents[2]
        elif project_path:
            rocketsmith_path = Path(project_path)
        else:
            # Path(rocketsmith.__file__) example:
            # /GitHub/rocketsmith-agent/.venv/lib/python3.13/site-packages/rocketsmith
            # Going up 5 levels to get to the project root
            rocketsmith_path = Path(rocketsmith.__file__).parents[5]

        rprint(
            f"[bold green]Using `rocketsmith` packaged under project path:[/bold green] {rocketsmith_path}"
        )

        install(rocketsmith_path, client=client, include_agent=include_agent)

    _ = app.command(name="install")(mcp_install)
    return mcp_install
