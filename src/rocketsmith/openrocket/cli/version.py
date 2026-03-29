import re
import typer

from pathlib import Path
from rich import print as rprint
from typing_extensions import Annotated


def register_openrocket_version(app: typer.Typer):
    @app.command(name="version")
    def openrocket_version(
        openrocket_path: Annotated[
            Path | None,
            typer.Option(
                "--openrocket-path",
                help="Path to OpenRocket JAR or its parent directory.",
            ),
        ] = None,
    ) -> None:
        """Show the installed version of OpenRocket."""
        from rocketsmith.openrocket.utils import get_openrocket_path

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        match = re.search(r"OpenRocket-?([\d.]+)\.jar", jar.name, re.IGNORECASE)
        version = match.group(1) if match else "unknown"

        rprint(f"✅ OpenRocket [bold]{version}[/bold] found at: [cyan]{jar}[/cyan]")

    return openrocket_version
