"""Post-processing: generate STL, PNG thumbnail, and GIF from a STEP file.

All three conversions run in parallel via concurrent.futures.
"""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional


def step_to_stl(step_path: Path, stl_path: Path, tolerance: float = 0.5) -> Path:
    """Convert a STEP file to an STL mesh."""
    from build123d import import_step, export_stl

    part = import_step(str(step_path))
    export_stl(part, str(stl_path), tolerance=tolerance)
    return stl_path


def step_to_thumbnail(step_path: Path, png_path: Path, tolerance: float = 0.5) -> Path:
    """Render a 3-panel PNG thumbnail of a STEP file."""
    from rocketsmith.cadsmith.render.image import render_step_png

    png_path.parent.mkdir(parents=True, exist_ok=True)
    render_step_png(step_path, png_path, tolerance=tolerance)
    return png_path


def step_to_gif(
    step_path: Path,
    gif_path: Path,
    frames: int = 36,
    width: int = 120,
    height: int = 80,
    fps: int = 12,
    tolerance: float = 0.5,
) -> Path:
    """Render a rotating ASCII-art GIF of a STEP file."""
    from rocketsmith.cadsmith.render.ascii import render_step_ascii
    from PIL import Image, ImageDraw, ImageFont

    gif_path.parent.mkdir(parents=True, exist_ok=True)

    images: list[Image.Image] = []
    step = 360 // frames

    for deg in range(0, 360, step):
        ascii_art = render_step_ascii(
            step_path,
            angle_deg=deg,
            width=width,
            height=height,
            wireframe=False,
            tolerance=tolerance,
        )
        # Render ASCII to an image.
        lines = ascii_art.split("\n")
        char_w, char_h = 6, 10
        img_w = max(len(line) for line in lines) * char_w
        img_h = len(lines) * char_h
        img = Image.new("RGB", (img_w, img_h), (250, 250, 250))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        for i, line in enumerate(lines):
            draw.text((0, i * char_h), line, fill=(0, 0, 0), font=font)
        images.append(img)

    if images:
        duration = 1000 // fps
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
            optimize=True,
        )

    return gif_path


def postprocess_step(
    step_path: Path,
    parts_dir: Path,
    tolerance: float = 0.5,
) -> dict[str, Optional[Path]]:
    """Generate STL, PNG, and GIF from a STEP file in parallel.

    Args:
        step_path: Path to the source STEP file.
        parts_dir: The ``parts/`` directory (parent of ``step/``, ``stl/``, etc.).
        tolerance: Tessellation tolerance in mm.

    Returns:
        Dict with keys ``stl``, ``png``, ``gif`` mapping to output paths
        (or None if that conversion failed).
    """
    stem = step_path.stem

    stl_path = parts_dir / "stl" / f"{stem}.stl"
    png_path = parts_dir / "png" / f"{stem}.png"
    gif_path = parts_dir / "gif" / f"{stem}.gif"

    # Ensure output directories exist.
    for p in [stl_path, png_path, gif_path]:
        p.parent.mkdir(parents=True, exist_ok=True)

    results: dict[str, Optional[Path]] = {"stl": None, "png": None, "gif": None}

    def _run_stl() -> tuple[str, Path]:
        return "stl", step_to_stl(step_path, stl_path, tolerance)

    def _run_png() -> tuple[str, Path]:
        return "png", step_to_thumbnail(step_path, png_path, tolerance)

    def _run_gif() -> tuple[str, Path]:
        return "gif", step_to_gif(step_path, gif_path, tolerance=tolerance)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(_run_stl),
            executor.submit(_run_png),
            executor.submit(_run_gif),
        ]
        for future in as_completed(futures):
            try:
                key, path = future.result()
                results[key] = path
            except Exception as e:
                # Log but don't fail — partial results are fine.
                import logging

                logging.getLogger(__name__).warning("Post-processing failed: %s", e)

    return results
