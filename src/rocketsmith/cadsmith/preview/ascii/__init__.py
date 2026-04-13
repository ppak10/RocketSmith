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


def render_storyboard(
    step_path: Path,
    angles: list[float] | None = None,
    total_width: int | None = None,
    total_height: int | None = None,
    columns: int = 2,
    wireframe: bool = False,
    tolerance: float = 1.0,
) -> str:
    """Render a STEP file as a multi-angle storyboard.

    Tessellates the mesh once and renders it at several Y-axis rotation angles,
    arranged in a grid. Suitable for returning from an MCP tool where live
    animation is not possible.

    The frame height is derived automatically from the width-constrained scale
    and the projected Y span, so the mesh fills the available horizontal space.
    Pass ``total_height`` to cap the per-row height (useful to limit total output
    length when the shape is very tall relative to its width).

    Args:
        step_path: Path to the STEP file.
        angles: List of Y-axis rotation angles in degrees.
                Defaults to [0, 90, 180, 270].
        total_width: Total output width in characters. Defaults to terminal width.
        total_height: Optional height budget for the whole storyboard in rows.
                      When given, each grid row is capped so the grid fits within
                      this budget.
        columns: Number of frames per row (1–4). Defaults to 2.
        wireframe: Render edges only if True; shaded faces by default.
        tolerance: Mesh tessellation tolerance in mm.

    Returns:
        Multi-line ASCII string with all frames arranged in a grid.
    """
    from .project import compute_projected_spans, compute_scale

    if angles is None:
        angles = [0.0, 90.0, 180.0, 270.0]

    columns = max(1, min(columns, len(angles)))

    if total_width is None:
        total_width = shutil.get_terminal_size(fallback=(80, 24)).columns

    # Each frame gets an equal share of the total width minus 1-char gaps
    frame_width = (total_width - (columns - 1)) // columns

    verts, tris, normals = _load_centered_mesh(step_path, tolerance)
    if len(verts) == 0:
        return "(empty mesh — no geometry found in STEP file)"

    # Compute the width-constrained scale, then derive frame_height from the
    # actual projected Y span so the mesh fills the frame rather than leaving
    # blank rows (especially important for wide/flat shapes like airframe tubes).
    margin = 2
    max_sx_span, max_sy_span = compute_projected_spans(verts)
    if max_sx_span < 1e-10:
        scale = 1.0
    else:
        scale = (frame_width - 2 * margin) / max_sx_span

    # Natural frame height: how tall the mesh actually renders at this scale
    natural_frame_height = max(10, int(max_sy_span * scale) + 2 * margin)

    # If caller provided a total height budget, cap each row accordingly
    if total_height is not None:
        grid_rows = max(1, (len(angles) + columns - 1) // columns)
        # Account for header (2 lines) + label row per grid row (1 line) + blank (1 line)
        overhead = 2 + grid_rows * 2
        budget_per_row = max(10, (total_height - overhead) // grid_rows)
        frame_height = min(natural_frame_height, budget_per_row)
    else:
        frame_height = natural_frame_height

    # Re-compute scale constrained by both width and the (possibly capped) frame_height
    scale = compute_scale(verts, frame_width, frame_height)

    # Render every frame and trim blank rows so the grid stays compact
    frames: list[list[str]] = []
    for angle in angles:
        rows = _render_mesh_frame(
            verts, tris, normals, scale, angle, frame_width, frame_height, wireframe
        )
        # Strip leading and trailing all-whitespace rows
        while rows and not rows[0].strip():
            rows.pop(0)
        while rows and not rows[-1].strip():
            rows.pop()
        frames.append(rows)

    # Assemble into a grid: label row + frame rows, repeated for each row of columns
    col_sep = " "
    output_lines: list[str] = []
    step_name = step_path.name

    # Header
    output_lines.append(f"  {step_name}  ({'wireframe' if wireframe else 'shaded'})")
    output_lines.append("")

    for row_start in range(0, len(frames), columns):
        row_frames = frames[row_start : row_start + columns]
        row_angles = angles[row_start : row_start + columns]

        # Angle label row
        label_parts = []
        for angle in row_angles:
            label = f" {angle:.0f}°"
            label_parts.append(label.ljust(frame_width))
        output_lines.append(col_sep.join(label_parts).rstrip())

        # Frame rows — pad shorter frames to the same height with blank lines
        max_rows = max(len(f) for f in row_frames)
        for i in range(max_rows):
            parts = []
            for frame in row_frames:
                line = frame[i] if i < len(frame) else " " * frame_width
                parts.append(line)
            output_lines.append(col_sep.join(parts).rstrip())

        output_lines.append("")

    return "\n".join(output_lines).rstrip()


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
    frames: int = 36,
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
        frames:      Number of rotation frames (default 36 = 10° per frame).
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
