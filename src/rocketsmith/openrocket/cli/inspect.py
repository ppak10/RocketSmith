import typer

from pathlib import Path
from rich import print as rprint
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_inspect(app: typer.Typer):
    @app.command(name="inspect")
    def openrocket_inspect(
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
        """Read and display the component tree, CG, and CP from an .ork or .rkt file."""
        from rocketsmith.openrocket.components import inspect_rocket_file
        from rocketsmith.openrocket.ascii import render_rocket_ascii

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if not rocket_file_path.exists():
            rprint(f"⚠️  [yellow]Design file not found: {rocket_file_path}[/yellow]")
            raise typer.Exit(1)

        try:
            raw = inspect_rocket_file(rocket_file_path, jar)

            # Print the ASCII profile
            ascii_art = render_rocket_ascii(
                raw["components"],
                cg_x=raw.get("cg_x"),
                cp_x=raw.get("cp_x"),
                max_diameter=raw.get("max_diameter_m"),
            )
            rprint(ascii_art)

            # Print the component tree
            rprint("\n[bold]Component Tree:[/bold]")
            for comp in raw["components"]:
                indent = "  " * comp.get("depth", 0)
                rprint(f"{indent}• [cyan]{comp['type']}[/cyan]: {comp['name']}")

            # Print summary info
            rprint(f"\n[bold cyan]Rocket:[/bold cyan] {rocket_file_path.name}")
            if "stability_cal" in raw and raw["stability_cal"] is not None:
                rprint(f"[bold]Stability:[/bold] {raw['stability_cal']:.2f} cal")
            if "cg_x" in raw and raw["cg_x"] is not None:
                rprint(f"[bold]CG:[/bold] {raw['cg_x']*1000:.1f} mm from tip")
            if "cp_x" in raw and raw["cp_x"] is not None:
                rprint(f"[bold]CP:[/bold] {raw['cp_x']*1000:.1f} mm from tip")

        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to inspect design: {e}[/yellow]")
            raise typer.Exit(1)

    return openrocket_inspect
