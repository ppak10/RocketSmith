"""Lightweight gui server: static files + WebSocket push."""

import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web

from rocketsmith.gui.watcher import watch, build_snapshot_events
from rocketsmith.gui.layout import GUI_DIR, GUI_DATA_JS

logger = logging.getLogger(__name__)

# Directory containing the built React bundle (compiled into data/gui/).
_DIST_DIR = Path(__file__).resolve().parent.parent / "data" / "gui"

# Whitelists for the file tree exposed to the GUI.
_VISIBLE_DIRS = {
    "openrocket",
    "cadsmith",
    "gui",
    "prusaslicer",
}
_VISIBLE_ROOT_FILES: set[str] = set()

FILES_TREE_FILE = "gui/files-tree.json"


def _build_tree(root: Path, rel_prefix: str = "") -> list[dict]:
    """Build a recursive file tree of the project directory."""
    entries: list[dict] = []
    try:
        items = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    except OSError:
        return entries
    for item in items:
        if item.name.startswith("."):
            continue
        # At the top level, only show whitelisted folders and files.
        if not rel_prefix:
            if item.is_dir() and item.name not in _VISIBLE_DIRS:
                continue
            if item.is_file() and item.name not in _VISIBLE_ROOT_FILES:
                continue
        rel = (
            f"{rel_prefix}{item.name}"
            if not rel_prefix
            else f"{rel_prefix}/{item.name}"
        )
        if item.is_dir():
            children = _build_tree(item, rel)
            if children:
                entries.append(
                    {
                        "name": item.name,
                        "type": "directory",
                        "path": rel,
                        "children": children,
                    }
                )
        else:
            entries.append({"name": item.name, "type": "file", "path": rel})
    return entries


def write_files_tree_snapshot(project_dir: Path) -> None:
    """Write a files-tree.json snapshot for offline GUI use."""
    tree = _build_tree(project_dir)
    out = project_dir / FILES_TREE_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.write_text(json.dumps(tree))
    except OSError:
        logger.debug("Failed to write %s", out)


# Text extensions that are safe to inline into the offline data bundle.
_TEXT_EXTENSIONS = {
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".csv",
    ".txt",
    ".ini",
    ".cfg",
    ".toml",
    ".yaml",
    ".yml",
    ".gcode",
}

# Binary extensions to base64-encode into the offline bundle.
_BINARY_EXTENSIONS = {".stl"}

# Max size for a single file to be inlined (500 KB).
_MAX_INLINE_SIZE = 500_000


def _sanitize(obj):
    """Replace NaN/Infinity floats with None for JSON serialization."""
    import math

    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _collect_offline_files(project_dir: Path, tree: list[dict]) -> dict:
    """Walk the file tree and read all text/binary files into a dict keyed by relative path.

    Text files are stored as strings (JSON files are parsed + sanitized).
    Binary files (e.g. STL) are stored as ``{"__b64__": "<base64>"}`` so the
    frontend can convert them to blob URLs.
    """
    import base64

    files: dict = {}

    def _walk(nodes: list[dict]) -> None:
        for node in nodes:
            if node["type"] == "directory":
                _walk(node.get("children", []))
            else:
                rel = node["path"]
                full = project_dir / rel
                ext = full.suffix.lower()
                is_text = ext in _TEXT_EXTENSIONS
                is_binary = ext in _BINARY_EXTENSIONS
                if not is_text and not is_binary:
                    continue
                try:
                    if full.stat().st_size > _MAX_INLINE_SIZE:
                        continue
                except OSError:
                    continue

                if is_binary:
                    try:
                        raw = full.read_bytes()
                        files[rel] = {"__b64__": base64.b64encode(raw).decode("ascii")}
                    except OSError:
                        continue
                else:
                    try:
                        text = full.read_text(errors="replace")
                    except OSError:
                        continue
                    if ext == ".json":
                        try:
                            files[rel] = _sanitize(json.loads(text))
                        except json.JSONDecodeError:
                            files[rel] = text
                    else:
                        files[rel] = text

    _walk(tree)
    return files


def write_offline_data(project_dir: Path) -> None:
    """Write data.js containing all JSON/text data for file:// use.

    This file is loaded via a <script> tag (which works over file://,
    unlike fetch) and populates window.__OFFLINE_DATA__.
    """
    tree = _build_tree(project_dir)
    files = _collect_offline_files(project_dir, tree)

    payload = {
        "filesTree": tree,
        "projectInfo": {"name": project_dir.name, "path": str(project_dir)},
        "files": files,
    }

    js = (
        "window.__OFFLINE_DATA__ = "
        + json.dumps(payload, separators=(",", ":"))
        + ";\n"
    )
    out = project_dir / GUI_DATA_JS
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.write_text(js)
    except OSError:
        logger.debug("Failed to write %s", out)


_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


@web.middleware
async def _cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers=_CORS_HEADERS)
    response = await handler(request)
    response.headers.update(_CORS_HEADERS)
    return response


def _build_app(project_dir: Path) -> web.Application:
    app = web.Application(middlewares=[_cors_middleware])
    app["project_dir"] = project_dir
    app["ws_clients"] = set()
    app.router.add_get("/ws", _ws_handler)
    app.router.add_get("/api/project-info", _project_info_handler)
    app.router.add_get("/api/files/{path:.*}", _project_file_handler)
    app.router.add_post("/api/navigate", _navigate_handler)
    app.router.add_get("/api/files-tree", _files_tree_handler)

    app.on_startup.append(_start_watcher)
    app.on_shutdown.append(_stop_watcher)
    return app


