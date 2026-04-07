from mcp.server.fastmcp import FastMCP


def register_build123d_render(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error, resolve_workspace

    @app.tool(
        name="build123d_render",
        title="Render STEP as PNG",
        description=(
            "Render a STEP file from a workspace as a 3-panel PNG image "
            "(side profile, aft end, isometric 45°) and save it alongside the STEP file. "
            "Returns the absolute path to the PNG — read it with the Read tool to visually "
            "inspect the part geometry. Far more informative than ASCII art for verifying "
            "length, fin geometry, bore diameter, and overall shape."
        ),
        structured_output=True,
    )
    async def build123d_render(
        step_filename: str,
        workspace_name: str | None = None,
        tolerance: float = 0.5,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Render a STEP file to a 3-panel PNG image.

        Args:
            step_filename: Name of the STEP file in the workspace parts/ folder
                           (e.g. "parts/nose_cone.step").
            workspace_name: The workspace name.
            tolerance: Tessellation tolerance in mm. Lower = finer mesh, slower.
                       0.5 gives good quality for rocket parts; use 0.2 for fine detail.
        """
        from rocketsmith.build123d.png import render_step_png

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        step_path = workspace.path / "parts" / Path(step_filename).name

        if not step_path.exists():
            return tool_error(
                f"STEP file not found: {step_path}",
                "FILE_NOT_FOUND",
                step_path=str(step_path),
            )

        png_path = step_path.with_suffix(".png")

        try:
            render_step_png(step_path, png_path, tolerance=tolerance)
        except ValueError as e:
            return tool_error(
                str(e),
                "RENDER_FAILED",
                step_path=str(step_path),
                exception_type="ValueError",
            )
        except Exception as e:
            return tool_error(
                "Failed to render STEP file as PNG",
                "RENDER_FAILED",
                step_path=str(step_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        return tool_success(
            {
                "png_path": str(png_path),
                "step_path": str(step_path),
                "panels": ["side profile", "aft end", "isometric 45°"],
                "message": "Read the PNG with the Read tool to visually inspect the part.",
            }
        )

    return build123d_render
