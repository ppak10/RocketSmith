"""GIF renderer: 360° rotating isometric animation."""

from __future__ import annotations

from pathlib import Path


def render_step_gif(
    step_path: Path,
    output_path: Path,
    frames: int = 36,
    width: int = 560,
    height: int = 420,
    fps: int = 12,
    tolerance: float = 0.5,
) -> Path:
    """Render a 360° rotating isometric GIF of a STEP file.

    Args:
        step_path:   Path to the STEP file.
        output_path: Where to save the GIF.
        frames:      Number of rotation frames (default 36 = 10° per frame).
        width:       Frame width in pixels.
        height:      Frame height in pixels.
        fps:         Playback speed in frames per second.
        tolerance:   Tessellation tolerance in mm.

    Returns:
        output_path on success.
    """
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap
    from PIL import Image

    from rocketsmith.cadsmith.assets.ascii import _load_centered_mesh
    from rocketsmith.cadsmith.assets.image import (
        _BG,
        _PART_COLORS,
        _iso_scale,
        render_isometric_frame,
    )

    verts, tris, normals = _load_centered_mesh(step_path, tolerance=tolerance)
    if len(verts) == 0:
        raise ValueError(f"No geometry found in STEP file: {step_path}")

    scale = _iso_scale(verts, width, height)
    part_cmap = LinearSegmentedColormap.from_list("rocket_part", _PART_COLORS)
    bg_rgb = tuple(int(c * 255) for c in _BG)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    images: list[Image.Image] = []
    step_deg = 360.0 / frames

    for i in range(frames):
        intensity = render_isometric_frame(
            verts, tris, normals, width, height, i * step_deg, scale
        )

        rgb = np.full((height, width, 3), bg_rgb, dtype=np.uint8)
        mask = intensity >= 0
        if mask.any():
            rgb[mask] = (part_cmap(intensity[mask])[:, :3] * 255).astype(np.uint8)

        images.append(Image.fromarray(rgb, mode="RGB"))

    if images:
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=1000 // fps,
            loop=0,
        )

    return output_path
