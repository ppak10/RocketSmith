import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 24880
DEV_PORT = 5173
WS_PORT = 24881
PID_FILENAME = "gui/.gui.pid"
DEV_PID_FILENAME = "gui/.gui-dev.pid"


# ── Process / port helpers ────────────────────────────────────────────────────


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def _read_pid_file(pid_file: Path) -> list[int]:
    if not pid_file.is_file():
        return []
    try:
        text = pid_file.read_text().strip()
        return [int(line) for line in text.splitlines() if line.strip().isdigit()]
    except (OSError, ValueError):
        return []


def _cleanup_pid_file(pid_file: Path) -> None:
    try:
        pid_file.unlink(missing_ok=True)
    except OSError:
        pass


def _kill_pid(pid: int) -> bool:
    if pid == os.getpid():
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _kill_all_from_pid_file(pid_file: Path) -> list[int]:
    pids = _read_pid_file(pid_file)
    killed = [p for p in pids if _kill_pid(p)]
    _cleanup_pid_file(pid_file)
    return killed


def check_existing_servers(pid_file: Path, host: str, ports: list[int]) -> str:
    """Return 'healthy', 'stale', 'port_conflict', or 'none'."""
    pids = _read_pid_file(pid_file)
    ports_busy = [_is_port_in_use(p, host) for p in ports]

    if not pids:
        return "port_conflict" if any(ports_busy) else "none"

    if all(_is_pid_alive(p) for p in pids) and all(ports_busy):
        return "healthy"

    for p in pids:
        _kill_pid(p)
    _cleanup_pid_file(pid_file)
    return "port_conflict" if any(_is_port_in_use(p, host) for p in ports) else "stale"


# ── Public lifecycle API ──────────────────────────────────────────────────────


def start_gui_server(
    project_dir: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    """Start the GUI server for *project_dir*.

    Copies the built bundle into the project, writes offline snapshots,
    spawns the Python WebSocket/API backend, and opens ``index.html`` in
    the browser.

    Returns a status dict with keys:
        pid (int | None), server_url (str), reused (bool), error (str | None)

    Never raises — failures are surfaced via the ``error`` key so callers
    can decide whether to treat them as fatal.
    """
    pid_file = project_dir / PID_FILENAME
    state = check_existing_servers(pid_file, host, [port])

    if state == "healthy":
        pids = _read_pid_file(pid_file)
        return {
            "pid": pids[0] if pids else None,
            "server_url": f"http://{host}:{port}",
            "reused": True,
            "error": None,
        }

    if state == "port_conflict":
        return {
            "pid": None,
            "server_url": None,
            "reused": False,
            "error": f"Port {port} is already in use by another process.",
        }

    # Copy built GUI files (index.html → project root, rest → gui/).
    gui_data_dir = Path(__file__).resolve().parent.parent / "data" / "gui"
    if not gui_data_dir.is_dir():
        return {
            "pid": None,
            "server_url": None,
            "reused": False,
            "error": (
                f"GUI build output not found at {gui_data_dir}. "
                "Run 'npm run build' in src/rocketsmith/gui/web/ first."
            ),
        }

    gui_dir = project_dir / "gui"
    gui_dir.mkdir(parents=True, exist_ok=True)

    for src_file in gui_data_dir.iterdir():
        if src_file.is_file():
            dst = (
                project_dir / src_file.name
                if src_file.name == "index.html"
                else gui_dir / src_file.name
            )
            shutil.copy2(src_file, dst)

    # Write offline data snapshots (non-fatal if they fail).
    try:
        from rocketsmith.gui.server import write_files_tree_snapshot, write_offline_data

        write_files_tree_snapshot(project_dir)
        write_offline_data(project_dir)
    except Exception:
        pass

    # Spawn the Python backend.
    cmd = [
        sys.executable,
        "-c",
        (
            "from pathlib import Path; "
            "from rocketsmith.gui.server import run; "
            f"run(Path({str(project_dir)!r}), host={host!r}, port={port})"
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
        return {
            "pid": None,
            "server_url": None,
            "reused": False,
            "error": f"Failed to launch backend server: {e}",
        }

    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(proc.pid))

    time.sleep(0.5)
    webbrowser.open((project_dir / "index.html").as_uri())

    return {
        "pid": proc.pid,
        "server_url": f"http://{host}:{port}",
        "reused": False,
        "error": None,
    }


def stop_gui_server(project_dir: Path) -> list[int]:
    """Kill all GUI server processes (production + dev) for *project_dir*.

    Reads PID files, sends SIGTERM to each listed process, and removes the
    PID files. Returns the list of PIDs that were successfully signalled.
    """
    killed: list[int] = []
    killed.extend(_kill_all_from_pid_file(project_dir / PID_FILENAME))
    killed.extend(_kill_all_from_pid_file(project_dir / DEV_PID_FILENAME))
    return killed
