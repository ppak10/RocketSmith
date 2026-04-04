from typing import Union
from pathlib import Path
from rocketsmith.mcp.types import T, ToolError, ToolSuccess


# Convenience function to create error responses
def tool_error(message: str, code: str, **details) -> ToolError:
    """Create a standardized tool error response."""
    return ToolError(error=message, error_code=code, details=details)


# Convenience function to create success responses
def tool_success(data: T) -> ToolSuccess[T]:
    """Create a standardized tool success response."""
    return ToolSuccess(data=data)


def resolve_workspace(workspace_name: str | None) -> Union["Workspace", ToolError]:
    """
    Resolve a workspace by name, returning a ToolError if it doesn't exist.
    """
    from wa import Workspace
    from wa.utils import get_project_root

    if workspace_name:
        project_root = get_project_root()
        workspace_dir = project_root / "workspaces" / workspace_name
    else:
        workspace_dir = Path.cwd()

    workspace_config_path = workspace_dir / "workspace.json"

    if not workspace_config_path.exists():
        return tool_error(
            f"This is not a valid workspace folder. `{workspace_config_path}` not found.",
            "WORKSPACE_NOT_FOUND",
            workspace_name=workspace_name,
            path=str(workspace_config_path),
        )

    try:
        return Workspace.load(workspace_config_path)
    except Exception as e:
        return tool_error(
            f"Failed to load workspace config: {e}",
            "WORKSPACE_LOAD_ERROR",
            workspace_name=workspace_name,
            exception_type=type(e).__name__,
        )
