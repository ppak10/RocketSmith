from mcp.server.fastmcp import FastMCP


def register_cadsmith_postprocess(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="cadsmith_postprocess",
        title="Post-process STEP File",
        description=(
            "Generate STL, PNG thumbnail, and rotating GIF from a STEP file. "
            "All three conversions run in parallel. The outputs are placed in "
            "sibling directories under parts/ (parts/stl/, parts/png/, parts/gif/). "
            "Call this after generating each STEP file."
        ),
        structured_output=True,
    )
    async def cadsmith_postprocess(
        step_file_path: Path,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Post-process a STEP file to generate STL, PNG, and GIF.

        Expects the STEP file to live at ``parts/step/<name>.step``.
        Outputs are written to ``parts/stl/<name>.stl``,
        ``parts/png/<name>.png``, and ``parts/gif/<name>.gif``.

        Args:
            step_file_path: Path to the STEP file to post-process.
        """
        import asyncio

        step_file_path = resolve_path(step_file_path)

        if not step_file_path.exists():
            return tool_error(
                f"STEP file not found: {step_file_path}",
                "FILE_NOT_FOUND",
                step_file_path=str(step_file_path),
            )

        # Determine the parts/ directory.
        # Expected layout: parts/step/<name>.step
        if (
            step_file_path.parent.name == "step"
            and step_file_path.parent.parent.name == "parts"
        ):
            parts_dir = step_file_path.parent.parent
        else:
            # Fallback: create parts/ structure next to the STEP file.
            parts_dir = step_file_path.parent.parent
            if parts_dir.name != "parts":
                parts_dir = step_file_path.parent / "parts"

        try:
            from rocketsmith.cadsmith.postprocess import postprocess_step

            results = await asyncio.get_event_loop().run_in_executor(
                None,
                postprocess_step,
                step_file_path,
                parts_dir,
            )

            output = {}
            for fmt, path in results.items():
                output[fmt] = str(path) if path else None

            failed = [k for k, v in output.items() if v is None]
            if failed:
                output["warnings"] = f"Failed to generate: {', '.join(failed)}"

            output["step_file_path"] = str(step_file_path)
            output["message"] = "Post-processing complete."

            return tool_success(output)

        except Exception as e:
            return tool_error(
                f"Post-processing failed: {e}",
                "POSTPROCESS_FAILED",
                step_file_path=str(step_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    return cadsmith_postprocess
