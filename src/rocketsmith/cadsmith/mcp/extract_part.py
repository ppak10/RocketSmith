from mcp.server.fastmcp import FastMCP


def register_cadsmith_extract_part(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error
    from rocketsmith.cadsmith.models import Part
    from rocketsmith.cadsmith.extract_part import SUPPORTED_SUFFIXES

    @app.tool(
        name="cadsmith_extract_part",
        title="Extract Part Geometry",
        description=(
            "Extract geometric properties from a STEP or BREP file using build123d: "
            "volume, surface area, bounding box, and centre of mass. "
            "Optionally calculate mass from material density. "
            "Returns a Part with geometry fields populated."
        ),
        structured_output=True,
    )
    async def cadsmith_extract_part(
        file_path: Path,
        material_density_kg_m3: float | None = None,
        display_name: str | None = None,
        project_dir: Path | None = None,
    ) -> Union[ToolSuccess[Part], ToolError]:
        """
        Extract geometric properties from a STEP or BREP file.

        Args:
            file_path: Path to the STEP (.step/.stp) or BREP (.brep) file.
            material_density_kg_m3: Optional material density in kg/m³.
                When provided, mass is calculated from volume × density.
                Common values: PETG ≈ 1250, PLA ≈ 1240, ABS ≈ 1050,
                Aluminium ≈ 2700, Carbon fibre ≈ 1600.
            display_name: Optional human-readable name for the part
                (e.g. "Nose Cone"). Falls back to the filename stem.
            project_dir: Optional project directory. When provided, saves
                the part JSON to <project_dir>/parts/<name>.json.
        """
        from rocketsmith.cadsmith.extract_part import extract_part

        file_path = resolve_path(file_path)
        if not file_path.exists():
            return tool_error(
                f"File not found: {file_path}",
                "FILE_NOT_FOUND",
                file_path=str(file_path),
            )

        if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            return tool_error(
                f"Unsupported file format '{file_path.suffix}'. "
                f"Expected one of: {', '.join(sorted(SUPPORTED_SUFFIXES))}",
                "UNSUPPORTED_FORMAT",
                file_path=str(file_path),
            )

        try:
            part = extract_part(
                file_path,
                material_density_kg_m3=material_density_kg_m3,
                display_name=display_name,
            )

            # Write part JSON to parts/<name>.json if project_dir is given.
            if project_dir is not None:
                resolved_dir = resolve_path(project_dir)
                parts_dir = resolved_dir / "parts"
                parts_dir.mkdir(parents=True, exist_ok=True)
                out_path = parts_dir / f"{file_path.stem}.json"
                out_path.write_text(part.model_dump_json(indent=2), encoding="utf-8")

            return tool_success(part)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                file_path=str(file_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to extract part geometry",
                "EXTRACT_FAILED",
                file_path=str(file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    return cadsmith_extract_part
