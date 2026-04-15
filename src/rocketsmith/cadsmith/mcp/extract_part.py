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
        out_path: Path | None = None,
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
            out_path: Optional path to save the part JSON. Defaults to
                ``<project_dir>/gui/parts/<name>.json``.
        """
        from rocketsmith.cadsmith.extract_part import extract_part
        from rocketsmith.mcp.utils import get_project_dir

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

            # Write part JSON — to explicit out_path or the default project layout.
            from rocketsmith.gui.layout import PARTS_DIR

            if out_path is not None:
                resolved_out = resolve_path(out_path)
            else:
                resolved_out = get_project_dir() / PARTS_DIR / f"{file_path.stem}.json"
            resolved_out.parent.mkdir(parents=True, exist_ok=True)
            resolved_out.write_text(part.model_dump_json(indent=2), encoding="utf-8")

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
