from mcp.server.fastmcp import FastMCP


def register_build123d_render(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="build123d_render",
        title="Render STEP as PNG",
        description=(
            "Render a STEP file as a 3-panel PNG image "
            "(side profile, aft end, isometric 45°). "
            "Returns the absolute path to the PNG — read it with the Read tool to visually "
            "inspect the part geometry. Far more informative than ASCII art for verifying "
            "length, fin geometry, bore diameter, and overall shape."
        ),
        structured_output=True,
    )
    async def build123d_render(
        step_file_path: Path,
        out_path: Path | None = None,
        tolerance: float = 0.5,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Render a STEP file to a 3-panel PNG image.

        Args:
            step_file_path: Path to the STEP file.
            out_path: Path to save the PNG. Defaults to step_file_path with .png extension.
            tolerance: Tessellation tolerance in mm. Lower = finer mesh, slower.
                       0.5 gives good quality for rocket parts; use 0.2 for fine detail.
        """
        from rocketsmith.build123d.png import render_step_png

        step_file_path = resolve_path(step_file_path)
        if out_path is not None:
            out_path = resolve_path(out_path)
        if not step_file_path.exists():
            return tool_error(
                f"STEP file not found: {step_file_path}",
                "FILE_NOT_FOUND",
                step_file_path=str(step_file_path),
            )

        png_path = (
            out_path if out_path is not None else step_file_path.with_suffix(".png")
        )

        try:
            render_step_png(step_file_path, png_path, tolerance=tolerance)
        except ValueError as e:
            return tool_error(
                str(e),
                "RENDER_FAILED",
                step_file_path=str(step_file_path),
                exception_type="ValueError",
            )
        except Exception as e:
            return tool_error(
                "Failed to render STEP file as PNG",
                "RENDER_FAILED",
                step_file_path=str(step_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        return tool_success(
            {
                "png_path": str(png_path),
                "step_file_path": str(step_file_path),
                "panels": ["side profile", "aft end", "isometric 45°"],
                "message": "Read the PNG with the Read tool to visually inspect the part.",
            }
        )

    return build123d_render
