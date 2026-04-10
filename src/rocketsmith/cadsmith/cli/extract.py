import typer

from pathlib import Path
from typing_extensions import Annotated
from rich import print as rprint
from rich.table import Table
from rich.console import Console


def register_cadsmith_extract(app: typer.Typer):
    @app.command(name="extract")
    def cadsmith_extract(
        step_file_path: Annotated[
            Path,
            typer.Argument(help="Path to the STEP file."),
        ],
        density: Annotated[
            float | None,
            typer.Option(
                "--density",
                help="Material density in kg/m³. When provided, mass is calculated from volume × density.",
            ),
        ] = None,
    ) -> None:
        """Extract and display geometric properties from a STEP file."""
        from rocketsmith.cadsmith.extract import extract_geometry

        if not step_file_path.exists():
            rprint(f"⚠️  [yellow]File not found: {step_file_path}[/yellow]")
            raise typer.Exit(1)

        rprint(f"[dim]Analysing [cyan]{step_file_path.name}[/cyan]...[/dim]")

        try:
            geo = extract_geometry(step_file_path, material_density_kg_m3=density)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to extract geometry: {e}[/yellow]")
            raise typer.Exit(1)

        table = Table(
            title=str(step_file_path.name), show_header=False, box=None, padding=(0, 2)
        )
        table.add_column("Property", style="dim")
        table.add_column("Value", style="cyan")

        table.add_row(
            "Volume", f"{geo.volume_mm3:,.2f} mm³  ({geo.volume_cm3:.3f} cm³)"
        )
        table.add_row("Surface area", f"{geo.surface_area_mm2:,.2f} mm²")
        table.add_row(
            "Bounding box",
            f"{geo.bounding_box_mm.x_mm:.2f} × {geo.bounding_box_mm.y_mm:.2f} × {geo.bounding_box_mm.z_mm:.2f} mm",
        )
        table.add_row(
            "Centre of mass",
            f"({geo.center_of_mass_mm.x_mm:.3f}, {geo.center_of_mass_mm.y_mm:.3f}, {geo.center_of_mass_mm.z_mm:.3f}) mm",
        )
        if geo.mass_g is not None:
            table.add_row("Mass", f"{geo.mass_g:.2f} g  (at {density:.0f} kg/m³)")

        Console().print(table)

    return cadsmith_extract
