"""File-based progress tracking for preview generation.

Each part gets its own progress file at
``progress/<part_name>.json`` so multiple parts can generate
previews concurrently without conflicts. The GUI watcher polls the
``progress/`` directory to display live progress.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

Status = Literal["pending", "in_progress", "done", "failed"]

PROGRESS_DIR = "progress"


class PreviewProgress:
    """Manages a per-part progress file in progress/."""

    def __init__(self, project_dir: Path, part_name: str, outputs: list[str]) -> None:
        self._path = project_dir / PROGRESS_DIR / f"{part_name}.json"
        self._part_name = part_name
        self._state: dict[str, dict[str, str | None]] = {
            name: {"status": "pending", "path": None} for name in outputs
        }
        self._write()

    def update(
        self,
        output_name: str,
        status: Status,
        path: str | None = None,
    ) -> None:
        """Update the status of one output and flush to disk."""
        self._state[output_name]["status"] = status
        if path is not None:
            self._state[output_name]["path"] = path
        self._write()

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {"part_name": self._part_name, "outputs": self._state},
                indent=2,
            ),
            encoding="utf-8",
        )
