import typer

from typing_extensions import Annotated

from wa.cli.options import WorkspaceOption
from wa.cli.utils import get_workspace


def register_build123d_visualize(app: typer.Typer):
    @app.command(name="visualize")
    def build123d_visualize(
        step_filename: Annotated[
            str,
            typer.Argument(
                help="Filename of the STEP file in the workspace parts/ folder."
            ),
        ],
        workspace_option: WorkspaceOption = None,
        wireframe: Annotated[
            bool,
            typer.Option(
                "--wireframe", help="Render edges only instead of shaded faces."
            ),
        ] = False,
        angle: Annotated[
            float | None,
            typer.Option(
                "--angle",
                help="Render a single static frame at this Y-axis angle (degrees). "
                "Omit to animate continuously.",
            ),
        ] = None,
        fps: Annotated[
            float,
            typer.Option("--fps", help="Animation frames per second."),
        ] = 12.0,
        speed: Annotated[
            float,
            typer.Option("--speed", help="Rotation speed in degrees per second."),
        ] = 36.0,
        tolerance: Annotated[
            float,
            typer.Option(
                "--tolerance",
                help="Mesh tessellation tolerance in mm. Lower = finer detail (slower).",
            ),
        ] = 1.0,
    ) -> None:
        """Render a STEP file as ASCII art using isometric projection.

        Animates a continuous Y-axis rotation by default. Pass --angle to
        render a single static frame instead.
        """
        from rich import print as rprint
        from rocketsmith.build123d.ascii import render_step_ascii, animate_step_ascii

        workspace = get_workspace(workspace_option)
        step_path = workspace.path / "parts" / step_filename

        if not step_path.exists():
            rprint(f"[yellow]File not found: {step_path}[/yellow]")
            raise typer.Exit(1)

        if angle is not None:
            frame = render_step_ascii(
                step_path,
                angle_deg=angle,
                wireframe=wireframe,
                tolerance=tolerance,
            )
            print(frame)
        else:
            animate_step_ascii(
                step_path,
                wireframe=wireframe,
                fps=fps,
                degrees_per_second=speed,
                tolerance=tolerance,
            )

    return build123d_visualize
