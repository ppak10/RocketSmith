import typer

from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_list_materials(app: typer.Typer):
    @app.command(name="list-materials")
    def openrocket_list_materials(
        material_type: Annotated[
            str,
            typer.Argument(help="Material type: bulk, surface, or line."),
        ],
        openrocket_path: Annotated[
            str | None,
            typer.Option("--openrocket-path", help="Path to OpenRocket JAR or its parent directory."),
        ] = None,
    ) -> None:
        """List structural materials from the OpenRocket database."""
        from rocketsmith.openrocket.database import list_materials

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        try:
            materials = list_materials(jar, material_type)
        except ValueError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to query materials: {e}[/yellow]")
            raise typer.Exit(1)

        density_unit = {"bulk": "kg/m³", "surface": "kg/m²", "line": "kg/m"}.get(material_type, "")

        table = Table(title=f"{material_type.title()} Materials ({len(materials)} results)")
        table.add_column("Name", style="bold cyan")
        table.add_column(f"Density ({density_unit})", style="cyan")

        for m in materials:
            table.add_row(m["name"], str(m["density"]))

        Console().print(table)

    return openrocket_list_materials
