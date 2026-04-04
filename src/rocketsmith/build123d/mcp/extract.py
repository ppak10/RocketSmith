from mcp.server.fastmcp import FastMCP


def register_build123d_extract(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error
    from rocketsmith.build123d.models import Build123dGeometry

    @app.tool(
        name="build123d_extract",
        title="Extract STEP Geometry",
        description=(
            "Extract geometric properties from a STEP file using build123d: "
            "volume, surface area, bounding box, and centre of mass. "
            "Optionally calculate mass from material density."
        ),
        structured_output=True,
    )
    async def build123d_extract(
        step_filename: str,
        workspace_name: str | None = None,
        material_density_kg_m3: float | None = None,
    ) -> Union[ToolSuccess[Build123dGeometry], ToolError]:
        """
        Extract geometric properties from a STEP file.

        Args:
            step_filename: Name of the STEP file in the workspace parts/ folder.
            workspace_name: The workspace name.
            material_density_kg_m3: Optional material density in kg/m³.
                When provided, mass_g is calculated from volume × density.
                Common values: PETG ≈ 1250, PLA ≈ 1240, ABS ≈ 1050,
                Aluminium ≈ 2700, Carbon fibre ≈ 1600.
        """
        from rocketsmith.build123d.extract import extract_geometry
        from rocketsmith.mcp.utils import resolve_workspace

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        step_path = workspace.path / "parts" / step_filename

        if not step_path.exists():
            return tool_error(
                f"STEP file not found: {step_path}",
                "FILE_NOT_FOUND",
                step_path=str(step_path),
            )

        try:
            geo = extract_geometry(
                step_path, material_density_kg_m3=material_density_kg_m3
            )
            return tool_success(geo)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                step_path=str(step_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to extract geometry from STEP file",
                "EXTRACT_FAILED",
                step_path=str(step_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    return build123d_extract
