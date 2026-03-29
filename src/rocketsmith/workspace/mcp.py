from mcp.server.fastmcp import FastMCP

from pathlib import Path
from typing import Union


def register_workspace_create(app: FastMCP):
    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error
    from wa import Workspace

    @app.tool(
        title="Create RocketSmith Workspace",
        description="Creates workspace folder for use with rocketsmith tools.",
        structured_output=True,
    )
    async def workspace_create(
        workspace_name: str,
        workspaces_path: Path | None = None,
        force: bool = False,
    ) -> Union[ToolSuccess[Workspace], ToolError]:
        """
        Initialize rocketsmith workspace folder.

        Args:
            workspace_name: Name of folder to initialize.
            workspaces_path: Path of folder containing workspaces.
            force: Overwrite existing workspace.
        """
        from rocketsmith.workspace.create import create_rocketsmith_workspace

        try:
            workspace = create_rocketsmith_workspace(
                workspace_name=workspace_name,
                workspaces_path=workspaces_path,
                force=force,
            )

            return tool_success(workspace)

        except PermissionError as e:
            return tool_error(
                "Permission denied when creating workspace folder",
                "PERMISSION_DENIED",
                workspace_name=workspace_name,
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to create workspace folder",
                "WORKSPACE_CREATE_FAILED",
                workspace_name=workspace_name,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = workspace_create
