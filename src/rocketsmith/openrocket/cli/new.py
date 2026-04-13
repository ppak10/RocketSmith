import typer

from pathlib import Path
from rich import print as rprint
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_new(app: typer.Typer):
    @app.command(name="new")
    def openrocket_new(
        name: Annotated[
            str,
            typer.Argument(help="Name of the rocket (stored inside the .ork file)."),
        ],
        out_path: Annotated[
            Path | None,
            typer.Option(
                "--out",
                help="Path to save the .ork file. Defaults to {name}.ork in the current directory.",
            ),
        ] = None,
        openrocket_path: Annotated[
            str | None,
            typer.Option(
                "--openrocket-path",
                help="Path to OpenRocket JAR or its parent directory.",
            ),
        ] = None,
    ) -> None:
        """Create a new empty .ork file with one stage."""
        from rocketsmith.openrocket.components import new_ork

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if out_path is None:
            out_path = Path.cwd() / f"{name}.ork"

        if not str(out_path).endswith(".ork"):
            out_path = out_path.with_suffix(".ork")

        if out_path.exists():
            rprint(f"⚠️  [yellow]File already exists: {out_path}[/yellow]")
            raise typer.Exit(1)

        try:
            new_ork(name, out_path, jar)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to create .ork: {e}[/yellow]")
            raise typer.Exit(1)

        rprint(f"✅ Created [cyan]{out_path}[/cyan]")

    return openrocket_new
