from mcp.server.fastmcp import FastMCP


def register_build123d_visualize(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        name="build123d_visualize",
        title="Visualize STEP as ASCII",
        description=(
            "Render a STEP file from a workspace as isometric ASCII art. "
            "Use storyboard=true to show four 90°-apart views in a grid — "
            "the best option for agents since MCP cannot animate. "
            "For a single static frame use angle_deg. "
            "Shaded by default; pass wireframe=true for edge-only rendering."
        ),
        structured_output=True,
    )
    async def build123d_visualize(
        step_path: Path,
        storyboard: bool = False,
        angle_deg: float = 0.0,
        wireframe: bool = False,
        width: int = 80,
        height: int = 120,
        tolerance: float = 1.0,
    ) -> Union[ToolSuccess[str], ToolError]:
        """
        Render a STEP file as isometric ASCII art.

        Args:
            step_path: Path to the STEP file (typically inside a workspace).
            storyboard: If true, render four views (0°/90°/180°/270°) in a 2×2
                grid. Recommended for agents — gives a full 360° impression in
                one call. Overrides angle_deg when set.
            angle_deg: Y-axis rotation angle in degrees (0–360). Only used when
                storyboard is false.
            wireframe: Render edges only if true. Default is shaded faces.
            width: Total output width in characters (default 80).
            height: Total storyboard height budget in rows (default 120). The
                frame height is derived automatically from the mesh's projected
                aspect ratio; this value caps the total output so it stays
                readable. Ignored when storyboard is false (use height directly
                for single-frame renders).
            tolerance: Tessellation tolerance in mm. Lower = finer mesh, slower.
        """
        from rocketsmith.build123d.ascii import render_step_ascii, render_storyboard

        try:
            if storyboard:
                ascii_art = render_storyboard(
                    step_path,
                    total_width=width,
                    total_height=height,
                    wireframe=wireframe,
                    tolerance=tolerance,
                )
            else:
                ascii_art = render_step_ascii(
                    step_path,
                    angle_deg=angle_deg,
                    width=width,
                    height=height,
                    wireframe=wireframe,
                    tolerance=tolerance,
                )
            return tool_success(ascii_art)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                step_path=str(step_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to render STEP file as ASCII",
                "RENDER_FAILED",
                step_path=str(step_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    return build123d_visualize
