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
        out_path: Path | None = None,
    ) -> Union[ToolSuccess[Assembly], ToolError]:
        """
        Generate or read the assembly layout for the 3D viewer.

        Actions:
            generate: Read component_tree.json and STEP files to compute
                      bounding boxes and positions, then write assembly.json.
            read:     Load and return an existing assembly.json.

        Args:
            action: 'generate' or 'read'.
            out_path: Optional path to write assembly.json. Defaults to
                      ``<project_dir>/gui/assembly.json``.
        """
        import json
        from datetime import datetime, timezone

        from rocketsmith.cadsmith.models import AssemblyPart, UnitVector
        from rocketsmith.manufacturing.models import ComponentTree, Fate, Component
        from rocketsmith.mcp.utils import get_project_dir

        project_dir = get_project_dir()
        from rocketsmith.gui.layout import ASSEMBLY_FILE, TREE_FILE, PARTS_DIR

        assembly_path = (
            resolve_path(out_path)
            if out_path is not None
            else project_dir / ASSEMBLY_FILE
        )

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

        tree_path = project_dir / TREE_FILE
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
        parts_dir = project_dir / PARTS_DIR
        parts_dir.mkdir(parents=True, exist_ok=True)

        color_palette = [
            "#fb8500",
            "#e57700",
            "#cc6a00",
            "#b35c00",
            "#ff9e33",
            "#ffb766",
            "#ffa940",
            "#f29000",
        ]

        from pint import Quantity

        for ci, comp in enumerate(all_printed):
            step_rel = comp.step_path or ""
            step_abs = project_dir / step_rel if step_rel else Path()

            # Convert component name to snake_case stem.
            stem = comp.name.lower().replace(" ", "_")
            part_file = f"{PARTS_DIR}/{stem}.json"

            # Extract geometry and write part JSON.
            part_height = 0.0
            if step_rel and step_abs.exists():
                try:
                    from rocketsmith.cadsmith.extract_part import extract_part

                    extracted = extract_part(step_abs, display_name=comp.name)
                    part_height = (
                        extracted.bounding_box.z.magnitude
                        if extracted.bounding_box
                        else 0.0
                    )
                    # Write part JSON.
                    part_json_path = project_dir / part_file
                    part_json_path.write_text(
                        extracted.model_dump_json(indent=2), encoding="utf-8"
                    )
                except Exception:
                    pass

            # Fall back to component dimensions for height.
            if part_height == 0.0 and comp.dimensions and comp.dimensions.length:
                part_height = comp.dimensions.length.magnitude

            # Compute joint offset — how much the *next* part should overlap
            # into this one.  Shoulder lengths on nose cones and coupler
            # lengths on tube couplers represent insertion depth.
            joint_offset_mm = 0.0
            agent = comp.agent
            if agent and getattr(agent, "dfam_shoulder_length_mm", None):
                joint_offset_mm = agent.dfam_shoulder_length_mm
            elif (
                comp.type == "TubeCoupler"
                and comp.dimensions
                and comp.dimensions.length
            ):
                # Couplers insert half their length into each tube.
                joint_offset_mm = comp.dimensions.length.magnitude / 2

            # Nose cones and transition shoulders point aft — invert them.
            invert = not first_nose_seen and "nose" in comp.name.lower()
            if invert:
                first_nose_seen = True

            # For inverted parts, the geometry extends backward from the
            # cursor.  Position at cursor + part_height so the base (after
            # flip) sits at cursor.
            pos_z = cursor_z + part_height if invert else cursor_z

            assembly_parts.append(
                AssemblyPart(
                    part_file=part_file,
                    position=UnitVector(z=pos_z),
                    color=color_palette[ci % len(color_palette)],
                    invert_z=invert,
                    joint_offset=(
                        Quantity(joint_offset_mm, "mm") if joint_offset_mm > 0 else None
                    ),
                )
            )

            # Advance cursor by part height, minus shoulder overlap so the
            # next part slides into this one.
            cursor_z += part_height - joint_offset_mm

        # Add purchased/skipped items — no part JSON, just a reference stub.
        for comp in [*all_purchased, *all_skipped]:
            reason = comp.agent.reason if comp.agent else None
            if comp in all_skipped and not (reason and "non-structural" in reason):
                continue
            stem = comp.name.lower().replace(" ", "_")
            part_file = f"{PARTS_DIR}/{stem}.json"
            assembly_parts.append(AssemblyPart(part_file=part_file))

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
