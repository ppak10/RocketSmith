import typer

from pathlib import Path
from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_run_flight(app: typer.Typer):
    @app.command(name="run-flight")
    def openrocket_run_flight(
        rocket_file_path: Annotated[
            Path,
            typer.Argument(help="Path to the .ork or .rkt design file."),
        ],
        openrocket_path: Annotated[
            str | None,
            typer.Option(
                "--openrocket-path",
                help="Path to OpenRocket JAR or its parent directory.",
            ),
        ] = None,
    ) -> None:
        """Run all flight configs defined in an .ork or .rkt file."""
        from orhelper import FlightDataType, FlightEvent
        from rocketsmith.openrocket.simulation import run_simulation

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if not rocket_file_path.exists():
            rprint(f"⚠️  [yellow]Design file not found: {rocket_file_path}[/yellow]")
            raise typer.Exit(1)

        rprint(f"[blue]Running flights in:[/blue] [cyan]{rocket_file_path}[/cyan]")

        try:
            results = run_simulation(rocket_file_path, jar)
        except Exception as e:
            rprint(f"⚠️  [yellow]Flight failed: {e}[/yellow]")
            raise typer.Exit(1)

        table = Table(title=rocket_file_path.name)
        table.add_column("Flight", style="cyan")
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

    return openrocket_run_flight
