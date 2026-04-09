import typer

from pathlib import Path
from rich import print as rprint
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_delete_component(app: typer.Typer):
    @app.command(name="delete-component")
    def openrocket_delete_component(
        rocket_file_path: Annotated[
            Path,
            typer.Argument(help="Path to the .ork or .rkt design file."),
        ],
        component_name: Annotated[
            str,
            typer.Argument(
                help="Name of the component to delete (as shown by inspect)."
            ),
        ],
        openrocket_path: Annotated[
            str | None,
            typer.Option(
                "--openrocket-path",
                help="Path to OpenRocket JAR or its parent directory.",
            ),
        ] = None,
    ) -> None:
        """Remove a component from an .ork or .rkt file by name."""
        from rocketsmith.openrocket.components import delete_component

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if not rocket_file_path.exists():
            rprint(f"⚠️  [yellow]Design file not found: {rocket_file_path}[/yellow]")
            raise typer.Exit(1)

        try:
            deleted = delete_component(rocket_file_path, component_name, jar)
        except ValueError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to delete component: {e}[/yellow]")
            raise typer.Exit(1)

        rprint(
            f"✅ Deleted [cyan]{deleted}[/cyan] from [cyan]{rocket_file_path.name}[/cyan]"
        )

    return openrocket_delete_component
