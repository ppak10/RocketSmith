from mcp.server.fastmcp import FastMCP


def register_cadsmith_script(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="cadsmith_script",
        title="Run build123d Script",
        description=(
            "Execute a build123d Python script in an isolated uv environment and "
            "return the paths of any STEP files written to the output directory. "
            "The script should write one or more .step files to out_dir."
        ),
        structured_output=True,
    )
    async def cadsmith_script(
        script_path: Path,
        out_dir: Path,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Run a build123d Python script and collect its STEP outputs.

        Args:
            script_path: Path to the build123d .py script to execute.
            out_dir: Directory where the script should write its .step output(s).
                     Must exist before calling this tool.

        # TODO: Add static import validation before execution using ast.walk to
        # check for disallowed imports (e.g. os, sys, subprocess, socket).
        # Only imports in an explicit allowlist (build123d, math, pathlib, typing)
        # should be permitted. Return a VALIDATION_ERROR with the violating module
        # names if any are found, before uv run is ever called.
        """
        import subprocess

        script_path = resolve_path(script_path)
        out_dir = resolve_path(out_dir)

        if not script_path.exists():
            return tool_error(
                f"Script not found: {script_path}",
                "FILE_NOT_FOUND",
                script_path=str(script_path),
            )

        if not out_dir.exists():
            return tool_error(
                f"Output directory not found: {out_dir}",
                "DIR_NOT_FOUND",
                out_dir=str(out_dir),
            )

        try:
            result = subprocess.run(
                ["uv", "run", "--isolated", "--with", "build123d", str(script_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError:
            return tool_error(
                "uv executable not found — ensure uv is installed and on PATH",
                "UV_NOT_FOUND",
            )
        except subprocess.TimeoutExpired:
            return tool_error(
                "Script execution timed out after 120 seconds",
                "TIMEOUT",
                script_path=str(script_path),
            )

        if result.returncode != 0:
            return tool_error(
                "Script execution failed",
                "SCRIPT_FAILED",
                script_path=str(script_path),
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )

        step_files = [str(p) for p in out_dir.glob("*.step")]

        return tool_success(
            {
                "step_files": step_files,
                "out_dir": str(out_dir),
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )

    return cadsmith_script