async def _project_info_handler(request: web.Request) -> web.Response:
    """Return the project directory path so the frontend knows the root."""
    project_dir: Path = request.app["project_dir"]
    return web.json_response({"project_dir": str(project_dir)})


async def _project_file_handler(request: web.Request) -> web.Response:
    """Serve a file from the project directory.

    The path is relative to the project root. Only files inside the
    project directory are served (path traversal is rejected).
    """
    project_dir: Path = request.app["project_dir"]
    rel_path = request.match_info["path"]
    file_path = (project_dir / rel_path).resolve()

    # Guard against path traversal.
    if not str(file_path).startswith(str(project_dir.resolve())):
        return web.Response(status=403, text="Forbidden")

    if not file_path.is_file():
        return web.Response(status=404, text="Not found")

    # JSON files may contain Python-style NaN/Infinity which are not valid
    # JSON for browsers.  Re-serialize through Python's json module to
    # replace them with null.
    if file_path.suffix.lower() == ".json":
        import json
        import math

        try:
            with open(file_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return web.FileResponse(file_path)

        def _sanitize(obj):
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_sanitize(v) for v in obj]
            return obj

        return web.json_response(_sanitize(data))

    return web.FileResponse(file_path)


async def _files_tree_handler(request: web.Request) -> web.Response:
    """Return a recursive file tree of the project directory."""
    project_dir: Path = request.app["project_dir"]
    tree = _build_tree(project_dir)
    # Keep the offline snapshot fresh.
    write_files_tree_snapshot(project_dir)
    return web.json_response(tree)


async def _navigate_handler(request: web.Request) -> web.Response:
    """Receive a navigation command and broadcast it to all WebSocket clients."""
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    command = {
        "command": "navigate",
        "path": data.get("path"),
    }
    await _broadcast(request.app, command)
    return web.json_response({"ok": True})


async def _ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Replay current project state so the client doesn't start empty.
    project_dir: Path = request.app["project_dir"]
    try:
        snapshot = build_snapshot_events(project_dir)
        for event in snapshot:
            await ws.send_str(json.dumps(event))
        # Also send the current file tree.
        tree = _build_tree(project_dir)
        await ws.send_str(json.dumps({"type": "files-tree", "tree": tree}))
    except Exception:
        pass  # Best-effort — don't fail the connection.

    request.app["ws_clients"].add(ws)
    try:
        async for _ in ws:
            pass  # Read-only — ignore any messages from the client.
    finally:
        request.app["ws_clients"].discard(ws)
    return ws


async def _broadcast(app: web.Application, event: dict) -> None:
    msg = json.dumps(event)
    stale = set()
    for ws in app["ws_clients"]:
        try:
            await ws.send_str(msg)
        except Exception:
            stale.add(ws)
    app["ws_clients"] -= stale


async def _start_watcher(app: web.Application) -> None:
    project_dir: Path = app["project_dir"]

    # Write initial snapshots.
    write_files_tree_snapshot(project_dir)
    write_offline_data(project_dir)

    # Event type labels for the session log.
    _TYPE_VERBS = {
        "openrocket": "Updating design",
        "flight": "Running flight",
        "cadsmith": "Writing script",
        "step": "Generating",
        "stl": "Exporting",
        "gcode": "Slicing",
        "parts": "Extracting",
        "manifest": "Building manifest",
        "assembly": "Building assembly",
        "preview": "Rendering",
    }

    # Debounced snapshot writer — at most once every 5 seconds.
    _snapshot_handle: asyncio.TimerHandle | None = None

    async def _write_and_broadcast() -> None:
        tree = _build_tree(project_dir)
        write_files_tree_snapshot(project_dir)
        write_offline_data(project_dir)
        # Push the updated tree to connected clients so the sidebar refreshes.
        await _broadcast(app, {"type": "files-tree", "tree": tree})

    def _schedule_snapshot() -> None:
        nonlocal _snapshot_handle
        if _snapshot_handle is not None:
            _snapshot_handle.cancel()
        loop = asyncio.get_event_loop()
        _snapshot_handle = loop.call_later(
            5.0, lambda: asyncio.ensure_future(_write_and_broadcast())
        )

    async def on_change(event: dict) -> None:
        await _broadcast(app, event)
        _schedule_snapshot()

        # Auto-log watcher events to session.jsonl (skip logs/ to avoid loops).
        rel = event.get("relative_path", "")
        etype = event.get("type", "")
        if rel and not rel.startswith("gui/logs/"):
            from rocketsmith.gui.log import gui_log

            filename = rel.split("/")[-1] if "/" in rel else rel
            verb = _TYPE_VERBS.get(etype, "Processing")
            try:
                gui_log(project_dir, etype or "file", f"{verb} {filename}")
            except Exception:
                pass

    app["watcher_task"] = asyncio.create_task(watch(project_dir, on_change))


async def _stop_watcher(app: web.Application) -> None:
    task = app.get("watcher_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def run(project_dir: Path, host: str = "127.0.0.1", port: int = 0) -> None:
    """Start the gui server.

    Args:
        project_dir: Project directory to watch for file changes.
        host: Host IP to bind to.  Defaults to ``127.0.0.1``.
        port: Port to bind to.  ``0`` picks a random available port.
    """
    app = _build_app(project_dir)
    web.run_app(app, host=host, port=port, print=lambda msg: logger.info(msg))
