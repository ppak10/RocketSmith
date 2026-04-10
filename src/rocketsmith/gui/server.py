"""Lightweight dashboard server: static files + WebSocket push."""

import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web

from rocketsmith.gui.watcher import watch

logger = logging.getLogger(__name__)

# Directory containing the built React bundle.
_DIST_DIR = Path(__file__).resolve().parent / "web" / "dist"


def _build_app(project_dir: Path) -> web.Application:
    app = web.Application()
    app["project_dir"] = project_dir
    app["ws_clients"] = set()

    app.router.add_get("/ws", _ws_handler)
    app.router.add_get("/", _index_handler)
    # Static files for assets (JS/CSS bundles).
    app.router.add_static("/assets", _DIST_DIR / "assets")

    app.on_startup.append(_start_watcher)
    app.on_shutdown.append(_stop_watcher)
    return app


async def _index_handler(request: web.Request) -> web.FileResponse:
    return web.FileResponse(_DIST_DIR / "index.html")


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


async def _broadcast(
    app: web.Application, event_type: str, path: str, timestamp: str
) -> None:
    msg = json.dumps({"type": event_type, "path": path, "timestamp": timestamp})
    stale = set()
    for ws in app["ws_clients"]:
        try:
            await ws.send_str(msg)
        except Exception:
            stale.add(ws)
    app["ws_clients"] -= stale


async def _start_watcher(app: web.Application) -> None:
    project_dir: Path = app["project_dir"]

    async def on_change(event_type: str, path: str, timestamp: str) -> None:
        await _broadcast(app, event_type, path, timestamp)

    app["watcher_task"] = asyncio.create_task(watch(project_dir, on_change))


async def _stop_watcher(app: web.Application) -> None:
    task = app.get("watcher_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def run(project_dir: Path, port: int = 0) -> None:
    """Start the dashboard server.

    Args:
        project_dir: Project directory to watch for file changes.
        port: Port to bind to.  ``0`` picks a random available port.
    """
    app = _build_app(project_dir)
    web.run_app(app, host="127.0.0.1", port=port, print=lambda msg: logger.info(msg))
