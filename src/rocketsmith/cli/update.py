import typer

from pathlib import Path
from typing_extensions import Annotated
from rich import print as rprint


def register_update(app: typer.Typer):
    @app.command(name="update")
    def rocketsmith_update(
        tools_only: Annotated[
            bool,
            typer.Option(
                "--tools-only",
                help="Upgrade the package only; skip overwriting the agent file.",
            ),
        ] = False,
        project_path: Annotated[
            str | None,
            typer.Option(
                "--project-path",
                help="Project directory to run the upgrade in. Defaults to the current working directory.",
            ),
        ] = None,
    ) -> None:
        """Upgrade rocketsmith to the latest PyPI release and refresh the agent file."""
        from rocketsmith.mcp.update import update

        path = Path(project_path) if project_path else Path.cwd()
        rprint(f"[bold green]Project path:[/bold green] {path}")

        success = update(path, tools_only=tools_only)
        if not success:
            raise typer.Exit(1)

    return rocketsmith_update
