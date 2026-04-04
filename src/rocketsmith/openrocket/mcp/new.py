from mcp.server.fastmcp import FastMCP


def register_openrocket_new(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error, resolve_workspace

    @app.tool(
        title="New OpenRocket File",
        description="Create a new empty OpenRocket .ork file with a single stage.",
        structured_output=True,
    )
    async def openrocket_new(
        name: str,
        workspace_name: str | None = None,
        ork_filename: str | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Create a new OpenRocket design file with an empty rocket and one stage.

        Args:
            name: Display name for the rocket (stored inside the .ork file).
            workspace_name: Name of the workspace to create the file in.
            ork_filename: Name of the .ork file to save in the workspace's openrocket folder (defaults to {name}.ork).
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
        """
        from rocketsmith.openrocket.components import new_ork
        from rocketsmith.openrocket.utils import get_openrocket_path

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        if not ork_filename:
            ork_filename = f"{name}.ork"

        if not ork_filename.endswith(".ork"):
            ork_filename += ".ork"

        output_path = workspace.path / "openrocket" / ork_filename

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            result_path = new_ork(
                name=name, output_path=output_path, jar_path=openrocket_path
            )
            return tool_success({"path": str(result_path), "name": name})

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to create OpenRocket file",
                "CREATE_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_new

    _ = openrocket_new
