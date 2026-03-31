import typer

from rich import print as rprint
from rich.table import Table
from rich.console import Console
from typing_extensions import Annotated

from rocketsmith.openrocket.components import COMPONENT_TYPES
from rocketsmith.openrocket.utils import get_openrocket_path
from wa.cli.options import WorkspaceOption
from wa.cli.utils import get_workspace


def register_openrocket_create_component(app: typer.Typer):
    @app.command(name="create-component")
    def openrocket_create_component(
        ork_filename: Annotated[
            str,
            typer.Argument(help="Filename of the .ork file in the workspace openrocket/ folder."),
        ],
        component_type: Annotated[
            str,
            typer.Argument(
                help=f"Component type to add. One of: {', '.join(COMPONENT_TYPES)}."
            ),
        ],
        workspace_option: WorkspaceOption = None,
        openrocket_path: Annotated[
            str | None,
            typer.Option("--openrocket-path", help="Path to OpenRocket JAR or its parent directory."),
        ] = None,
        name: Annotated[str | None, typer.Option("--name", help="Component name.")] = None,
        parent: Annotated[str | None, typer.Option("--parent", help="Parent component name. Defaults to first stage (external) or last body tube (internal).")] = None,
        length: Annotated[float | None, typer.Option("--length", help="Length in meters.")] = None,
        diameter: Annotated[float | None, typer.Option("--diameter", help="Diameter in meters (base for nose-cone, outer for body-tube).")] = None,
        thickness: Annotated[float | None, typer.Option("--thickness", help="Wall thickness in meters.")] = None,
        shape: Annotated[str | None, typer.Option("--shape", help="Nose-cone/transition shape: ogive, conical, ellipsoid, power, parabolic, haack.")] = None,
        fore_diameter: Annotated[float | None, typer.Option("--fore-diameter", help="Fore diameter in meters (transition only).")] = None,
        aft_diameter: Annotated[float | None, typer.Option("--aft-diameter", help="Aft diameter in meters (transition only).")] = None,
        count: Annotated[int | None, typer.Option("--count", help="Fin count (fin-set only).")] = None,
        root_chord: Annotated[float | None, typer.Option("--root-chord", help="Fin root chord in meters.")] = None,
        tip_chord: Annotated[float | None, typer.Option("--tip-chord", help="Fin tip chord in meters.")] = None,
        span: Annotated[float | None, typer.Option("--span", help="Fin span in meters.")] = None,
        sweep: Annotated[float | None, typer.Option("--sweep", help="Fin sweep length in meters.")] = None,
        cd: Annotated[float | None, typer.Option("--cd", help="Parachute drag coefficient.")] = None,
        mass: Annotated[float | None, typer.Option("--mass", help="Mass in kg (mass component only).")] = None,
    ) -> None:
        """Add a new component to an existing .ork file."""
        from rocketsmith.openrocket.components import create_component

        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        workspace = get_workspace(workspace_option)
        ork_path = workspace.path / "openrocket" / ork_filename

        if not ork_path.exists():
            rprint(f"⚠️  [yellow].ork file not found: {ork_path}[/yellow]")
            raise typer.Exit(1)

        try:
            info = create_component(
                ork_path=ork_path,
                component_type=component_type,
                jar_path=jar,
                parent_name=parent,
                name=name,
                length=length,
                diameter=diameter,
                thickness=thickness,
                shape=shape,
                fore_diameter=fore_diameter,
                aft_diameter=aft_diameter,
                count=count,
                root_chord=root_chord,
                tip_chord=tip_chord,
                span=span,
                sweep=sweep,
                cd=cd,
                mass=mass,
            )
        except (ValueError, Exception) as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        table = Table(title=f"Created {info['type']}  —  {info['name']}")
        table.add_column("Property", style="dim")
        table.add_column("Value", style="cyan")
        for key, value in info.items():
            if key in ("type", "name"):
                continue
            table.add_row(key, str(value))

        Console().print(table)
        rprint(f"✅ Saved [cyan]{ork_path.name}[/cyan]")

    return openrocket_create_component
