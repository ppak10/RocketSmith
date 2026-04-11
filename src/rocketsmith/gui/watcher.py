"""Lightweight filesystem watcher that polls for mtime changes."""

import asyncio
import os
from pathlib import Path
from typing import Callable, Awaitable, Optional

from rocketsmith.gui.layout import (
    OPENROCKET_DIR,
    PARTS_DIR,
    PREVIEWS_DIR,
    TREE_FILE,
    ASSEMBLY_FILE,
)

# Map layout directory names to event types.
_DIR_MAP: dict[str, str] = {
    OPENROCKET_DIR: "flight",
    PARTS_DIR: "parts",
    PREVIEWS_DIR: "preview",
}

# Fallback: classify by extension when the file is not in a known directory.
_EXT_MAP: dict[str, str] = {
    ".step": "step",
    ".stp": "step",
    ".ork": "flight",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".svg": "image",
    ".gcode": "gcode",
    ".md": "report",
}

# Extensions whose content we snapshot for diff support.
_TEXT_EXTENSIONS: set[str] = {
    ".json",
    ".md",
    ".py",
    ".csv",
    ".txt",
    ".ini",
    ".cfg",
    ".toml",
    ".yaml",
    ".yml",
}

# Don't snapshot files larger than this (bytes).
_MAX_SNAPSHOT_SIZE = 100_000

POLL_INTERVAL_S = 1.0

# Files to exclude from watch events.
IGNORED_FILES: set[str] = {
    ".gui.pid",
    "settings.local.json",
}


def _classify(path: Path, root: Path) -> str:
    """Return the event type for a file based on its location or extension."""
    if path.name == TREE_FILE and path.parent == root:
        return "manifest"
    if path.name == ASSEMBLY_FILE and path.parent == root:
        return "assembly"

    try:
        rel = path.relative_to(root)
        top_dir = rel.parts[0] if rel.parts else ""
        if top_dir in _DIR_MAP:
            return _DIR_MAP[top_dir]
    except ValueError:
        pass

    return _EXT_MAP.get(path.suffix.lower(), "unknown")


def _is_text_file(path: Path) -> bool:
    return path.suffix.lower() in _TEXT_EXTENSIONS


def _read_text_safe(path: Path) -> Optional[str]:
    """Read a text file if it's small enough, else return None."""
    try:
        if path.stat().st_size > _MAX_SNAPSHOT_SIZE:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


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
    on_change: Callable[[dict], Awaitable[None]],
    *,
    poll_interval: float = POLL_INTERVAL_S,
) -> None:
    """Poll *root* for file changes and invoke *on_change* for each.

    ``on_change(event)`` is awaited for every created or modified file
    detected between polls.  The event dict contains:

    - ``type``: event classification string
    - ``path``: absolute path
    - ``relative_path``: path relative to root
    - ``timestamp``: ISO 8601 timestamp
    - ``content``: current file text (text files under 100KB only, else null)
    - ``previous_content``: text from the prior snapshot (null on first change)

    Deleted files are ignored.

    This coroutine runs forever — cancel the task to stop it.
    """
    from datetime import datetime, timezone

    prev_mtimes = _scan(root)
    # Content snapshots for text files: {path: content_string}
    prev_contents: dict[Path, str] = {}

    # Seed initial content snapshots for files that already exist.
    for path in prev_mtimes:
        if _is_text_file(path):
            content = _read_text_safe(path)
            if content is not None:
                prev_contents[path] = content

    while True:
        await asyncio.sleep(poll_interval)
        curr_mtimes = _scan(root)

        for path, mtime in curr_mtimes.items():
            old_mtime = prev_mtimes.get(path)
            if old_mtime is None or mtime > old_mtime:
                if path.name in IGNORED_FILES:
                    continue
                event_type = _classify(path, root)
                ts = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                try:
                    rel = str(path.relative_to(root))
                except ValueError:
                    rel = str(path)

                content: Optional[str] = None
                previous_content: Optional[str] = None

                if _is_text_file(path):
                    content = _read_text_safe(path)
                    previous_content = prev_contents.get(path)
                    if content is not None:
                        prev_contents[path] = content

                await on_change(
                    {
                        "type": event_type,
                        "path": str(path),
                        "relative_path": rel,
                        "timestamp": ts,
                        "content": content,
                        "previous_content": previous_content,
                    }
                )

        prev_mtimes = curr_mtimes
