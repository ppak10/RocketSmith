from mcp.server.fastmcp import FastMCP


def register_cadsmith_run_script(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="cadsmith_run_script",
        title="Run build123d Script",
        description=(
            "Execute a build123d Python script in an isolated uv environment. "
            "Before execution, validates that the script calls export_step "
            "and only imports from the allowed set "
            "(build123d, pathlib, math, typing). "
            "After execution, verifies that non-empty .step files "
            "were written to the output directory. "
            "STL files are generated separately by cadsmith_generate_preview."
        ),
        structured_output=True,
    )
    async def cadsmith_run_script(
        script_path: Path,
        out_dir: Path,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Run a build123d Python script and collect its outputs.

        Args:
            script_path: Path to the build123d .py script to execute.
            out_dir: Directory where the script should write its .step and
                     .stl output(s). Must exist before calling this tool.
        """
        import subprocess

        from rocketsmith.cadsmith.validate_script import validate_script

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

        # ── Pre-run validation ─────────────────────────────────────────
        errors = validate_script(script_path)
        if errors:
            return tool_error(
                "Script failed pre-execution validation",
                "VALIDATION_ERROR",
                script_path=str(script_path),
                validation_errors=errors,
            )

        # ── Execute ────────────────────────────────────────────────────
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

        # ── Post-run validation ────────────────────────────────────────
        step_files = [str(p) for p in out_dir.glob("*.step") if p.stat().st_size > 0]

        if not step_files:
            return tool_error(
                "Script ran but did not produce expected output files",
                "OUTPUT_MISSING",
                script_path=str(script_path),
                out_dir=str(out_dir),
                output_errors=[
                    "No non-empty .step files found in output directory after execution."
                ],
                stdout=result.stdout,
                stderr=result.stderr,
            )

        return tool_success(
            {
                "step_files": step_files,
                "out_dir": str(out_dir),
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )

    return cadsmith_run_script
