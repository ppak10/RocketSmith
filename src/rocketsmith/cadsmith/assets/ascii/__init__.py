"""ASCII renderer for STEP files via isometric projection."""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_centered_mesh(step_path: Path, tolerance: float):
    """Load, tessellate, and center a STEP file mesh.

    Returns (verts, tris, normals) — vertices are centered at the origin.
    """
    import numpy as np
    from .mesh import load_step_mesh

    verts, tris, normals = load_step_mesh(step_path, tolerance=tolerance)
    if len(verts) == 0:
        return verts, tris, normals

    center = (verts.min(axis=0) + verts.max(axis=0)) / 2
    return verts - center, tris, normals


def _render_mesh_frame(
    verts,
    tris,
    normals,
    scale: float,
    angle_deg: float,
    width: int,
    height: int,
    wireframe: bool,
) -> list[str]:
    """Rotate, project, and rasterize a pre-loaded mesh to a list of row strings."""
    from .project import rotate_y, project
    from .rasterize import rasterize, rasterize_wireframe, _compute_shade_indices
    from .core import LIGHT_DIR

    rotated_verts = rotate_y(verts, angle_deg)
    rotated_normals = rotate_y(normals, angle_deg)
    screen_xy, depth = project(rotated_verts, scale, width, height)

    if wireframe:
        return rasterize_wireframe(
            screen_xy, depth, tris, rotated_normals, width, height
        )
    shade_idx = _compute_shade_indices(rotated_normals, LIGHT_DIR)
    return rasterize(screen_xy, depth, tris, shade_idx, width, height)


# ── Public API ────────────────────────────────────────────────────────────────


def render_step_ascii(
    step_path: Path,
    angle_deg: float = 0.0,
    width: int | None = None,
    height: int | None = None,
    wireframe: bool = False,
    tolerance: float = 1.0,
) -> str:
    """Render a STEP file as an isometric ASCII projection.

    Args:
        step_path: Path to the STEP file.
        angle_deg: Y-axis rotation angle in degrees (0 = default isometric view).
        width: Canvas width in characters. Defaults to terminal width.
        height: Canvas height in characters. Defaults to terminal height - 4.
        wireframe: Render edges only if True; shaded faces by default.
        tolerance: Mesh tessellation tolerance in mm (smaller = finer detail, slower).

    Returns:
        Multi-line ASCII string.
    """
    from .project import compute_scale

    if width is None or height is None:
        term = shutil.get_terminal_size(fallback=(80, 24))
        if width is None:
            width = term.columns
        if height is None:
            height = max(10, term.lines - 4)

    verts, tris, normals = _load_centered_mesh(step_path, tolerance)
    if len(verts) == 0:
        return "(empty mesh — no geometry found in STEP file)"

    scale = compute_scale(verts, width, height)
    rows = _render_mesh_frame(
        verts, tris, normals, scale, angle_deg, width, height, wireframe
    )
    return "\n".join(rows)


def animate_step_ascii(
    step_path: Path,
    width: int | None = None,
    height: int | None = None,
    wireframe: bool = False,
    tolerance: float = 1.0,
    fps: float = 12.0,
    degrees_per_second: float = 36.0,
) -> None:
    """Animate a STEP file rotating around the Y axis in the terminal.

    Tessellates once, then rotates and re-renders each frame. Runs until
    interrupted with Ctrl+C.

    Args:
        step_path: Path to the STEP file.
        width: Canvas width. Defaults to terminal width.
        height: Canvas height. Defaults to terminal height - 4.
        wireframe: Render edges only if True; shaded faces by default.
        tolerance: Mesh tessellation tolerance in mm.
        fps: Target frames per second.
        degrees_per_second: Y-axis rotation speed in degrees per second.
    """
    from .project import compute_scale

    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"
    HOME = "\033[H"
    CLEAR_SCREEN = "\033[2J"

    if width is None or height is None:
        term = shutil.get_terminal_size(fallback=(80, 24))
        if width is None:
            width = term.columns
        if height is None:
            height = max(10, term.lines - 4)

    verts, tris, normals = _load_centered_mesh(step_path, tolerance)
    if len(verts) == 0:
        print("(empty mesh — no geometry found in STEP file)")
        return

    scale = compute_scale(verts, width, height)

    frame_time = 1.0 / fps
    deg_per_frame = degrees_per_second / fps
    mode_label = "wireframe" if wireframe else "shaded"
    step_name = step_path.name

    sys.stdout.write(CLEAR_SCREEN + HOME + HIDE_CURSOR)
    sys.stdout.flush()

    try:
        angle = 0.0
        while True:
            t_start = time.monotonic()

            rows = _render_mesh_frame(
                verts, tris, normals, scale, angle, width, height, wireframe
            )
            frame = "\n".join(rows)
            status = (
                f"  {step_name}  |  {mode_label}  |  {angle:5.1f}°  |  Ctrl+C to stop"
            )

            sys.stdout.write(HOME + frame + "\n" + status)
            sys.stdout.flush()

            elapsed = time.monotonic() - t_start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            angle = (angle + deg_per_frame) % 360.0

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\n" + SHOW_CURSOR)
        sys.stdout.flush()


def render_ascii_animation(
    step_path: Path,
    output_path: Path,
    frames: int = 360,
    width: int = 80,
    height: int = 40,
    wireframe: bool = False,
    tolerance: float = 1.0,
) -> Path:
    """Render a rotating ASCII animation to a text file.

    Each frame is separated by a form-feed character (``\\f``) so the
    GUI can cycle through them as an animation.

    Args:
        step_path:   Path to the STEP file.
        output_path: Where to save the .txt file.
        frames:      Number of rotation frames (default 360 = 1° per frame).
        width:       Canvas width in characters.
        height:      Canvas height in rows.
        wireframe:   Render edges only if True; shaded faces by default.
        tolerance:   Tessellation tolerance in mm.

    Returns:
        output_path on success.
    """
    from .project import compute_scale

    verts, tris, normals = _load_centered_mesh(step_path, tolerance)
    if len(verts) == 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("(empty mesh — no geometry found)\n", encoding="utf-8")
        return output_path

    scale = compute_scale(verts, width, height)
    deg_per_frame = 360.0 / frames

    frame_strings: list[str] = []
    for i in range(frames):
        angle = i * deg_per_frame
        rows = _render_mesh_frame(
            verts, tris, normals, scale, angle, width, height, wireframe
        )
        frame_strings.append("\n".join(rows))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\f".join(frame_strings), encoding="utf-8")

    return output_path
