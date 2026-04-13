import os
import signal
import socket
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 24880
DEV_PORT = 5173
WS_PORT = 24881
PID_FILENAME = "gui/.gui.pid"
DEV_PID_FILENAME = "gui/.gui-dev.pid"


# ── Lifecycle helpers ─────────────────────────────────────────────────────────


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if *port* is already bound on *host*."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def _read_pid_file(pid_file: Path) -> list[int]:
    """Parse the PID file and return a list of integer PIDs."""
    if not pid_file.is_file():
        return []
    try:
        text = pid_file.read_text().strip()
        return [int(line) for line in text.splitlines() if line.strip().isdigit()]
    except (OSError, ValueError):
        return []


def _cleanup_pid_file(pid_file: Path) -> None:
    """Remove the PID file if it exists."""
    try:
        pid_file.unlink(missing_ok=True)
    except OSError:
        pass


def _kill_pid(pid: int) -> bool:
    """Kill a process group (PID == PGID), falling back to individual kill.

    Safety: never kills our own process group.
    """
    # Guard: don't kill our own process group.
    if pid == os.getpid() or pid == os.getpgrp():
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        pass
    except (PermissionError, OSError):
        pass
    # Fallback: kill the individual process.
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return False


def _kill_all_from_pid_file(pid_file: Path) -> list[int]:
    """Read the PID file, kill every listed process, clean up. Return killed PIDs."""
    pids = _read_pid_file(pid_file)
    killed = []
    for p in pids:
        if _kill_pid(p):
            killed.append(p)
    _cleanup_pid_file(pid_file)
    return killed


def _check_existing_servers(
    pid_file: Path,
    host: str,
    ports: list[int],
) -> str:
    """Check the state of previously launched servers.

    Returns:
        ``"healthy"`` — PIDs alive and all ports occupied. Reuse them.
        ``"stale"``   — PIDs dead or ports free. Safe to relaunch.
        ``"port_conflict"`` — PIDs dead but ports still occupied by something else.
        ``"none"``    — No PID file and ports are free.
    """
    pids = _read_pid_file(pid_file)
    ports_busy = [_is_port_in_use(p, host) for p in ports]

    if not pids:
        if any(ports_busy):
            return "port_conflict"
        return "none"

    all_alive = all(_is_pid_alive(p) for p in pids)
    all_busy = all(ports_busy)

    if all_alive and all_busy:
        return "healthy"

    # Partially alive or ports freed — kill everything and clean up.
    for p in pids:
        _kill_pid(p)
    _cleanup_pid_file(pid_file)

    # After cleanup, re-check ports.
    if any(_is_port_in_use(p, host) for p in ports):
        return "port_conflict"

    return "stale"


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
            "Use action='start' to launch the GUI in the user's browser (serves the built bundle). "
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
        port: Optional[int] = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Start, dev, or stop the RocketSmith GUI server.

        Args:
            action: One of "start", "dev", or "stop".
            project_dir: (start/dev/stop) Path to the project directory.
            pid: (stop only) PID of a specific GUI server process to stop.
                 If omitted, reads the PID file from project_dir.
            host: (start/dev) Host IP to bind to. Defaults to 127.0.0.1.
            port: (start only) Port to bind to. Defaults to 24880.
                  In dev mode, Vite runs on 5173 and the WebSocket server on 24881.
        """
        if action == "start":
            return await _start(project_dir, host, port)
        elif action == "dev":
            return await _dev(project_dir, host)
        elif action == "stop":
            return await _stop(pid, project_dir)
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

    def _port_conflict_error(ports: list[int]):
        busy = [p for p in ports if _is_port_in_use(p)]
        return tool_error(
            f"Port(s) {', '.join(str(p) for p in busy)} already in use by another process. "
            f"Run 'lsof -i :{busy[0]}' to find the owner.",
            "PORTS_OCCUPIED",
            ports=busy,
        )

    # ── start (production) ────────────────────────────────────────────────

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

        bind_host = host if host is not None else DEFAULT_HOST
        bind_port = port if port is not None else DEFAULT_PORT
        pid_file = resolved / PID_FILENAME

        # Check for existing servers.
        state = _check_existing_servers(pid_file, bind_host, [bind_port])
        if state == "healthy":
            pids = _read_pid_file(pid_file)
            return tool_success(
                {
                    "pid": pids[0] if pids else None,
                    "server_url": f"http://{bind_host}:{bind_port}",
                    "project_dir": str(resolved),
                    "reused": True,
                    "message": (
                        f"Backend server already running at http://{bind_host}:{bind_port}. "
                        "Reusing existing process."
                    ),
                }
            )
        if state == "port_conflict":
            return _port_conflict_error([bind_port])

        # Copy built GUI files into the project.
        # index.html goes to the project root; main.js goes to gui/.
        gui_data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "gui"
        if not gui_data_dir.is_dir():
            return tool_error(
                f"GUI build output not found at {gui_data_dir}. "
                "Run 'npm run build' in src/rocketsmith/gui/web/ first.",
                "GUI_NOT_BUILT",
            )

        gui_dir = resolved / "gui"
        gui_dir.mkdir(parents=True, exist_ok=True)

        copied_files = []
        for src_file in gui_data_dir.iterdir():
            if src_file.is_file():
                if src_file.name == "index.html":
                    dst = resolved / src_file.name
                else:
                    dst = gui_dir / src_file.name
                shutil.copy2(src_file, dst)
                copied_files.append(src_file.name)

        # Write offline data snapshots for file:// mode.
        from rocketsmith.gui.server import write_files_tree_snapshot, write_offline_data

        write_files_tree_snapshot(resolved)
        write_offline_data(resolved)

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

        # Write PID file.
        pid_file.parent.mkdir(parents=True, exist_ok=True)
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

    # ── dev ────────────────────────────────────────────────────────────────

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
        dev_pid_file = resolved / DEV_PID_FILENAME
        prod_pid_file = resolved / PID_FILENAME

        # Check if a dev server is already running.
        dev_state = _check_existing_servers(dev_pid_file, bind_host, [DEV_PORT])
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

        # Check if Vite port is taken by something else.
        if _is_port_in_use(DEV_PORT, bind_host):
            return _port_conflict_error([DEV_PORT])

        # Detect whether a production server is already running.
        # If so, piggyback on it — Vite proxies to the production WS server.
        prod_running = (
            _read_pid_file(prod_pid_file)
            and all(_is_pid_alive(p) for p in _read_pid_file(prod_pid_file))
            and _is_port_in_use(DEFAULT_PORT, bind_host)
        )

        ws_port = DEFAULT_PORT if prod_running else WS_PORT
        ws_pid = None

        if not prod_running:
            # No production server — start our own WS server.
            if _is_port_in_use(WS_PORT, bind_host):
                return _port_conflict_error([WS_PORT])

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

        # Start the Vite dev server with HMR.
        # Pass the WS port so vite.config.ts proxies to the right backend.
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

        # Write dev PID file (separate from production).
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
        # Strategy 1: project_dir provided — kill both prod and dev servers.
        if project_dir is not None:
            result = await _validate_project_dir(project_dir)
            if isinstance(result, ToolError):
                return result
            resolved = result
            killed: list[int] = []
            killed.extend(_kill_all_from_pid_file(resolved / PID_FILENAME))
            killed.extend(_kill_all_from_pid_file(resolved / DEV_PID_FILENAME))
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

        # Strategy 2: single PID provided — kill that process.
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
