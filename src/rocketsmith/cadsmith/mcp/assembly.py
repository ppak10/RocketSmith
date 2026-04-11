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
            "Use 'generate' to build assembly.json from component_tree.json "
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
            generate: Read component_tree.json and STEP files to compute
                      bounding boxes and positions, then write assembly.json.
            read:     Load and return an existing assembly.json.

        Args:
            action: 'generate' or 'read'.
            project_dir: Absolute path to the project root directory.
        """
        import json
        from datetime import datetime, timezone

        from rocketsmith.cadsmith.models import AssemblyPart, UnitVector
        from rocketsmith.manufacturing.models import ComponentTree, Fate, Component

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

        tree_path = project_dir / "component_tree.json"
        if not tree_path.exists():
            return tool_error(
                f"component_tree.json not found at {tree_path}. "
                "Run the design-for-additive-manufacturing skill first.",
                "FILE_NOT_FOUND",
                file_path=str(tree_path),
            )

        try:
            data = json.loads(tree_path.read_text(encoding="utf-8"))
            tree = ComponentTree.model_validate(data)
        except Exception as e:
            return tool_error(
                f"Failed to read component_tree.json: {e}",
                "PARSE_ERROR",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        # Recursively collect components grouped by fate.
        def _walk(
            components: list[Component],
        ) -> tuple[list[Component], list[Component], list[Component]]:
            printed: list[Component] = []
            purchased: list[Component] = []
            skipped: list[Component] = []
            for comp in components:
                fate = comp.agent.fate if comp.agent else None
                if fate == Fate.PRINT:
                    printed.append(comp)
                elif fate == Fate.PURCHASE:
                    purchased.append(comp)
                elif fate == Fate.SKIP:
                    skipped.append(comp)
                # Recurse into children regardless of this component's fate.
                cp, cu, cs = _walk(comp.children)
                printed.extend(cp)
                purchased.extend(cu)
                skipped.extend(cs)
            return printed, purchased, skipped

        all_printed: list[Component] = []
        all_purchased: list[Component] = []
        all_skipped: list[Component] = []
        for stage in tree.stages:
            p, u, s = _walk(stage.components)
            all_printed.extend(p)
            all_purchased.extend(u)
            all_skipped.extend(s)

        # Build assembly parts from printed components.
        assembly_parts: list[AssemblyPart] = []
        cursor_z = 0.0
        first_nose_seen = False

        for comp in all_printed:
            step_rel = comp.step_path or ""
            step_abs = project_dir / step_rel if step_rel else Path()
            stl_rel = step_rel.replace("step/", "stl/").replace(".step", ".stl")

            # Extract geometry from STEP file.
            extracted_bbox = None
            part_height = 0.0
            if step_rel and step_abs.exists():
                try:
                    from rocketsmith.cadsmith.extract_part import extract_part

                    extracted = extract_part(step_abs)
                    extracted_bbox = extracted.bounding_box
                    part_height = extracted_bbox.z.magnitude if extracted_bbox else 0.0
                except Exception:
                    pass

            # Fall back to component dimensions for height.
            if part_height == 0.0 and comp.dimensions and comp.dimensions.length:
                part_height = comp.dimensions.length.magnitude

            # Nose cone — flip it 180 on X so the shoulder points aft.
            is_nose = not first_nose_seen and "nose" in comp.name.lower()
            if is_nose:
                first_nose_seen = True
            rotation = UnitVector.deg(x=180.0) if is_nose else UnitVector.deg()

            assembly_parts.append(
                AssemblyPart(
                    name=comp.name,
                    stl_path=(
                        stl_rel
                        if stl_rel and (project_dir / stl_rel).exists()
                        else None
                    ),
                    step_path=step_rel if step_rel and step_abs.exists() else None,
                    bounding_box=extracted_bbox,
                    position=UnitVector(z=cursor_z),
                    rotation=rotation,
                )
            )

            cursor_z += part_height

        # Add purchased items as parts with no geometry.
        for comp in all_purchased:
            assembly_parts.append(
                AssemblyPart(
                    name=comp.name,
                    description=(
                        comp.agent.reason if comp.agent and comp.agent.reason else None
                    ),
                )
            )

        # Add skipped items that are real physical objects (e.g. parachutes).
        for comp in all_skipped:
            reason = comp.agent.reason if comp.agent else None
            if reason and "non-structural" in reason:
                assembly_parts.append(
                    AssemblyPart(
                        name=comp.name,
                        description=reason,
                    )
                )

        assembly = Assembly(
            project_root=str(project_dir),
            generated_at=datetime.now(timezone.utc).isoformat(),
            parts=assembly_parts,
            total_length=cursor_z,
        )

        # Write assembly.json.
        assembly_path.write_text(
            assembly.model_dump_json(indent=2),
            encoding="utf-8",
        )

        return tool_success(assembly)

    _ = cadsmith_assembly
