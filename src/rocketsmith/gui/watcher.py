"""Lightweight filesystem watcher that polls for mtime changes."""

import asyncio
import os
from pathlib import Path
from typing import Callable, Awaitable

from rocketsmith.gui.layout import (
    OPENROCKET_DIR,
    REPORTS_DIR,
    CADSMITH_DIR,
    STEP_DIR,
    IMAGES_DIR,
    GCODE_DIR,
    MANIFEST_FILE,
)

# Map layout directory names to event types.
_DIR_MAP: dict[str, str] = {
    OPENROCKET_DIR: "simulation",
    REPORTS_DIR: "report",
    CADSMITH_DIR: "script",
    STEP_DIR: "step",
    IMAGES_DIR: "image",
    GCODE_DIR: "gcode",
}

# Fallback: classify by extension when the file is not in a known directory.
_EXT_MAP: dict[str, str] = {
    ".step": "step",
    ".stp": "step",
    ".ork": "simulation",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".svg": "image",
    ".gcode": "gcode",
    ".md": "report",
}

POLL_INTERVAL_S = 1.0


def _classify(path: Path, root: Path) -> str:
    """Return the event type for a file based on its location or extension."""
    # Manifest file at the project root.
    if path.name == MANIFEST_FILE and path.parent == root:
        return "manifest"

    # Check if the file lives under a known layout directory.
    try:
        rel = path.relative_to(root)
        top_dir = rel.parts[0] if rel.parts else ""
        if top_dir in _DIR_MAP:
            return _DIR_MAP[top_dir]
    except ValueError:
        pass

    # Fallback to extension-based classification.
    return _EXT_MAP.get(path.suffix.lower(), "unknown")


def _scan(root: Path) -> dict[Path, float]:
    """Walk *root* and return {path: mtime} for every file."""
    snapshot: dict[Path, float] = {}
    try:
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                p = Path(dirpath) / fname
                try:
                    snapshot[p] = p.stat().st_mtime
                except OSError:
                    pass
    except OSError:
        pass
    return snapshot


async def watch(
    root: Path,
    on_change: Callable[[str, str, str], Awaitable[None]],
    *,
    poll_interval: float = POLL_INTERVAL_S,
) -> None:
    """Poll *root* for file changes and invoke *on_change* for each.

    ``on_change(event_type, path, timestamp)`` is awaited for every
    created or modified file detected between polls.  Deleted files are
    ignored (the dashboard only cares about new/updated content).

    This coroutine runs forever — cancel the task to stop it.
    """
    prev = _scan(root)

    while True:
        await asyncio.sleep(poll_interval)
        curr = _scan(root)

        for path, mtime in curr.items():
            old_mtime = prev.get(path)
            if old_mtime is None or mtime > old_mtime:
                event_type = _classify(path, root)
                from datetime import datetime, timezone

                ts = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                await on_change(event_type, str(path), ts)

        prev = curr
