from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel


class DependencyStatus(BaseModel):
    java: str
    openrocket: str
    prusaslicer: str
    ready: bool


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


def register_setup(app: FastMCP):
    @app.tool(name="rocketsmith_setup")
    def rocketsmith_setup(
        action: Literal["check", "install"] = "check",
    ) -> DependencyStatus:
        """Check or install rocketsmith dependencies (Java, OpenRocket, PrusaSlicer).

        Actions:
        - check: Return the current installation status of each dependency.
        - install: Install any missing dependencies for the current platform, then return status.

        Supported platforms for automatic install:
        - macOS: Java via Homebrew, OpenRocket JAR downloaded directly, PrusaSlicer via Homebrew cask
        - Linux: Java via apt, OpenRocket JAR downloaded directly, PrusaSlicer via Homebrew or AppImage
        - Windows: Java via winget (Temurin), OpenRocket JAR downloaded directly, PrusaSlicer via winget
        """
        if action == "check":
            return _check()

        # install
        from rocketsmith.openrocket.install import install as install_openrocket
        from rocketsmith.prusaslicer.install import install as install_prusaslicer

        status = _check()

        if "not found" in status.java or "not found" in status.openrocket:
            install_openrocket()

        if "not found" in status.prusaslicer:
            install_prusaslicer()

        return _check()

    return rocketsmith_setup
