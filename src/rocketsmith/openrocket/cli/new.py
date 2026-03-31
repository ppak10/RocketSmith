import typer

from rich import print as rprint
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path
from wa.cli.options import WorkspaceOption
from wa.cli.utils import get_workspace


def register_openrocket_new(app: typer.Typer):
    @app.command(name="new")
    def openrocket_new(
        name: Annotated[
            str,
            typer.Argument(help="Name of the rocket and the output .ork file (without extension)."),
        ],
        workspace_option: WorkspaceOption = None,
        openrocket_path: Annotated[
            str | None,
            typer.Option("--openrocket-path", help="Path to OpenRocket JAR or its parent directory."),
        ] = None,
    ) -> None:
        """Create a new empty .ork file with one stage."""
        from rocketsmith.openrocket.components import new_ork

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        workspace = get_workspace(workspace_option)
        output_path = workspace.path / "openrocket" / f"{name}.ork"

        if output_path.exists():
            rprint(f"⚠️  [yellow]File already exists: {output_path}[/yellow]")
            raise typer.Exit(1)

        try:
            new_ork(name, output_path, jar)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to create .ork: {e}[/yellow]")
            raise typer.Exit(1)

        rprint(f"✅ Created [cyan]{output_path}[/cyan]")

    return openrocket_new
