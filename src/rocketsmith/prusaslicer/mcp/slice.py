from mcp.server.fastmcp import FastMCP

from pathlib import Path
from typing import Union


def register_prusaslicer_slice(app: FastMCP):
    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error
    from rocketsmith.prusaslicer.models import Material, PrusaSlicerResult

    @app.tool(
        title="Slice Model with PrusaSlicer",
        description="Slice a 3D model file (.stl, .step, .3mf, .obj) using PrusaSlicer and return print metadata.",
        structured_output=True,
    )
    async def prusaslicer_slice(
        model_file_path: Path,
        out_path: Path | None = None,
        config_path: Path | None = None,
        prusaslicer_path: Path | None = None,
        material: Material = Material.PLA,
    ) -> Union[ToolSuccess[PrusaSlicerResult], ToolError]:
        """
        Slice a 3D model using PrusaSlicer.

        Args:
            model_file_path: Path to the input model file (.stl, .step, .3mf, .obj).
            out_path: Path to save the .gcode output. Defaults to the same directory
                      as model_file_path with a .gcode extension.
            config_path: Optional path to a PrusaSlicer .ini config file to load.
            prusaslicer_path: Optional path to the PrusaSlicer executable.
            material: Filament material for weight calculation (pla, petg, abs).
                      Defaults to pla.
        """
        from rocketsmith.prusaslicer.slice import slice as prusaslicer_slice_fn

        model_file_path = resolve_path(model_file_path)
        if out_path is not None:
            out_path = resolve_path(out_path)
        if config_path is not None:
            config_path = resolve_path(config_path)

        if not model_file_path.exists():
            return tool_error(
                f"Model file not found: {model_file_path}",
                "FILE_NOT_FOUND",
                model_file_path=str(model_file_path),
            )

        output_path = (
            out_path if out_path is not None else model_file_path.with_suffix(".gcode")
        )

        try:
            result = prusaslicer_slice_fn(
                model_path=model_file_path,
                output_path=output_path,
                config_path=config_path,
                prusaslicer_path=prusaslicer_path,
                material=material,
            )

            return tool_success(result)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                model_file_path=str(model_file_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to slice model",
                "SLICE_FAILED",
                model_file_path=str(model_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = prusaslicer_slice
