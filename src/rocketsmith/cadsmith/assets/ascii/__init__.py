"""ASCII renderer for STEP files via isometric projection."""

from __future__ import annotations

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
