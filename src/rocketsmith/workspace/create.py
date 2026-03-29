from pathlib import Path

from wa import create_workspace, Workspace


def create_rocketsmith_workspace(
    workspace_name: str,
    workspaces_path: Path | None = None,
    force: bool = False,
    **kwargs,
) -> Workspace:
    """
    Create RocketSmith Workspace class object and folder.
    """

    workspace = create_workspace(
        workspace_name=workspace_name, workspaces_path=workspaces_path, force=force
    )

    return workspace
