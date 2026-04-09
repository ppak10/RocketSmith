import typer

from pathlib import Path
from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_read_component(app: typer.Typer):
    @app.command(name="read-component")
    def openrocket_read_component(
        rocket_file_path: Annotated[
            Path,
            typer.Argument(help="Path to the .ork or .rkt design file."),
        ],
        component_name: Annotated[
            str,
            typer.Argument(help="Name of the component to read (as shown by inspect)."),
        ],
        openrocket_path: Annotated[
            str | None,
            typer.Option(
                "--openrocket-path",
                help="Path to OpenRocket JAR or its parent directory.",
            ),
        ] = None,
    ) -> None:
        """Display all properties of a single component by name from an .ork or .rkt file."""
        from rocketsmith.openrocket.components import read_component

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if not rocket_file_path.exists():
            rprint(f"⚠️  [yellow]Design file not found: {rocket_file_path}[/yellow]")
            raise typer.Exit(1)

        try:
            info = read_component(rocket_file_path, component_name, jar)
        except ValueError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to read component: {e}[/yellow]")
            raise typer.Exit(1)

        table = Table(title=f"{info['type']}  —  {info['name']}")
        table.add_column("Property", style="dim")
        table.add_column("Value", style="cyan")

        for key, value in info.items():
            if key in ("type", "name"):
                continue
            table.add_row(key, str(value))

        Console().print(table)

    return openrocket_read_component
