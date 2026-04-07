from mcp.server.fastmcp import FastMCP


def register_openrocket_inspect(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error, resolve_workspace

    @app.tool(
        title="Inspect OpenRocket or RockSim File",
        description=(
            "Return the full component tree of an OpenRocket .ork or RockSim .rkt file, "
            "plus an ASCII side-profile of the rocket."
        ),
        structured_output=True,
    )
    async def openrocket_inspect(
        filename: str,
        workspace_name: str | None = None,
        openrocket_path: Path | None = None,
        width: int | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Inspect all components in an OpenRocket (.ork) or RockSim (.rkt) design file.

        Returns a dict with two keys:
          - ``components``: flat list of components in tree order.  Each entry
            contains 'type', 'name', 'depth', 'position_x_m', and
            component-specific properties (length_m, outer_diameter_m, etc.).
          - ``ascii_art``: multi-line string with a horizontal ASCII side-profile
            of the rocket (nose left, tail right).  Body walls use /, \\, and -
            to show the profile shape.  Internal tubes appear as dashed (:) walls.
            Fins are rendered as | protrusions above and below the body.

        Args:
            filename: The .ork or .rkt file in the workspace openrocket/ folder.
            workspace_name: The workspace name.
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
            width: ASCII art output width in characters. Larger values zoom in and
                   show more detail. Defaults to 120 if not provided.
        """
        from rocketsmith.openrocket.ascii import render_rocket_ascii
        from rocketsmith.openrocket.components import inspect_rocket_file
        from rocketsmith.openrocket.utils import get_openrocket_path

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        if not (filename.endswith(".ork") or filename.endswith(".rkt")):
            filename += ".ork"

        file_path = workspace.path / "openrocket" / filename

        if not file_path.exists():
            return tool_error(
                f"Design file not found: {file_path}",
                "FILE_NOT_FOUND",
                file_path=str(file_path),
            )

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            result = inspect_rocket_file(path=file_path, jar_path=openrocket_path)
            components = result["components"]
            ascii_art = render_rocket_ascii(
                components,
                width=width,
                cg_x=result.get("cg_x"),
                cp_x=result.get("cp_x"),
                max_diameter=result.get("max_diameter_m"),
            )
            return tool_success(
                {
                    "components": components,
                    "ascii_art": ascii_art,
                    "cg_x": result.get("cg_x"),
                    "cp_x": result.get("cp_x"),
                    "max_diameter_m": result.get("max_diameter_m"),
                }
            )

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                file_path=str(file_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to inspect design file",
                "INSPECT_FAILED",
                file_path=str(file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_inspect
