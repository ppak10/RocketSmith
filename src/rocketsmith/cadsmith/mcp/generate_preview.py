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
            "Generate preview assets for a STEP file: PNG thumbnail, "
            "rotating GIF, and/or ASCII animation. Outputs are written to "
            "<project_dir>/previews/<format>/<part_name>.<ext>. "
            "Progress is tracked in previews/preview_progress.json "
            "so the GUI can display a live progress bar."
        ),
        structured_output=True,
    )
    async def cadsmith_generate_preview(
        step_file_path: Path,
        project_dir: Path,
        outputs: list[str] | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Generate preview assets for a STEP file.

        Args:
            step_file_path: Path to the STEP file to preview.
            project_dir: Absolute path to the project root directory.
            outputs: List of preview types to generate. Options:
                "thumbnail" (PNG), "gif", "ascii". Defaults to all three.
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from rocketsmith.cadsmith.preview.progress import PreviewProgress

        step_file_path = resolve_path(step_file_path)
        project_dir = resolve_path(project_dir)

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
        previews_dir = project_dir / "previews"

        png_path = previews_dir / "png" / f"{part_name}.png"
        gif_path = previews_dir / "gif" / f"{part_name}.gif"
        txt_path = previews_dir / "txt" / f"{part_name}.txt"

        progress = PreviewProgress(previews_dir, part_name, sorted(requested))

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

        runners = {
            "thumbnail": _run_thumbnail,
            "gif": _run_gif,
            "ascii": _run_ascii,
        }

        results: dict[str, str | None] = {}
        warnings: list[str] = []

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(runners[name]): name for name in requested}
            # Wait without blocking the event loop.
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
            "previews_dir": str(previews_dir),
            "step_file_path": str(step_file_path),
        }
        if warnings:
            output["warnings"] = warnings

        return tool_success(output)

    return cadsmith_generate_preview
