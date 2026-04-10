"""PNG renderer for STEP files.

Reuses the existing mesh tessellation and z-buffer rasterization pipeline
from the ASCII renderer, but outputs float intensity arrays → matplotlib PNG.

Three views are rendered per part. Labels describe the *part-local* frame,
not the rocket-logical frame — individual parts live in their own local
coordinates (e.g. nose cones are built shoulder-at-Z=0 for printing, which
is the opposite of the rocket's fore-to-aft direction). Rocket-frame
orientation is only meaningful in assembly renders where every part has
been transformed into the assembly coordinate system.

  - Side (eye at −X, looking +X) : horizontal = Z (low Z on the left), vertical = Y
  - End  (eye at +Z, looking −Z) : horizontal = X, vertical = Y; the +Z face
                                   of the part's bounding box is what the
                                   camera sees first
  - Isometric 45°                : 3D sanity check with Y-rotation applied
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np


# ── Light ─────────────────────────────────────────────────────────────────────

_LIGHT = np.array([1.0, 2.0, 1.5])
_LIGHT_DIR: np.ndarray = _LIGHT / np.linalg.norm(_LIGHT)


# ── Projection helpers ────────────────────────────────────────────────────────


def _project_side(
    vertices: np.ndarray, scale: float, width: int, height: int
) -> tuple[np.ndarray, np.ndarray]:
    """Orthographic side view: eye at −X looking +X, Z horizontal (low Z on the left, +Y up)."""
    z, y = vertices[:, 2], vertices[:, 1]
    sx = z * scale + width / 2.0
    sy = -y * scale + height / 2.0
    depth = -vertices[:, 0]  # eye at −X → smaller X is closer → depth = −X
    return np.stack([sx, sy], axis=1), depth


def _project_end(
    vertices: np.ndarray, scale: float, width: int, height: int
) -> tuple[np.ndarray, np.ndarray]:
    """Orthographic end view: eye at +Z looking −Z, high-Z face of the part is nearest camera."""
    x, y = vertices[:, 0], vertices[:, 1]
    sx = x * scale + width / 2.0
    sy = -y * scale + height / 2.0
    depth = vertices[:, 2]  # eye at +Z → larger Z is closer → depth = +Z
    return np.stack([sx, sy], axis=1), depth


def _project_iso(
    vertices: np.ndarray,
    normals: np.ndarray,
    scale: float,
    width: int,
    height: int,
    angle_deg: float = 45.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Isometric projection with Y-axis rotation. Returns (screen_xy, depth, rotated_normals)."""
    from rocketsmith.build123d.ascii.project import rotate_y

    rv = rotate_y(vertices, angle_deg)
    rn = rotate_y(normals, angle_deg)

    cos30 = math.cos(math.radians(30))
    sin30 = math.sin(math.radians(30))

    # Square-pixel isometric (char_aspect = 1.0)
    x, y, z = rv[:, 0], rv[:, 1], rv[:, 2]
    sx = (x - z) * cos30 * scale + width / 2.0
    sy = (-y + (x + z) * sin30) * scale + height / 2.0
    depth = x + y + z

    return np.stack([sx, sy], axis=1), depth, rn


# ── Scale helpers ─────────────────────────────────────────────────────────────


def _ortho_scale(
    vertices: np.ndarray,
    horiz_axis: int,
    vert_axis: int,
    width: int,
    height: int,
    margin: int = 30,
) -> float:
    h_span = float(vertices[:, horiz_axis].max() - vertices[:, horiz_axis].min())
    v_span = float(vertices[:, vert_axis].max() - vertices[:, vert_axis].min())
    if h_span < 1e-6 or v_span < 1e-6:
        return 1.0
    return min((width - 2 * margin) / h_span, (height - 2 * margin) / v_span)


