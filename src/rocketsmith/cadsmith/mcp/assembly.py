from pathlib import Path
from typing import Literal, Union

from mcp.server.fastmcp import FastMCP


def register_cadsmith_assembly(app: FastMCP):
    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error
    from rocketsmith.cadsmith.models import Assembly

    @app.tool(
        name="cadsmith_assembly",
        title="Generate or Read Assembly",
        description=(
            "Generate or read an assembly.json that describes how parts "
            "fit together spatially for the 3D viewer. "
            "Use 'generate' to build assembly.json from the parts manifest "
            "and STEP file bounding boxes. "
            "Use 'read' to load an existing assembly.json."
        ),
        structured_output=True,
    )
    async def cadsmith_assembly(
        action: Literal["generate", "read"],
        project_dir: Path,
    ) -> Union[ToolSuccess[Assembly], ToolError]:
        """
        Generate or read the assembly layout for the 3D viewer.

        Actions:
            generate: Read parts_manifest.json and STEP files to compute
                      bounding boxes and positions, then write assembly.json.
            read:     Load and return an existing assembly.json.

        Args:
            action: 'generate' or 'read'.
            project_dir: Absolute path to the project root directory.
        """
        import json
        from datetime import datetime, timezone

        from rocketsmith.cadsmith.models import AssemblyPart

        project_dir = resolve_path(project_dir)
        assembly_path = project_dir / "assembly.json"

        if action == "read":
            if not assembly_path.exists():
                return tool_error(
                    f"assembly.json not found at {assembly_path}",
                    "FILE_NOT_FOUND",
                    file_path=str(assembly_path),
                )
            try:
                data = json.loads(assembly_path.read_text(encoding="utf-8"))
                assembly = Assembly.model_validate(data)
                return tool_success(assembly)
            except Exception as e:
                return tool_error(
                    f"Failed to read assembly.json: {e}",
                    "PARSE_ERROR",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                )

        # ── action == "generate" ────────────────────────────────────────

        manifest_path = project_dir / "parts_manifest.json"
        if not manifest_path.exists():
            return tool_error(
                f"parts_manifest.json not found at {manifest_path}. "
                "Run the design-for-additive-manufacturing skill first.",
                "FILE_NOT_FOUND",
                file_path=str(manifest_path),
            )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            return tool_error(
                f"Failed to read parts_manifest.json: {e}",
                "PARSE_ERROR",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        # Determine the ordered part list from the manifest assembly.
        assemblies = manifest.get("assemblies", [])
        if assemblies:
            order = assemblies[0].get("parts_fore_to_aft", [])
        else:
            order = [p["name"] for p in manifest.get("parts", [])]

        parts_by_name = {p["name"]: p for p in manifest.get("parts", [])}

        # Read bounding boxes from STEP files.
        assembly_parts: list[AssemblyPart] = []
        cursor_z = 0.0

        for part_name in order:
            mfg_part = parts_by_name.get(part_name)
            if mfg_part is None:
                continue

            step_rel = mfg_part.get("step_path", "")
            step_abs = project_dir / step_rel
            stl_rel = step_rel.replace("step/", "stl/").replace(".step", ".stl")

            # Compute bounding box from STEP file.
            bbox = None
            part_height = 0.0
            if step_abs.exists():
                try:
                    bbox, part_height = _get_bounding_box(step_abs)
                except Exception:
                    pass

            # Fall back to manifest features for height.
            if part_height == 0.0 and mfg_part.get("features"):
                part_height = mfg_part["features"].get("length_mm", 0.0)
                # Add shoulder length for nose cones.
                shoulder = mfg_part["features"].get("shoulder")
                if shoulder:
                    part_height += shoulder.get("length_mm", 0.0)

            # Nose cone is the first part — flip it 180 on X so
            # the shoulder points aft (toward the next part).
            is_nose = part_name == order[0] and "nose" in part_name.lower()
            rotation = (180.0, 0.0, 0.0) if is_nose else (0.0, 0.0, 0.0)

            assembly_parts.append(
                AssemblyPart(
                    name=part_name,
                    stl_path=stl_rel if (project_dir / stl_rel).exists() else None,
                    step_path=step_rel if step_abs.exists() else None,
                    bounding_box_mm=bbox,
                    position_mm=(0.0, 0.0, cursor_z),
                    rotation_deg=rotation,
                )
            )

            cursor_z += part_height

        # Add purchased items as parts with no geometry.
        for item in manifest.get("purchased_items", []):
            assembly_parts.append(
                AssemblyPart(
                    name=item.get("derived_from", "purchased_item"),
                    description=item.get("description"),
                    id=item.get("suggested_source"),
                )
            )

        # Add skipped items that are real physical objects (e.g. parachutes).
        for item in manifest.get("skipped_components", []):
            if "non-structural" in item.get("reason", ""):
                assembly_parts.append(
                    AssemblyPart(
                        name=item["name"],
                        description=item.get("reason"),
                    )
                )

        assembly = Assembly(
            project_root=str(project_dir),
            generated_at=datetime.now(timezone.utc).isoformat(),
            parts=assembly_parts,
            total_length_mm=cursor_z,
        )

        # Write assembly.json.
        assembly_path.write_text(
            assembly.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return tool_success(assembly)

    _ = cadsmith_assembly


def _get_bounding_box(
    step_path: Path,
) -> tuple[tuple[float, float, float], float]:
    """Read a STEP file and return (bbox_tuple, z_height)."""
    from build123d import import_step

    shape = import_step(str(step_path))
    bb = shape.bounding_box()
    bbox = (round(bb.size.X, 2), round(bb.size.Y, 2), round(bb.size.Z, 2))
    return bbox, round(bb.size.Z, 2)
