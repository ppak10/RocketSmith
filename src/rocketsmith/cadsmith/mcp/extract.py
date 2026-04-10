from mcp.server.fastmcp import FastMCP


def register_cadsmith_extract(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error
    from rocketsmith.cadsmith.models import CADSmithModelInfo

    @app.tool(
        name="cadsmith_extract",
        title="Extract STEP Geometry",
        description=(
            "Extract geometric properties from a STEP file using build123d: "
            "volume, surface area, bounding box, and centre of mass. "
            "Optionally calculate mass from material density."
        ),
        structured_output=True,
    )
    async def cadsmith_extract(
        step_file_path: Path,
        material_density_kg_m3: float | None = None,
    ) -> Union[ToolSuccess[CADSmithModelInfo], ToolError]:
        """
        Extract geometric properties from a STEP file.

        Args:
            step_file_path: Path to the STEP file.
            material_density_kg_m3: Optional material density in kg/m³.
                When provided, mass_g is calculated from volume × density.
                Common values: PETG ≈ 1250, PLA ≈ 1240, ABS ≈ 1050,
                Aluminium ≈ 2700, Carbon fibre ≈ 1600.
        """
        from rocketsmith.cadsmith.extract import extract_geometry

        step_file_path = resolve_path(step_file_path)
        if not step_file_path.exists():
            return tool_error(
                f"STEP file not found: {step_file_path}",
                "FILE_NOT_FOUND",
                step_file_path=str(step_file_path),
            )

        try:
            geo = extract_geometry(
                step_file_path, material_density_kg_m3=material_density_kg_m3
            )
            return tool_success(geo)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                step_file_path=str(step_file_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to extract geometry from STEP file",
                "EXTRACT_FAILED",
                step_file_path=str(step_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    return cadsmith_extract
