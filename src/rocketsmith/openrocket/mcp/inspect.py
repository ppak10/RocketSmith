from mcp.server.fastmcp import FastMCP


def register_openrocket_inspect(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        title="Inspect OpenRocket File",
        description="Return the full component tree of an OpenRocket .ork file as a flat list.",
        structured_output=True,
    )
    async def openrocket_inspect(
        ork_path: Path,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[list[dict]], ToolError]:
        """
        Inspect all components in an OpenRocket design file.

        Returns a flat list of components in tree order. Each entry contains
        'type', 'name', 'depth', and component-specific properties (length_m,
        outer_diameter_m, etc.).

        Args:
            ork_path: Path to the OpenRocket .ork design file.
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
        """
        from rocketsmith.openrocket.components import inspect_ork
        from rocketsmith.openrocket.utils import get_openrocket_path

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            components = inspect_ork(ork_path=ork_path, jar_path=openrocket_path)
            return tool_success(components)

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
