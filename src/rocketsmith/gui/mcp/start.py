from mcp.server.fastmcp import FastMCP


def register_gui_start(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="gui_start",
        title="Launch STEP Viewer",
        description=(
            "Launch an interactive 3D viewer window for a STEP file. "
            "The viewer hot-reloads whenever the file is updated on disk, "
            "so the user can watch CAD generation in real time. "
            "The viewer runs in a separate process and does not block the agent. "
            "Returns immediately with the viewer process PID."
        ),
        structured_output=True,
    )
    async def gui_start(
        step_file_path: Path,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Launch a detached 3D viewer window that monitors a STEP file for changes.

        The viewer opens a native Qt window with orbit/pan/zoom controls and
        automatically reloads the geometry whenever the STEP file is written.
        It runs in a completely separate process and does not interfere with
        ongoing CAD generation.

        Args:
            step_file_path: Path to the STEP file to view. The file does not
                need to exist yet — the viewer will wait and load it once it
                appears.
        """
        import subprocess
        import sys

        step_file_path = resolve_path(step_file_path)

        # Ensure parent directory exists (the file itself may not exist yet)
        if not step_file_path.parent.exists():
            return tool_error(
                f"Parent directory does not exist: {step_file_path.parent}",
                "DIR_NOT_FOUND",
                step_file_path=str(step_file_path),
            )

        # Locate the viewer module
        viewer_module = (
            Path(__file__).resolve().parent.parent.parent
            / "cadsmith"
            / "viewer"
            / "viewer.py"
        )
        if not viewer_module.exists():
            return tool_error(
                "Viewer module not found in package",
                "VIEWER_NOT_FOUND",
                expected_path=str(viewer_module),
            )

        cmd = [sys.executable, str(viewer_module), str(step_file_path)]

        try:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return tool_error(
                f"Failed to launch viewer: {e}",
                "VIEWER_LAUNCH_FAILED",
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

        return tool_success(
            {
                "pid": proc.pid,
                "step_file_path": str(step_file_path),
                "message": (
                    "Viewer launched. The user can orbit/pan/zoom the 3D view. "
                    "The viewer will automatically reload when the STEP file is updated."
                ),
            }
        )

    return gui_start
