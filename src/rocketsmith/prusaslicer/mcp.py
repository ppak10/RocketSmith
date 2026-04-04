from mcp.server.fastmcp import FastMCP

from pathlib import Path
from typing import Union


def register_prusaslicer_slice(app: FastMCP):
    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error, resolve_workspace
    from rocketsmith.prusaslicer.models import Material, PrusaSlicerResult

    @app.tool(
        title="Slice Model with PrusaSlicer",
        description="Slice a 3D model file (.stl, .step, .3mf, .obj) using PrusaSlicer and return print metadata.",
        structured_output=True,
    )
    async def prusaslicer_slice(
        model_filename: str,
        workspace_name: str | None = None,
        config_path: Path | None = None,
        prusaslicer_path: Path | None = None,
        material: Material = Material.PLA,
    ) -> Union[ToolSuccess[PrusaSlicerResult], ToolError]:
        """
        Slice a 3D model using PrusaSlicer.

        Args:
            model_filename: Name of the input model file (.stl, .step, .3mf, .obj) in the workspace parts/ folder.
            workspace_name: The workspace name.
            config_path: Optional path to a PrusaSlicer .ini config file to load.
            prusaslicer_path: Optional path to the PrusaSlicer executable.
            material: Filament material for weight calculation (pla, petg, abs).
                      Defaults to pla.
        """
        from rocketsmith.prusaslicer.slice import slice as prusaslicer_slice_fn

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        model_path = workspace.path / "parts" / model_filename

        if not model_path.exists():
            return tool_error(
                f"Model file not found: {model_path}",
                "FILE_NOT_FOUND",
                model_path=str(model_path),
            )

        output_path = workspace.path / "parts" / model_path.with_suffix(".gcode").name

        try:
            result = prusaslicer_slice_fn(
                model_path=model_path,
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
                model_path=str(model_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to slice model",
                "SLICE_FAILED",
                model_path=str(model_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = prusaslicer_slice
