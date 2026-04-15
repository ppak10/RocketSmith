from mcp.server.fastmcp import FastMCP


def register_cadsmith_generate_preview(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        name="cadsmith_generate_preview",
        title="Generate Part Preview",
        description=(
            "Generate preview assets for a STEP file: STL mesh (for the 3D "
            "viewer), PNG thumbnail, rotating GIF, and/or ASCII animation. "
            "The STL is always generated to gui/assets/stl/. Other outputs "
            "are written to gui/assets/<format>/. "
            "Progress is tracked in gui/progress/<part_name>.json "
            "so the GUI can display a live progress bar."
        ),
        structured_output=True,
    )
    async def cadsmith_generate_preview(
        step_file_path: Path,
        outputs: list[str] | None = None,
        out_dir: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Generate preview assets for a STEP file.

        The STL mesh is always generated (required by the 3D viewer).
        Additional outputs are optional.

        Args:
            step_file_path: Path to the STEP file to preview.
            outputs: List of additional preview types to generate. Options:
                "thumbnail" (PNG), "gif", "ascii". Defaults to all three.
            out_dir: Optional project root for writing preview assets.
                Defaults to the current project directory.
        """
        import asyncio
        import subprocess
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from rocketsmith.cadsmith.preview.progress import PreviewProgress
        from rocketsmith.mcp.utils import get_project_dir

        step_file_path = resolve_path(step_file_path)
        project_dir = (
            resolve_path(out_dir) if out_dir is not None else get_project_dir()
        )

        if not step_file_path.exists():
            return tool_error(
                f"STEP file not found: {step_file_path}",
                "FILE_NOT_FOUND",
                step_file_path=str(step_file_path),
            )

        valid_outputs = {"thumbnail", "gif", "ascii"}
        requested = set(outputs) if outputs else valid_outputs
        unknown = requested - valid_outputs
        if unknown:
            return tool_error(
                f"Unknown output types: {', '.join(sorted(unknown))}. "
                f"Valid options: {', '.join(sorted(valid_outputs))}",
                "INVALID_OUTPUTS",
            )

        part_name = step_file_path.stem

        from rocketsmith.gui.layout import STL_DIR, PNG_DIR, GIF_DIR, TXT_DIR

        stl_path = project_dir / STL_DIR / f"{part_name}.stl"
        png_path = project_dir / PNG_DIR / f"{part_name}.png"
        gif_path = project_dir / GIF_DIR / f"{part_name}.gif"
        txt_path = project_dir / TXT_DIR / f"{part_name}.txt"

        # Always include STL in the progress tracking.
        all_outputs = sorted({"stl"} | requested)
        progress = PreviewProgress(project_dir, part_name, all_outputs)

        def _run_stl() -> tuple[str, Path]:
            """Convert STEP → STL via build123d in an isolated uv env."""
            import sys

            progress.update("stl", "in_progress")
            stl_path.parent.mkdir(parents=True, exist_ok=True)

            script = (
                "from build123d import import_step, export_stl\n"
                "from pathlib import Path\n"
                f"parts = import_step(Path({str(step_file_path)!r}))\n"
                f"export_stl(parts, Path({str(stl_path)!r}))\n"
            )

            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0 or not stl_path.exists():
                raise RuntimeError(
                    f"STEP→STL conversion failed: {result.stderr or result.stdout}"
                )

            progress.update("stl", "done", path=str(stl_path.relative_to(project_dir)))
            return "stl", stl_path

        def _run_thumbnail() -> tuple[str, Path]:
            from rocketsmith.cadsmith.preview.image import render_step_png

            progress.update("thumbnail", "in_progress")
            result = render_step_png(step_file_path, png_path)
            progress.update(
                "thumbnail", "done", path=str(png_path.relative_to(project_dir))
            )
            return "thumbnail", result

        def _run_gif() -> tuple[str, Path]:
            from rocketsmith.cadsmith.preview.gif import render_step_gif

            progress.update("gif", "in_progress")
            result = render_step_gif(step_file_path, gif_path)
            progress.update("gif", "done", path=str(gif_path.relative_to(project_dir)))
            return "gif", result

        def _run_ascii() -> tuple[str, Path]:
            from rocketsmith.cadsmith.preview.ascii import render_ascii_animation

            progress.update("ascii", "in_progress")
            result = render_ascii_animation(step_file_path, txt_path)
            progress.update(
                "ascii", "done", path=str(txt_path.relative_to(project_dir))
            )
            return "ascii", result

        runners: dict[str, object] = {
            "stl": _run_stl,  # Always run.
            "thumbnail": _run_thumbnail,
            "gif": _run_gif,
            "ascii": _run_ascii,
        }

        to_run = {"stl"} | requested

        results: dict[str, str | None] = {}
        warnings: list[str] = []

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(runners[name]): name for name in to_run}
            done_futures = await loop.run_in_executor(
                None,
                lambda: {f: f.result() for f in as_completed(futures)},
            )

        for future, (name, path) in done_futures.items():
            try:
                results[name] = str(path)
            except Exception as e:
                results[name] = None
                warnings.append(f"{name} failed: {e}")
                progress.update(futures[future], "failed")

        output = {
            "results": results,
            "project_dir": str(project_dir),
            "step_file_path": str(step_file_path),
        }
        if warnings:
            output["warnings"] = warnings

        return tool_success(output)

    return cadsmith_generate_preview
