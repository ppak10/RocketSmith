from pathlib import Path

from mcp.server.fastmcp import FastMCP

from rocketsmith.gui.lifecycle import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEV_PID_FILENAME,
    DEV_PORT,
    WS_PORT,
    PID_FILENAME,
    _is_pid_alive,
    _is_port_in_use,
    _kill_pid,
    _read_pid_file,
    _kill_all_from_pid_file,
    check_existing_servers,
    stop_gui_server,
)


# ── MCP tool registration ────────────────────────────────────────────────────


def register_gui_server(app: FastMCP):
    from typing import Optional, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="gui_server",
        title="GUI Server",
        description=(
            "Manage the RocketSmith GUI server. "
            "The server is started automatically by rocketsmith_setup — you do not "
            "need to start it manually. "
            "Use action='dev' to launch in development mode with Vite HMR for frontend hot-reloading. "
            "Use action='stop' to shut down a running GUI server. "
            "Pass project_dir to stop (reads the PID file automatically) or pid to stop a specific process."
        ),
        structured_output=True,
    )
    async def gui_server(
        action: str,
        project_dir: Optional[str] = None,
        pid: Optional[int] = None,
        host: Optional[str] = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Manage the RocketSmith GUI server (dev mode and stop only).

        The production GUI server is started automatically by rocketsmith_setup.

        Args:
            action: One of "dev" or "stop".
            project_dir: (dev/stop) Path to the project directory.
            pid: (stop only) PID of a specific GUI server process to stop.
                 If omitted, reads the PID file from project_dir.
            host: (dev) Host IP to bind to. Defaults to 127.0.0.1.
        """
        if action == "dev":
            return await _dev(project_dir, host)
        elif action == "stop":
            return await _stop(pid, project_dir)
        elif action == "start":
            return tool_error(
                "action='start' is no longer supported on gui_server. "
                "The GUI server is started automatically by rocketsmith_setup. "
                "Call rocketsmith_setup(action='check', project_dir='<path>') instead.",
                "DEPRECATED",
                action=action,
            )
        else:
            return tool_error(
                f"Unknown action: {action!r}. Use 'dev' or 'stop'.",
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

    def _port_conflict_error(ports: list[int]):
        busy = [p for p in ports if _is_port_in_use(p)]
        return tool_error(
            f"Port(s) {', '.join(str(p) for p in busy)} already in use by another process. "
            f"Run 'lsof -i :{busy[0]}' to find the owner.",
            "PORTS_OCCUPIED",
            ports=busy,
        )

    # ── dev ────────────────────────────────────────────────────────────────

    async def _dev(
        project_dir: Optional[str],
        host: Optional[str],
    ) -> Union[ToolSuccess[dict], ToolError]:
        import subprocess
        import time
        import webbrowser

        result = await _validate_project_dir(project_dir)
        if isinstance(result, ToolError):
            return result
        resolved = result

        bind_host = host if host is not None else DEFAULT_HOST
        dev_pid_file = resolved / DEV_PID_FILENAME
        prod_pid_file = resolved / PID_FILENAME

        # Check if a dev server is already running.
        dev_state = check_existing_servers(dev_pid_file, bind_host, [DEV_PORT])
        if dev_state == "healthy":
            pids = _read_pid_file(dev_pid_file)
            url = f"http://{bind_host}:{DEV_PORT}"
            return tool_success(
                {
                    "vite_pid": pids[0] if pids else None,
                    "url": url,
                    "project_dir": str(resolved),
                    "reused": True,
                    "message": f"Dev server already running at {url}. Reusing.",
                }
            )

        if _is_port_in_use(DEV_PORT, bind_host):
            return _port_conflict_error([DEV_PORT])

        # Piggyback on a running production server if available.
        prod_running = (
            _read_pid_file(prod_pid_file)
            and all(_is_pid_alive(p) for p in _read_pid_file(prod_pid_file))
            and _is_port_in_use(DEFAULT_PORT, bind_host)
        )

        ws_port = DEFAULT_PORT if prod_running else WS_PORT
        ws_pid = None

        if not prod_running:
            if _is_port_in_use(WS_PORT, bind_host):
                return _port_conflict_error([WS_PORT])

            import sys

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
                ws_pid = ws_proc.pid
            except Exception as e:
                return tool_error(
                    f"Failed to launch WebSocket server: {e}",
                    "SERVER_LAUNCH_FAILED",
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                )

        web_dir = Path(__file__).resolve().parent.parent / "web"

        vite_env = {**subprocess.os.environ, "VITE_WS_PORT": str(ws_port)}
        vite_cmd = ["npx", "vite", "--host", bind_host, "--port", str(DEV_PORT)]

        try:
            vite_proc = subprocess.Popen(
                vite_cmd,
                cwd=str(web_dir),
                env=vite_env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            if ws_pid:
                _kill_pid(ws_pid)
            return tool_error(
                f"Failed to launch Vite dev server: {e}",
                "VITE_LAUNCH_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        dev_pid_file.parent.mkdir(parents=True, exist_ok=True)
        pids_to_write = [str(vite_proc.pid)]
        if ws_pid:
            pids_to_write.append(str(ws_pid))
        dev_pid_file.write_text("\n".join(pids_to_write))

        url = f"http://{bind_host}:{DEV_PORT}"
        time.sleep(1.0)
        webbrowser.open(url)

        return tool_success(
            {
                "vite_pid": vite_proc.pid,
                "ws_pid": ws_pid,
                "ws_port": ws_port,
                "url": url,
                "ws_url": f"ws://{bind_host}:{ws_port}/ws",
                "project_dir": str(resolved),
                "piggyback": prod_running,
                "message": (
                    f"GUI dev server launched at {url} (Vite HMR). "
                    f"{'Proxying to existing production server on port ' + str(DEFAULT_PORT) if prod_running else 'WebSocket server on port ' + str(WS_PORT)}. "
                    "Frontend changes will hot-reload automatically."
                ),
            }
        )

    # ── stop ───────────────────────────────────────────────────────────────

    async def _stop(
        pid: Optional[int],
        project_dir: Optional[str],
    ) -> Union[ToolSuccess[dict], ToolError]:
        if project_dir is not None:
            result = await _validate_project_dir(project_dir)
            if isinstance(result, ToolError):
                return result
            resolved = result
            killed = stop_gui_server(resolved)
            if not killed:
                return tool_error(
                    f"No running GUI servers found for {resolved}",
                    "PROCESS_NOT_FOUND",
                    project_dir=str(resolved),
                )
            return tool_success(
                {
                    "killed_pids": killed,
                    "project_dir": str(resolved),
                    "message": (
                        f"Stopped {len(killed)} GUI server process(es): "
                        f"{', '.join(str(p) for p in killed)}."
                    ),
                }
            )

        if pid is not None:
            if _kill_pid(pid):
                return tool_success(
                    {
                        "killed_pids": [pid],
                        "message": f"GUI server (PID {pid}) has been stopped.",
                    }
                )
            return tool_error(
                f"No process found with PID {pid}",
                "PROCESS_NOT_FOUND",
                pid=pid,
            )

        return tool_error(
            "Either project_dir or pid is required for action='stop'.",
            "MISSING_PARAMETER",
            parameter="project_dir or pid",
        )

    return gui_server
