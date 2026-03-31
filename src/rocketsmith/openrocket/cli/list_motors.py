import typer

from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_list_motors(app: typer.Typer):
    @app.command(name="list-motors")
    def openrocket_list_motors(
        manufacturer: Annotated[
            str | None,
            typer.Option("--manufacturer", "-m", help="Filter by manufacturer name."),
        ] = None,
        impulse_class: Annotated[
            str | None,
            typer.Option("--class", "-c", help="Filter by impulse class letter (A, B, C, D, E, F, G, H, ...)."),
        ] = None,
        diameter: Annotated[
            float | None,
            typer.Option("--diameter", "-d", help="Filter by diameter in mm (e.g. 18, 24, 29, 38, 54)."),
        ] = None,
        motor_type: Annotated[
            str | None,
            typer.Option("--type", "-t", help="Filter by type: single-use, reloadable, hybrid."),
        ] = None,
        openrocket_path: Annotated[
            str | None,
            typer.Option("--openrocket-path", help="Path to OpenRocket JAR or its parent directory."),
        ] = None,
    ) -> None:
        """List available rocket motors from the OpenRocket database."""
        from rocketsmith.openrocket.database import list_motors

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        try:
            motors = list_motors(
                jar,
                manufacturer=manufacturer,
                impulse_class=impulse_class,
                diameter_mm=diameter,
                motor_type=motor_type,
            )
        except Exception as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if not motors:
            rprint("[yellow]No motors found matching the given filters.[/yellow]")
            return

        table = Table(title=f"Motors ({len(motors)} results)")
        table.add_column("Manufacturer", style="dim")
        table.add_column("Name", style="bold cyan")
        table.add_column("Type", style="dim")
        table.add_column("Dia (mm)")
        table.add_column("Len (mm)")
        table.add_column("Impulse (Ns)", style="cyan")
        table.add_column("Avg Thrust (N)")
        table.add_column("Burn (s)")
        table.add_column("Variants")

        for m in motors:
            table.add_row(
                m["manufacturer"],
                m["common_name"],
                m["type"],
                str(m["diameter_mm"]),
                str(m["length_mm"]),
                str(m["total_impulse_ns"]),
                str(m["avg_thrust_n"]),
                str(m["burn_time_s"]),
                str(m["variant_count"]),
            )

        Console().print(table)

    return openrocket_list_motors
