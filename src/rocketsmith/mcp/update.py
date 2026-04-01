import os
import subprocess

from pathlib import Path
from rich import print as rprint


def update(project_path: Path, tools_only: bool = False) -> bool:
    """Upgrade rocketsmith to the latest version on PyPI and refresh the agent file.

    Tries `uv add --upgrade rocketsmith` first (uv project context).
    Falls back to `uv pip install --upgrade rocketsmith` if that fails.

    Args:
        project_path: Directory in which to run the uv upgrade command. Should
                      contain pyproject.toml for the `uv add` path, or at
                      minimum a uv-managed virtual environment.
        tools_only: If True, skip the agent file update after upgrading.

    Returns:
        True if the upgrade succeeded, False otherwise.
    """
    rprint("[dim]Upgrading rocketsmith...[/dim]")

    # Try uv add --upgrade first (works in a uv project with pyproject.toml)
    result = subprocess.run(
        ["uv", "add", "--upgrade", "rocketsmith"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        rprint("[dim]uv add failed — falling back to uv pip install --upgrade[/dim]")
        result = subprocess.run(
            ["uv", "pip", "install", "--upgrade", "rocketsmith"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )

    if result.returncode != 0:
        rprint(f"⚠️  [yellow]Upgrade failed:[/yellow]\n{result.stderr.strip()}")
        return False

    # Report new version
    ver_result = subprocess.run(
        ["uv", "run", "python", "-c",
         "import importlib.metadata; print(importlib.metadata.version('rocketsmith'))"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )
    version = ver_result.stdout.strip() if ver_result.returncode == 0 else "unknown"
    rprint(f"✅ [bold green]Upgraded to rocketsmith {version}[/bold green]")

    if tools_only:
        return True

    # Copy the agent file from the *newly installed* package.
    # We must do this in a subprocess so it imports the new version, not the
    # currently running one.
    agent_dest = project_path / ".claude" / "agents" / "rocketsmith.md"
    agent_dest.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["RS_AGENT_DEST"] = str(agent_dest)

    copy_result = subprocess.run(
        [
            "uv", "run", "python", "-c",
            "import shutil, os; "
            "from importlib.resources import files; "
            "import rocketsmith.data as d; "
            "shutil.copy(str(files(d).joinpath('mcp/agent.md')), os.environ['RS_AGENT_DEST'])",
        ],
        cwd=project_path,
        capture_output=True,
        text=True,
        env=env,
    )

    if copy_result.returncode == 0:
        rprint(f"✅ [bold green]Updated agent:[/bold green] {agent_dest}")
    else:
        rprint(f"⚠️  [yellow]Agent file update failed:[/yellow]\n{copy_result.stderr.strip()}")

    return True
