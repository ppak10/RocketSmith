import shutil

from pathlib import Path

from wa import create_workspace, create_workspace_folder, Workspace


def create_rocketsmith_workspace(
    workspace_name: str,
    workspaces_path: Path | None = None,
    force: bool = False,
    include_examples: bool = False,
    **kwargs,
) -> Workspace:
    """
    Create RocketSmith Workspace class object and folder.
    """

    workspace = create_workspace(
        workspace_name=workspace_name, workspaces_path=workspaces_path, force=force
    )

    if include_examples:
        _create_workspace_openrocket_folder(
            workspace_name=workspace_name,
            workspaces_path=workspaces_path,
            force=force,
            include_examples=include_examples,
        )

    return workspace


def _create_workspace_openrocket_folder(
    workspace_name: str,
    workspaces_path: Path | None = None,
    force: bool = False,
    include_examples: bool = False,
) -> None:
    """
    Create openrocket subfolder within workspace and optionally copy example files.
    """
    from rocketsmith.data import DATA_DIR

    openrocket_folder = create_workspace_folder(
        name_or_path="openrocket",
        workspace_name=workspace_name,
        workspaces_path=workspaces_path,
        force=force,
    )

    if include_examples:
        for ork_file in (DATA_DIR).glob("*.ork"):
            shutil.copy2(ork_file, openrocket_folder.path / ork_file.name)