def _iso_scale(
    vertices: np.ndarray, width: int, height: int, margin: int = 30
) -> float:
    from rocketsmith.build123d.ascii.project import rotate_y

    cos30 = math.cos(math.radians(30))
    sin30 = math.sin(math.radians(30))
    max_sx, max_sy = 0.0, 0.0

    for i in range(8):
        rv = rotate_y(vertices, 360.0 * i / 8)
        x, y, z = rv[:, 0], rv[:, 1], rv[:, 2]
        sx = (x - z) * cos30
        sy = -y + (x + z) * sin30
        max_sx = max(max_sx, float(sx.max() - sx.min()))
        max_sy = max(max_sy, float(sy.max() - sy.min()))

    if max_sx < 1e-10 or max_sy < 1e-10:
        return 1.0
    return min((width - 2 * margin) / max_sx, (height - 2 * margin) / max_sy)


# ── Rasterizer → float intensity ─────────────────────────────────────────────


def _rasterize_intensity(
    screen_xy: np.ndarray,
    depth: np.ndarray,
    tri_indices: np.ndarray,
    tri_normals: np.ndarray,
    width: int,
    height: int,
) -> np.ndarray:
    """Z-buffer rasterize → float32 (H, W) intensity. Background = -1, surface = [0, 1]."""
    ambient = 0.15
    diffuse = np.clip(tri_normals @ _LIGHT_DIR, 0.0, 1.0)
    tri_intensity = (ambient + (1.0 - ambient) * diffuse).astype(np.float32)

    img = np.full((height, width), -1.0, dtype=np.float32)
    z_buf = np.full((height, width), -np.inf, dtype=np.float64)
    py_grid, px_grid = np.mgrid[0:height, 0:width].astype(np.float64)

    for idx in range(len(tri_indices)):
        i0, i1, i2 = (
            int(tri_indices[idx, 0]),
            int(tri_indices[idx, 1]),
            int(tri_indices[idx, 2]),
        )
        sx0, sy0 = screen_xy[i0, 0], screen_xy[i0, 1]
        sx1, sy1 = screen_xy[i1, 0], screen_xy[i1, 1]
        sx2, sy2 = screen_xy[i2, 0], screen_xy[i2, 1]

        bx0 = max(0, math.floor(min(sx0, sx1, sx2)))
        bx1 = min(width - 1, math.ceil(max(sx0, sx1, sx2)))
        by0 = max(0, math.floor(min(sy0, sy1, sy2)))
        by1 = min(height - 1, math.ceil(max(sy0, sy1, sy2)))
        if bx0 > bx1 or by0 > by1:
            continue

        denom = (sy1 - sy2) * (sx0 - sx2) + (sx2 - sx1) * (sy0 - sy2)
        if abs(denom) < 1e-10:
            continue

        px = px_grid[by0 : by1 + 1, bx0 : bx1 + 1]
        py = py_grid[by0 : by1 + 1, bx0 : bx1 + 1]

        w0 = ((sy1 - sy2) * (px - sx2) + (sx2 - sx1) * (py - sy2)) / denom
        w1 = ((sy2 - sy0) * (px - sx2) + (sx0 - sx2) * (py - sy2)) / denom
        w2 = 1.0 - w0 - w1

        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue

        z = w0 * depth[i0] + w1 * depth[i1] + w2 * depth[i2]
        sub_z = z_buf[by0 : by1 + 1, bx0 : bx1 + 1]
        update = inside & (z > sub_z)
        if not update.any():
            continue

        z_buf[by0 : by1 + 1, bx0 : bx1 + 1][update] = z[update]
        img[by0 : by1 + 1, bx0 : bx1 + 1][update] = tri_intensity[idx]

    return img


# ── Main function ─────────────────────────────────────────────────────────────


