import typer

from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.database import PRESET_TYPES
from rocketsmith.openrocket.utils import get_openrocket_path


def register_openrocket_list_presets(app: typer.Typer):
    @app.command(name="list-presets")
    def openrocket_list_presets(
        preset_type: Annotated[
            str,
            typer.Argument(help=f"Component type. One of: {', '.join(PRESET_TYPES)}."),
        ],
        manufacturer: Annotated[
            str | None,
            typer.Option("--manufacturer", "-m", help="Filter by manufacturer name."),
        ] = None,
        openrocket_path: Annotated[
            str | None,
            typer.Option("--openrocket-path", help="Path to OpenRocket JAR or its parent directory."),
        ] = None,
    ) -> None:
        """List manufacturer component presets from the OpenRocket database."""
        from rocketsmith.openrocket.database import list_presets

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        try:
            presets = list_presets(jar, preset_type, manufacturer=manufacturer)
        except ValueError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"⚠️  [yellow]Failed to query presets: {e}[/yellow]")
            raise typer.Exit(1)

        if not presets:
            rprint("[yellow]No presets found.[/yellow]")
            return

        # Gather all dimension keys present across all presets
        dim_keys = []
        seen = set()
        for p in presets:
            for k in p:
                if k not in ("manufacturer", "part_no", "type", "description") and k not in seen:
                    dim_keys.append(k)
                    seen.add(k)

        table = Table(title=f"{preset_type} presets ({len(presets)} results)")
        table.add_column("Manufacturer", style="dim")
        table.add_column("Part No", style="bold cyan")
        for k in dim_keys:
            table.add_column(k.replace("_", " "), style="cyan")
        table.add_column("Description", style="dim", no_wrap=False)

        for p in presets:
            desc = p.get("description", "")
            if len(desc) > 60:
                desc = desc[:57] + "..."
            table.add_row(
                p["manufacturer"],
                p["part_no"],
                *[str(p.get(k, "")) for k in dim_keys],
                desc,
            )

        Console().print(table)

    return openrocket_list_presets
