from mcp.server.fastmcp import FastMCP


def register_openrocket_inspect(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error, resolve_workspace

    @app.tool(
        title="Inspect OpenRocket File",
        description=(
            "Return the full component tree of an OpenRocket .ork file, "
            "plus an ASCII side-profile of the rocket."
        ),
        structured_output=True,
    )
    async def openrocket_inspect(
        ork_filename: str,
        workspace_name: str | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Inspect all components in an OpenRocket design file.

        Returns a dict with two keys:
          - ``components``: flat list of components in tree order.  Each entry
            contains 'type', 'name', 'depth', 'position_x_m', and
            component-specific properties (length_m, outer_diameter_m, etc.).
          - ``ascii_art``: multi-line string with a horizontal ASCII side-profile
            of the rocket (nose left, tail right).  Body walls use /, \\, and -
            to show the profile shape.  Internal tubes appear as dashed (:) walls.
            Fins are rendered as | protrusions above and below the body.

        Args:
            ork_filename: The .ork file in the workspace openrocket/ folder.
            workspace_name: The workspace name.
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
        """
        from rocketsmith.openrocket.ascii import render_rocket_ascii
        from rocketsmith.openrocket.components import inspect_ork
        from rocketsmith.openrocket.utils import get_openrocket_path

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        if not ork_filename.endswith(".ork"):
            ork_filename += ".ork"

        ork_path = workspace.path / "openrocket" / ork_filename

        if not ork_path.exists():
            return tool_error(
                f"OpenRocket file not found: {ork_path}",
                "FILE_NOT_FOUND",
                ork_path=str(ork_path),
            )

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            result = inspect_ork(ork_path=ork_path, jar_path=openrocket_path)
            components = result["components"]
            ascii_art = render_rocket_ascii(
                components,
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
                ork_path=str(ork_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to inspect OpenRocket file",
                "INSPECT_FAILED",
                ork_path=str(ork_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_inspect