def render_step_png(
    step_path: Path,
    output_path: Path,
    panel_width: int = 560,
    panel_height: int = 420,
    tolerance: float = 0.5,
) -> Path:
    """Render a STEP file to a 3-panel PNG (side, end, isometric).

    Args:
        step_path:    Path to the STEP file to render.
        output_path:  Where to save the PNG.
        panel_width:  Pixel width of each individual panel.
        panel_height: Pixel height of each individual panel.
        tolerance:    Tessellation tolerance in mm (lower = finer detail, slower).

    Returns:
        output_path on success.
    """
    import matplotlib.pyplot as plt

    plt.switch_backend("agg")

    from matplotlib.colors import LinearSegmentedColormap
    from rocketsmith.build123d.ascii import _load_centered_mesh

    verts, tris, normals = _load_centered_mesh(step_path, tolerance=tolerance)
    if len(verts) == 0:
        raise ValueError(f"No geometry found in STEP file: {step_path}")

    W, H = panel_width, panel_height

    # ── Scales ────────────────────────────────────────────────
    # Side: horiz=Z(axis 2), vert=Y(axis 1)
    # End:  horiz=X(axis 0), vert=Y(axis 1)
    scale_side = _ortho_scale(verts, horiz_axis=2, vert_axis=1, width=W, height=H)
    scale_end = _ortho_scale(verts, horiz_axis=0, vert_axis=1, width=W, height=H)
    scale_iso = _iso_scale(verts, W, H)

    # ── Project ───────────────────────────────────────────────
    xy_side, d_side = _project_side(verts, scale_side, W, H)
    xy_end, d_end = _project_end(verts, scale_end, W, H)
    xy_iso, d_iso, n_iso = _project_iso(verts, normals, scale_iso, W, H, angle_deg=45.0)

    # ── Rasterize ─────────────────────────────────────────────
    img_side = _rasterize_intensity(xy_side, d_side, tris, normals, W, H)
    img_end = _rasterize_intensity(xy_end, d_end, tris, normals, W, H)
    img_iso = _rasterize_intensity(xy_iso, d_iso, tris, n_iso, W, H)

    # ── Colormap: dark navy bg → steel blue shadow → light steel highlight ────
    bg = (0.06, 0.06, 0.10)
    part_cmap = LinearSegmentedColormap.from_list(
        "rocket_part",
        [
            (0.00, (0.10, 0.16, 0.28)),  # deep shadow
            (0.20, (0.20, 0.32, 0.50)),  # shadow
            (0.50, (0.40, 0.58, 0.76)),  # midtone
            (0.80, (0.65, 0.80, 0.93)),  # highlight
            (1.00, (0.90, 0.95, 1.00)),  # specular
        ],
    )

    # ── Build figure ──────────────────────────────────────────
    dpi = 100
    fig_w = (W * 3) / dpi
    fig_h = (H + 60) / dpi  # extra height for title + labels

    fig, axes = plt.subplots(1, 3, figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_facecolor(bg)
    fig.suptitle(step_path.name, color="white", fontsize=11, y=0.98)

    panels = [
        (img_side, "Side  (−X camera, Z horizontal: low Z left → high Z right)"),
        (img_end, "End  (+Z camera looking −Z: high-Z face of part)"),
        (img_iso, "Isometric 45°  (part-local frame)"),
    ]

    for ax, (img, title) in zip(axes, panels):
        ax.set_facecolor(bg)
        ax.set_title(title, color="#aaccee", fontsize=8, pad=4)
        ax.axis("off")

        # Composite: background + shaded part
        rgba = np.zeros((H, W, 4), dtype=np.float32)
        rgba[:, :, 0] = bg[0]
        rgba[:, :, 1] = bg[1]
        rgba[:, :, 2] = bg[2]
        rgba[:, :, 3] = 1.0

        mask = img >= 0
        if mask.any():
            part_rgba = part_cmap(img[mask])  # (N, 4)
            rgba[mask, :3] = part_rgba[:, :3]

        ax.imshow(rgba, origin="upper", interpolation="bilinear", aspect="equal")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=bg)
    plt.close(fig)

    return output_path
