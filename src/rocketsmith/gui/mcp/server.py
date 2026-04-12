from mcp.server.fastmcp import FastMCP

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 24880
DEV_PORT = 5173
WS_PORT = 24881
PID_FILENAME = ".gui.pid"


def register_gui_server(app: FastMCP):
    from pathlib import Path
    from typing import Optional, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="gui_server",
        title="GUI Server",
        description=(
            "Manage the RocketSmith GUI server. "
            "Use action='start' to launch the GUI in the user's browser (serves the built bundle). "
            "Use action='dev' to launch in development mode with Vite HMR for frontend hot-reloading. "
            "Use action='stop' to shut down a running GUI server by PID."
        ),
        structured_output=True,
    )
    async def gui_server(
        action: str,
        project_dir: Optional[str] = None,
        pid: Optional[int] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Start, dev, or stop the RocketSmith GUI server.

        Args:
            action: One of "start", "dev", or "stop".
            project_dir: (start/dev) Path to the project directory to watch.
            pid: (stop only) PID of the GUI server to stop.
            host: (start/dev) Host IP to bind to. Defaults to 127.0.0.1.
            port: (start only) Port to bind to. Defaults to 24880.
                  In dev mode, Vite runs on 5173 and the WebSocket server on 24881.
        """
        if action == "start":
            return await _start(project_dir, host, port)
        elif action == "dev":
            return await _dev(project_dir, host)
        elif action == "stop":
            return await _stop(pid)
        else:
            return tool_error(
                f"Unknown action: {action!r}. Use 'start', 'dev', or 'stop'.",
                "INVALID_ACTION",
                action=action,
            )

    async def _validate_project_dir(
        project_dir: Optional[str],
    ) -> Union[Path, ToolError]:
        if project_dir is None:
            return tool_error(
                "project_dir is required",
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

        return resolved

    async def _start(
        project_dir: Optional[str],
        host: Optional[str],
        port: Optional[int],
    ) -> Union[ToolSuccess[dict], ToolError]:
        import shutil
        import subprocess
        import sys
        import time
        import webbrowser

        result = await _validate_project_dir(project_dir)
        if isinstance(result, ToolError):
            return result
        resolved = result

        # Copy built GUI files into the project root.
        gui_data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "gui"
        if not gui_data_dir.is_dir():
            return tool_error(
                f"GUI build output not found at {gui_data_dir}. "
                "Run 'npm run build' in src/rocketsmith/gui/web/ first.",
                "GUI_NOT_BUILT",
            )

        copied_files = []
        for src_file in gui_data_dir.iterdir():
            if src_file.is_file():
                dst = resolved / src_file.name
                shutil.copy2(src_file, dst)
                copied_files.append(src_file.name)

        bind_host = host if host is not None else DEFAULT_HOST
        bind_port = port if port is not None else DEFAULT_PORT

        # Start the Python backend (WebSocket + API) for live updates.
        cmd = [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "from rocketsmith.gui.server import run; "
                f"run(Path({str(resolved)!r}), host={bind_host!r}, port={bind_port})"
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
                f"Failed to launch backend server: {e}",
                "SERVER_LAUNCH_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        # Write PID file so the SessionEnd hook can clean up.
        pid_file = resolved / PID_FILENAME
        pid_file.write_text(str(proc.pid))

        # Open index.html directly in the browser (file:// protocol).
        index_path = resolved / "index.html"
        time.sleep(0.5)
        webbrowser.open(index_path.as_uri())

        return tool_success(
            {
                "pid": proc.pid,
                "server_url": f"http://{bind_host}:{bind_port}",
                "project_dir": str(resolved),
                "files_copied": copied_files,
                "index": str(index_path),
                "message": (
                    f"GUI files copied to {resolved} and opened in browser. "
                    f"Backend server running at http://{bind_host}:{bind_port} "
                    "for live file updates and API access."
                ),
            }
        )

    async def _dev(
        project_dir: Optional[str],
        host: Optional[str],
    ) -> Union[ToolSuccess[dict], ToolError]:
        import subprocess
        import sys
        import time
        import webbrowser

        result = await _validate_project_dir(project_dir)
        if isinstance(result, ToolError):
            return result
        resolved = result

        bind_host = host if host is not None else DEFAULT_HOST
        web_dir = Path(__file__).resolve().parent.parent / "web"

        # 1. Start the Python WebSocket server (file watcher only, no static files).
        ws_cmd = [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "from rocketsmith.gui.server import run; "
                f"run(Path({str(resolved)!r}), host={bind_host!r}, port={WS_PORT})"
            ),
        ]

        try:
            ws_proc = subprocess.Popen(
                ws_cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return tool_error(
                f"Failed to launch WebSocket server: {e}",
                "SERVER_LAUNCH_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        # 2. Start the Vite dev server with HMR.
        vite_cmd = ["npx", "vite", "--host", bind_host, "--port", str(DEV_PORT)]

        try:
            vite_proc = subprocess.Popen(
                vite_cmd,
                cwd=str(web_dir),
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            # Clean up the WS server if Vite fails to start.
            import os
            import signal

            os.kill(ws_proc.pid, signal.SIGTERM)
            return tool_error(
                f"Failed to launch Vite dev server: {e}",
                "VITE_LAUNCH_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        # Write both PIDs so the SessionEnd hook can clean up.
        pid_file = resolved / PID_FILENAME
        pid_file.write_text(f"{vite_proc.pid}\n{ws_proc.pid}")

        url = f"http://{bind_host}:{DEV_PORT}"

        time.sleep(1.0)
        webbrowser.open(url)

        return tool_success(
            {
                "vite_pid": vite_proc.pid,
                "ws_pid": ws_proc.pid,
                "url": url,
                "ws_url": f"ws://{bind_host}:{WS_PORT}/ws",
                "project_dir": str(resolved),
                "message": (
                    f"GUI dev server launched at {url} (Vite HMR). "
                    f"WebSocket server on port {WS_PORT}. "
                    "Frontend changes will hot-reload automatically."
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
            # Kill the entire process group. The server was started with
            # start_new_session=True, so PID == PGID. This ensures child
            # processes (node under npx, asyncio tasks) are also terminated.
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            # Process group gone — try the individual PID as fallback.
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
                "message": f"GUI server (PID {pid}) has been stopped.",
            }
        )

    return gui_server
