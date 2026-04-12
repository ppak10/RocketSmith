from mcp.server.fastmcp import FastMCP


def register_openrocket_generate_tree(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="openrocket_generate_tree",
        title="Generate Component Tree",
        description=(
            "Generate a hierarchical component tree from an OpenRocket .ork or "
            "RockSim .rkt file. Returns typed dimensions in millimetres, "
            "per-component mass and material, agent annotations from comment "
            "fields, static stability (CG/CP/calibers), and an ASCII side "
            "profile. Writes component_tree.json to the project directory."
        ),
        structured_output=True,
    )
    async def openrocket_generate_tree(
        rocket_file_path: Path,
        project_dir: Path,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Generate a component tree from an OpenRocket design file.

        Reads the .ork/.rkt component hierarchy, converts all dimensions
        to millimetres, parses comment fields for agent annotations,
        computes static stability via the Barrowman method, and renders
        an ASCII side profile.

        The component_tree.json is written to project_dir and serves as
        the handoff between the OpenRocket agent, manufacturing agent,
        and cadsmith agent.

        Args:
            rocket_file_path: Path to the .ork or .rkt design file.
            project_dir: Absolute path to the project root directory.
            openrocket_path: Optional path to the OpenRocket JAR file.
        """
        from rocketsmith.openrocket.generate_tree import generate_tree
        from rocketsmith.openrocket.utils import get_openrocket_path

        rocket_file_path = resolve_path(rocket_file_path)
        project_dir = resolve_path(project_dir)

        if not rocket_file_path.exists():
            return tool_error(
                f"Design file not found: {rocket_file_path}",
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
            )

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            tree, ascii_art = generate_tree(
                rocket_file_path, project_dir, jar_path=openrocket_path
            )

            # Write component_tree.json
            from rocketsmith.gui.layout import TREE_FILE

            tree_path = project_dir / TREE_FILE
            tree_path.parent.mkdir(parents=True, exist_ok=True)
            tree_path.write_text(tree.model_dump_json(indent=2), encoding="utf-8")

            return tool_success(
                {
                    "tree": tree.model_dump(mode="json"),
                    "ascii_art": ascii_art,
                    "tree_path": str(tree_path),
                }
            )

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to generate component tree",
                "GENERATE_TREE_FAILED",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    return openrocket_generate_tree
