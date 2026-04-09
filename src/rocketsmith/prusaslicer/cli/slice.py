import typer

from pathlib import Path
from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.prusaslicer.models import Material
from rocketsmith.prusaslicer.utils import get_prusaslicer_path


def register_prusaslicer_slice(app: typer.Typer):
    @app.command(name="slice")
    def prusaslicer_slice(
        model_file_path: Annotated[
            Path,
            typer.Argument(help="Path to the model file (.stl, .step, .3mf, .obj)."),
        ],
        out_path: Annotated[
            Path | None,
            typer.Option(
                "--out",
                help="Path to save the .gcode output. Defaults to model file with .gcode extension.",
            ),
        ] = None,
        material: Annotated[
            Material,
            typer.Option(
                "--material",
                help="Filament material for weight calculation.",
            ),
        ] = Material.PLA,
        prusaslicer_path: Annotated[
            str | None,
            typer.Option(
                "--prusaslicer-path",
                help="Path to the PrusaSlicer executable.",
            ),
        ] = None,
        config_path: Annotated[
            Path | None,
            typer.Option(
                "--config",
                help="Path to a PrusaSlicer .ini config file.",
            ),
        ] = None,
    ) -> None:
        """Slice a 3D model file using PrusaSlicer."""
        from rocketsmith.prusaslicer.slice import slice as ps_slice

        try:
            exe = get_prusaslicer_path(prusaslicer_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if not model_file_path.exists():
            rprint(f"⚠️  [yellow]Model file not found: {model_file_path}[/yellow]")
            raise typer.Exit(1)

        output_path = (
            out_path if out_path is not None else model_file_path.with_suffix(".gcode")
        )

        rprint(f"[blue]Slicing:[/blue] [cyan]{model_file_path}[/cyan]")

        try:
            result = ps_slice(
                model_path=model_file_path,
                output_path=output_path,
                config_path=config_path,
                prusaslicer_path=exe,
                material=material,
            )
        except Exception as e:
            rprint(f"⚠️  [yellow]Slicing failed: {e}[/yellow]")
            raise typer.Exit(1)

        table = Table(title=model_file_path.name)
        table.add_column("G-code", style="cyan")
        table.add_column("Material", justify="right")
        table.add_column("Print Time", justify="right")
        table.add_column("Filament", justify="right")
        table.add_column("Layers", justify="right")

        def _fmt_time(seconds: float | None) -> str:
            if seconds is None:
                return "—"
            h, rem = divmod(int(seconds), 3600)
            m, s = divmod(rem, 60)
            parts = []
            if h:
                parts.append(f"{h}h")
            if m:
                parts.append(f"{m}m")
            parts.append(f"{s}s")
            return " ".join(parts)

        filament = "—"
        if result.filament_used_cm3 is not None or result.filament_used_g is not None:
            parts = []
            if result.filament_used_cm3 is not None:
                parts.append(f"{result.filament_used_cm3:.1f} cm³")
            if result.filament_used_g is not None:
                parts.append(f"{result.filament_used_g:.1f} g")
            filament = " / ".join(parts)

        table.add_row(
            result.gcode_path.name,
            result.material.value.upper(),
            _fmt_time(result.print_time_seconds),
            filament,
            str(result.total_layers) if result.total_layers is not None else "—",
        )

        Console().print(table)

    return prusaslicer_slice
