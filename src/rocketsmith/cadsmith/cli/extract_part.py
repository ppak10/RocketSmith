import typer

from pathlib import Path
from typing_extensions import Annotated
from rich import print as rprint
from rich.table import Table
from rich.console import Console


def register_cadsmith_extract_part(app: typer.Typer):
    @app.command(name="extract-part")
    def cadsmith_extract_part(
        file_path: Annotated[
            Path,
            typer.Argument(help="Path to the STEP (.step/.stp) or BREP (.brep) file."),
        ],
        density: Annotated[
            float | None,
            typer.Option(
                "--density",
                help="Material density in kg/m³. When provided, mass is calculated from volume × density.",
            ),
        ] = None,
    ) -> None:
        """Extract and display geometric properties from a STEP or BREP file."""
        from rocketsmith.cadsmith.extract_part import extract_part

        if not file_path.exists():
            rprint(f"⚠️  [yellow]File not found: {file_path}[/yellow]")
            raise typer.Exit(1)

        rprint(f"[dim]Analysing [cyan]{file_path.name}[/cyan]...[/dim]")

        try:
            part = extract_part(file_path, material_density_kg_m3=density)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to extract part geometry: {e}[/yellow]")
            raise typer.Exit(1)

        table = Table(
            title=str(file_path.name), show_header=False, box=None, padding=(0, 2)
        )
        table.add_column("Property", style="dim")
        table.add_column("Value", style="cyan")

        bb = part.bounding_box
        com = part.center_of_mass
        table.add_row("Volume", f"{part.volume:,.2f~}")
        table.add_row("Surface area", f"{part.surface_area:,.2f~}")
        table.add_row(
            "Bounding box",
            f"{bb.x.magnitude:.2f} × {bb.y.magnitude:.2f} × {bb.z.magnitude:.2f} {bb.x.units:~}",
        )
        table.add_row(
            "Centre of mass",
            f"({com.x.magnitude:.3f}, {com.y.magnitude:.3f}, {com.z.magnitude:.3f}) {com.x.units:~}",
        )
        if part.mass is not None:
            table.add_row("Mass", f"{part.mass:.2f~}  (at {density:.0f} kg/m³)")

        Console().print(table)

    return cadsmith_extract_part
