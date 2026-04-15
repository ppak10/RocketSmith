"""Lightweight filesystem watcher that polls for mtime changes."""

import asyncio
import os
from pathlib import Path
from typing import Callable, Awaitable, Optional

from rocketsmith.gui.layout import (
    OPENROCKET_DIR,
    FLIGHTS_DIR,
    CADSMITH_DIR,
    CADSMITH_SOURCE_DIR,
    STEP_DIR,
    STL_DIR,
    GCODE_DIR,
    PARTS_DIR,
    PNG_DIR,
    GIF_DIR,
    TXT_DIR,
    PROGRESS_DIR,
    LOGS_DIR,
    TREE_FILE,
    ASSEMBLY_FILE,
    PRUSASLICER_DIR,
)

# Map layout directory prefixes to event types.
# Order matters — more specific prefixes must come first.
_PREFIX_MAP: list[tuple[str, str]] = [
    (CADSMITH_SOURCE_DIR, "cadsmith"),
    (STEP_DIR, "step"),
    (STL_DIR, "stl"),
    (GCODE_DIR, "gcode"),
    (PARTS_DIR, "parts"),
    (PNG_DIR, "preview"),
    (GIF_DIR, "preview"),
    (TXT_DIR, "preview"),
    (PROGRESS_DIR, "preview"),
    (LOGS_DIR, "log"),
    (FLIGHTS_DIR, "flight"),
    (OPENROCKET_DIR, "openrocket"),
    (CADSMITH_DIR, "cadsmith"),
    (PRUSASLICER_DIR, "prusaslicer"),
]

# Fallback: classify by extension when the file is not in a known directory.
_EXT_MAP: dict[str, str] = {
    ".step": "step",
    ".stp": "step",
    ".ork": "openrocket",
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
    ".gui-dev.pid",
    "settings.local.json",
    "data.js",
    "files-tree.json",
    "index.html",
    "main.js",
    # session.jsonl is intentionally NOT ignored — the watcher broadcasts it so
    # the frontend can refresh the session log in real time.  Loop prevention is
    # handled in server.py: on_change skips auto-logging for gui/logs/ files.
}


def _classify(path: Path, root: Path) -> str:
    """Return the event type for a file based on its location or extension."""
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        return _EXT_MAP.get(path.suffix.lower(), "unknown")

    if rel == TREE_FILE:
        return "manifest"
    if rel == ASSEMBLY_FILE:
        return "assembly"

    for prefix, event_type in _PREFIX_MAP:
        if rel.startswith(prefix + "/") or rel == prefix:
            return event_type

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


_BINARY_EXTENSIONS: set[str] = {".stl"}
_MAX_BINARY_SIZE = 100_000_000


def build_snapshot_events(root: Path) -> list[dict]:
    """Build synthetic WatchEvents for all existing files in *root*.

    Used to replay the current project state to newly connected WebSocket
    clients so they don't start with an empty feed. Text files include
    their content; binary files (STL) include a ``__b64__`` wrapper so
    the frontend can create blob URLs.
    """
    import base64
    from datetime import datetime, timezone

    events: list[dict] = []
    for path, mtime in _scan(root).items():
        if path.name in IGNORED_FILES:
            continue
        event_type = _classify(path, root)
        if event_type == "unknown":
            continue
        ts = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            continue

        content: Optional[str] = None
        if _is_text_file(path):
            content = _read_text_safe(path)
        elif path.suffix.lower() in _BINARY_EXTENSIONS:
            try:
                if path.stat().st_size <= _MAX_BINARY_SIZE:
                    raw = path.read_bytes()
                    content = (
                        '{"__b64__":"' + base64.b64encode(raw).decode("ascii") + '"}'
                    )
            except OSError:
                pass

        events.append(
            {
                "type": event_type,
                "path": str(path),
                "relative_path": rel,
                "timestamp": ts,
                "content": content,
                "previous_content": None,
            }
        )

    # Sort by mtime so cards appear in chronological order.
    events.sort(key=lambda e: e["timestamp"])
    return events


def _scan(root: Path) -> dict[Path, float]:
    """Walk *root* and return {path: mtime} for every file."""
    snapshot: dict[Path, float] = {}
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden directories (e.g. .git) to avoid spurious events.
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
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
                elif path.suffix.lower() in _BINARY_EXTENSIONS:
                    import base64

                    try:
                        if path.stat().st_size <= _MAX_BINARY_SIZE:
                            raw = path.read_bytes()
                            content = (
                                '{"__b64__":"'
                                + base64.b64encode(raw).decode("ascii")
                                + '"}'
                            )
                    except OSError:
                        pass

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
