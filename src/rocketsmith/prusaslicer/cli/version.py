import subprocess
import typer

from pathlib import Path
from rich import print as rprint
from typing_extensions import Annotated

from rocketsmith.prusaslicer.utils import get_prusaslicer_path


def register_prusaslicer_version(app: typer.Typer):
    @app.command(name="version")
    def prusaslicer_version(
        prusaslicer_path: Annotated[
            Path | None,
            typer.Option(
                "--prusaslicer-path",
                help="Path to the PrusaSlicer executable.",
            ),
        ] = None,
    ) -> None:
        """Show the installed version of PrusaSlicer."""
        try:
            exe = get_prusaslicer_path(prusaslicer_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True,
            text=True,
        )
        version = (result.stdout or result.stderr).strip()
        rprint(f"✅ [bold]{version}[/bold] found at: [cyan]{exe}[/cyan]")

    return prusaslicer_version
