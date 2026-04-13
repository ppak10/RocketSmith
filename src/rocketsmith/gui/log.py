"""File-based logging for the GUI session log.

Appends JSONL entries to ``gui/logs/session.jsonl`` inside the project
directory.  The GUI watcher picks up changes and the frontend reads
the file to display the log history.

Usage::

    from rocketsmith.gui.log import gui_log

    gui_log(project_dir, "openrocket", "Created flight simulation", detail="h100w config")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from rocketsmith.gui.layout import LOGS_DIR

Level = Literal["info", "warn", "error", "success"]


def gui_log(
    project_dir: Path,
    source: str,
    message: str,
    *,
    level: Level = "info",
    detail: str | None = None,
) -> None:
    """Append a log entry to the session log file."""
    log_dir = project_dir / LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "session.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "source": source,
        "message": message,
    }
    if detail is not None:
        entry["detail"] = detail

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
