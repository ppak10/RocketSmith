import typer

from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path
from wa.cli.options import WorkspaceOption
from wa.cli.utils import get_workspace


def register_openrocket_run_simulation(app: typer.Typer):
    @app.command(name="run-simulation")
    def openrocket_run_simulation(
        filename: Annotated[
            str,
            typer.Argument(
                help="Filename of the .ork or .rkt design file in the workspace openrocket/ folder."
            ),
        ],
        workspace_option: WorkspaceOption = None,
        openrocket_path: Annotated[
            str | None,
            typer.Option(
                "--openrocket-path",
                help="Path to OpenRocket JAR or its parent directory.",
            ),
        ] = None,
    ) -> None:
        """Run all simulations defined in an .ork or .rkt file."""
        from orhelper import FlightDataType, FlightEvent
        from rocketsmith.openrocket.simulation import run_simulation

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        workspace = get_workspace(workspace_option)

        if not (filename.endswith(".ork") or filename.endswith(".rkt")):
            filename += ".ork"

        file_path = workspace.path / "openrocket" / filename

        if not file_path.exists():
            rprint(f"⚠️  [yellow]Design file not found: {file_path}[/yellow]")
            raise typer.Exit(1)

        rprint(f"[blue]Running simulations in:[/blue] [cyan]{file_path}[/cyan]")

        try:
            results = run_simulation(file_path, jar)
        except Exception as e:
            rprint(f"⚠️  [yellow]Simulation failed: {e}[/yellow]")
            raise typer.Exit(1)

        table = Table(title=filename)
        table.add_column("Simulation", style="cyan")
        table.add_column("Max Altitude", justify="right")
        table.add_column("Max Velocity", justify="right")
        table.add_column("Time to Apogee", justify="right")
        table.add_column("Flight Time", justify="right")

        for r in results:
            max_alt = float(r.timeseries[FlightDataType.TYPE_ALTITUDE].max())
            max_vel = float(r.timeseries[FlightDataType.TYPE_VELOCITY_TOTAL].max())
            flight_time = float(r.timeseries[FlightDataType.TYPE_TIME][-1])

            apogee_times = r.events.get(FlightEvent.APOGEE, [])
            time_to_apogee = f"{apogee_times[0]:.2f} s" if apogee_times else "—"

            table.add_row(
                r.name,
                f"{max_alt:.1f} m  ({max_alt * 3.28084:.1f} ft)",
                f"{max_vel:.1f} m/s",
                time_to_apogee,
                f"{flight_time:.2f} s",
            )

        Console().print(table)

    return openrocket_run_simulation
