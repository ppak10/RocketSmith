"""Lightweight gui server: static files + WebSocket push."""

import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web

from rocketsmith.gui.watcher import watch

logger = logging.getLogger(__name__)

# Directory containing the built React bundle (compiled into data/gui/).
_DIST_DIR = Path(__file__).resolve().parent.parent / "data" / "gui"


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
    _VISIBLE_DIRS = {
        "openrocket",
        "cadsmith",
        "step",
        "stl",
        "gcode",
        "parts",
        "png",
        "gif",
        "txt",
        "progress",
        "logs",
    }
    _VISIBLE_ROOT_FILES = {"assembly.json", "component_tree.json"}

    def _build_tree(root: Path, rel_prefix: str = "") -> list[dict]:
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

    tree = _build_tree(project_dir)
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

    # Event type labels for the session log.
    _TYPE_VERBS = {
        "openrocket": "Updating design",
        "cadsmith": "Writing script",
        "step": "Generating",
        "stl": "Exporting",
        "gcode": "Slicing",
        "parts": "Extracting",
        "manifest": "Building manifest",
        "assembly": "Building assembly",
        "preview": "Rendering",
    }

    async def on_change(event: dict) -> None:
        await _broadcast(app, event)

        # Auto-log watcher events to session.jsonl (skip logs/ to avoid loops).
        rel = event.get("relative_path", "")
        etype = event.get("type", "")
        if rel and not rel.startswith("logs/"):
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
