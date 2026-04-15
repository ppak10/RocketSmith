import atexit
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel


class DependencyStatus(BaseModel):
    java: str
    openrocket: str
    prusaslicer: str
    ready: bool
    gui_url: str | None = None
    gui_pid: int | None = None


def _check() -> DependencyStatus:
    from rocketsmith.openrocket.utils import get_openrocket_jvm, get_openrocket_path
    from rocketsmith.prusaslicer.utils import get_prusaslicer_path

    # Java
    jvm = get_openrocket_jvm(Path("/nonexistent"))
    java_status = f"installed ({jvm})" if jvm else "not found"

    # OpenRocket JAR
    try:
        jar = get_openrocket_path()
        openrocket_status = f"installed ({jar})"
    except FileNotFoundError:
        openrocket_status = "not found"

    # PrusaSlicer
    try:
        exe = get_prusaslicer_path()
        prusaslicer_status = f"installed ({exe})"
    except FileNotFoundError:
        prusaslicer_status = "not found"

    ready = all(
        "not found" not in s
        for s in [java_status, openrocket_status, prusaslicer_status]
    )

    return DependencyStatus(
        java=java_status,
        openrocket=openrocket_status,
        prusaslicer=prusaslicer_status,
        ready=ready,
    )


_gui_teardown_registered = False


def _start_gui(project_dir: Path) -> tuple[str | None, int | None]:
    """Start the GUI server and register an atexit teardown. Returns (url, pid)."""
    global _gui_teardown_registered

    from rocketsmith.gui.lifecycle import start_gui_server, stop_gui_server

    result = start_gui_server(project_dir)

    if not _gui_teardown_registered:
        atexit.register(stop_gui_server, project_dir)
        _gui_teardown_registered = True

    if result.get("error"):
        return None, None

    return result.get("server_url"), result.get("pid")


def register_setup(app: FastMCP):
    @app.tool(name="rocketsmith_setup")
    def rocketsmith_setup(
        action: Literal["check", "install"] = "check",
        project_dir: Path | None = None,
    ) -> DependencyStatus:
        """Check or install rocketsmith dependencies (Java, OpenRocket, PrusaSlicer).

        Always call this at the start of a session with ``project_dir`` set to
        the user's project directory. This registers the project directory for
        the lifetime of the MCP server process so all subsequent tools resolve
        paths correctly without requiring an explicit ``project_dir`` argument.
        It also starts the GUI server automatically and opens the browser.

        Actions:
        - check: Return the current installation status of each dependency.
        - install: Install any missing dependencies for the current platform, then return status.

        Supported platforms for automatic install:
        - macOS: Java via Homebrew, OpenRocket JAR downloaded directly, PrusaSlicer via Homebrew cask
        - Linux: Java via apt, OpenRocket JAR downloaded directly, PrusaSlicer via Homebrew or AppImage
        - Windows: Java via winget (Temurin), OpenRocket JAR downloaded directly, PrusaSlicer via winget
        """
        gui_url = None
        gui_pid = None

        if project_dir is not None:
            from rocketsmith.mcp.utils import set_project_dir

            set_project_dir(project_dir)
            gui_url, gui_pid = _start_gui(project_dir.resolve())

        if action == "check":
            status = _check()
            status.gui_url = gui_url
            status.gui_pid = gui_pid
            return status

        # install
        from rocketsmith.openrocket.install import install as install_openrocket
        from rocketsmith.prusaslicer.install import install as install_prusaslicer

        status = _check()

        if "not found" in status.java or "not found" in status.openrocket:
            install_openrocket()

        if "not found" in status.prusaslicer:
            install_prusaslicer()

        status = _check()
        status.gui_url = gui_url
        status.gui_pid = gui_pid
        return status

    return rocketsmith_setup
