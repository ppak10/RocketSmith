from mcp.server.fastmcp import FastMCP


def register_manufacturing_annotate_tree(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="manufacturing_annotate_tree",
        title="Annotate Component Tree (DFAM)",
        description=(
            "Apply design-for-additive-manufacturing rules to an existing "
            "component_tree.json. Annotates each component with fate "
            "(print, fuse, purchase, skip), fusion directives, and "
            "AM-specific dimension adjustments. Writes the annotated "
            "tree back to component_tree.json."
        ),
        structured_output=True,
    )
    async def manufacturing_annotate_tree(
        fusion_overrides: dict | None = None,
        out_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Annotate a component tree with DFAM decisions.

        Reads component_tree.json from the project directory, applies
        additive manufacturing rules (fin integration, coupler fusion,
        motor mount handling), and writes the annotated tree back.

        Args:
            fusion_overrides: Optional dict of fusion decision overrides:
                motor_mount_fate: "fuse" (default) | "separate"
                coupler_fate: "fuse" (default) | "separate"
                nose_cone_hollow: true | false
                fin_thickness_mm: override minimum fin thickness
                fin_fillet_mm: override fillet radius
            out_path: Optional path to write the annotated component_tree.json.
                Defaults to ``<project_dir>/gui/component_tree.json``.
        """
        import json

        from rocketsmith.manufacturing.models import ComponentTree
        from rocketsmith.manufacturing.dfam import annotate_dfam
        from rocketsmith.mcp.utils import get_project_dir

        project_dir = get_project_dir()
        from rocketsmith.gui.layout import TREE_FILE

        tree_path = (
            resolve_path(out_path) if out_path is not None else project_dir / TREE_FILE
        )

        if not tree_path.exists():
            return tool_error(
                f"component_tree.json not found at {tree_path}. "
                "Run openrocket_component with action='read' first.",
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

        try:
            annotated = annotate_dfam(tree, fusion_overrides=fusion_overrides)

            tree_path.write_text(annotated.model_dump_json(indent=2), encoding="utf-8")

            return tool_success(
                {
                    "tree": annotated.model_dump(mode="json"),
                    "tree_path": str(tree_path),
                    "message": "DFAM annotations applied to component tree.",
                }
            )

        except Exception as e:
            return tool_error(
                "Failed to annotate component tree",
                "ANNOTATE_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    return manufacturing_annotate_tree
