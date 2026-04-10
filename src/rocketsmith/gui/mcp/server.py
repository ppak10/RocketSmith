from mcp.server.fastmcp import FastMCP

DEFAULT_PORT = 24880


def register_gui_server(app: FastMCP):
    from pathlib import Path
    from typing import Optional, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="gui_server",
        title="Dashboard Server",
        description=(
            "Manage the RocketSmith dashboard server. "
            "Use action='start' to launch the dashboard in the user's browser. "
            "Use action='stop' to shut down a running dashboard server by PID."
        ),
        structured_output=True,
    )
    async def gui_server(
        action: str,
        project_dir: Optional[str] = None,
        pid: Optional[int] = None,
        port: Optional[int] = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Start or stop the RocketSmith dashboard server.

        Args:
            action: Either "start" or "stop".
            project_dir: (start only) Path to the project directory to watch.
            pid: (stop only) PID of the dashboard server to stop.
            port: (start only) Port to bind to. Defaults to 24880.
        """
        if action == "start":
            return await _start(project_dir, port)
        elif action == "stop":
            return await _stop(pid)
        else:
            return tool_error(
                f"Unknown action: {action!r}. Use 'start' or 'stop'.",
                "INVALID_ACTION",
                action=action,
            )

    async def _start(
        project_dir: Optional[str],
        port: Optional[int],
    ) -> Union[ToolSuccess[dict], ToolError]:
        import subprocess
        import sys
        import time
        import webbrowser

        if project_dir is None:
            return tool_error(
                "project_dir is required for action='start'",
                "MISSING_PARAMETER",
                parameter="project_dir",
            )

        resolved = resolve_path(project_dir)

        if not resolved.exists():
            return tool_error(
                f"Project directory does not exist: {resolved}",
                "DIR_NOT_FOUND",
                project_dir=str(resolved),
            )

        if not resolved.is_dir():
            return tool_error(
                f"Path is not a directory: {resolved}",
                "NOT_A_DIRECTORY",
                project_dir=str(resolved),
            )

        bind_port = port if port is not None else DEFAULT_PORT

        cmd = [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "from rocketsmith.gui.server import run; "
                f"run(Path({str(resolved)!r}), port={bind_port})"
            ),
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return tool_error(
                f"Failed to launch dashboard server: {e}",
                "SERVER_LAUNCH_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        url = f"http://127.0.0.1:{bind_port}"

        # Give the server a moment to bind before opening the browser.
        time.sleep(0.5)
        webbrowser.open(url)

        return tool_success(
            {
                "pid": proc.pid,
                "url": url,
                "project_dir": str(resolved),
                "message": (
                    f"Dashboard launched at {url}. "
                    "The browser should open automatically. "
                    "The dashboard will update as files change in the project directory."
                ),
            }
        )

    async def _stop(
        pid: Optional[int],
    ) -> Union[ToolSuccess[dict], ToolError]:
        import os
        import signal

        if pid is None:
            return tool_error(
                "pid is required for action='stop'",
                "MISSING_PARAMETER",
                parameter="pid",
            )

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return tool_error(
                f"No process found with PID {pid}",
                "PROCESS_NOT_FOUND",
                pid=pid,
            )
        except PermissionError:
            return tool_error(
                f"Permission denied when trying to stop PID {pid}",
                "PERMISSION_DENIED",
                pid=pid,
            )

        return tool_success(
            {
                "pid": pid,
                "message": f"Dashboard server (PID {pid}) has been stopped.",
            }
        )

    return gui_server
