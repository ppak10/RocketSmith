from mcp.server.fastmcp import FastMCP


def register_build123d_render(app: FastMCP):
    from pathlib import Path
    from typing import Literal, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="build123d_render",
        title="Render STEP file",
        description=(
            "Render a STEP file for visual inspection. "
            'format="image" produces a 3-panel PNG (side profile, aft end, isometric 45°) '
            "— read the returned path with the Read tool to inspect geometry. "
            'format="ascii" produces isometric ASCII art inline — '
            "use storyboard=true for a 4-view grid, or angle_deg for a single frame. "
            "Shaded by default; pass wireframe=true for edge-only rendering."
        ),
        structured_output=True,
    )
    async def build123d_render(
        step_file_path: Path,
        format: Literal["image", "ascii"] = "image",
        # --- ascii-specific ---
        storyboard: bool = False,
        angle_deg: float = 0.0,
        wireframe: bool = False,
        width: int = 80,
        height: int = 120,
        # --- image-specific ---
        out_path: Path | None = None,
        # --- shared ---
        tolerance: float = 0.5,
    ) -> Union[ToolSuccess[dict], ToolSuccess[str], ToolError]:
        """
        Render a STEP file as a PNG image or ASCII art.

        Args:
            step_file_path: Path to the STEP file.
            format: Output format — "image" for a 3-panel PNG, "ascii" for
                isometric ASCII art.
            storyboard: (ascii only) If true, render four views (0°/90°/180°/270°)
                in a 2×2 grid. Recommended for agents — gives a full 360° impression
                in one call. Overrides angle_deg when set.
            angle_deg: (ascii only) Y-axis rotation angle in degrees (0–360). Only
                used when storyboard is false.
            wireframe: (ascii only) Render edges only if true. Default is shaded faces.
            width: (ascii only) Total output width in characters (default 80).
            height: (ascii only) Total storyboard height budget in rows (default 120).
                The frame height is derived automatically from the mesh's projected
                aspect ratio; this value caps the total output so it stays readable.
                Ignored when storyboard is false.
            out_path: (image only) Path to save the PNG. If omitted, the tool follows
                the rocketsmith project convention: when the STEP file lives in a
                ``CAD/`` directory (the standard layout), the PNG is written to the
                sibling ``visualizations/`` directory with the same stem. For STEP
                files outside a ``CAD/`` directory, the PNG is written alongside the
                STEP with a ``.png`` extension. Pass ``out_path`` explicitly to
                override either default.
            tolerance: Tessellation tolerance in mm. Lower = finer mesh, slower.
                       0.5 gives good quality for rocket parts; use 0.2 for fine detail.
        """
        step_file_path = resolve_path(step_file_path)
        if not step_file_path.exists():
            return tool_error(
                f"STEP file not found: {step_file_path}",
                "FILE_NOT_FOUND",
                step_file_path=str(step_file_path),
            )

        if format == "ascii":
            return await _render_ascii(
                step_file_path,
                storyboard=storyboard,
                angle_deg=angle_deg,
                wireframe=wireframe,
                width=width,
                height=height,
                tolerance=tolerance,
                tool_success=tool_success,
                tool_error=tool_error,
            )
        else:
            if out_path is not None:
                out_path = resolve_path(out_path)
            return await _render_image(
                step_file_path,
                out_path=out_path,
                tolerance=tolerance,
                tool_success=tool_success,
                tool_error=tool_error,
            )

    return build123d_render


async def _render_ascii(
    step_file_path,
    *,
    storyboard,
    angle_deg,
    wireframe,
    width,
    height,
    tolerance,
    tool_success,
    tool_error,
):
    from rocketsmith.build123d.render.ascii import render_step_ascii, render_storyboard

    try:
        if storyboard:
            ascii_art = render_storyboard(
                step_file_path,
                total_width=width,
                total_height=height,
                wireframe=wireframe,
                tolerance=tolerance,
            )
        else:
            ascii_art = render_step_ascii(
                step_file_path,
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
            step_file_path=str(step_file_path),
            exception_type=type(e).__name__,
        )
    except Exception as e:
        return tool_error(
            "Failed to render STEP file as ASCII",
            "RENDER_FAILED",
            step_file_path=str(step_file_path),
            exception_type=type(e).__name__,
            exception_message=str(e),
        )


async def _render_image(
    step_file_path, *, out_path, tolerance, tool_success, tool_error
):
    from rocketsmith.build123d.render.image import render_step_png

    if out_path is not None:
        png_path = out_path
    elif step_file_path.parent.name == "CAD":
        viz_dir = step_file_path.parent.parent / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        png_path = viz_dir / (step_file_path.stem + ".png")
    else:
        png_path = step_file_path.with_suffix(".png")

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
