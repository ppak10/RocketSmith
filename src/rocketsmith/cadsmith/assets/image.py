"""PNG renderer for STEP files — single isometric thumbnail."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

_LIGHT = np.array([1.0, 2.0, 1.5])
_LIGHT_DIR: np.ndarray = _LIGHT / np.linalg.norm(_LIGHT)

_BG = (0.06, 0.06, 0.10)
_PART_COLORS = [
    (0.00, (0.10, 0.16, 0.28)),
    (0.20, (0.20, 0.32, 0.50)),
    (0.50, (0.40, 0.58, 0.76)),
    (0.80, (0.65, 0.80, 0.93)),
    (1.00, (0.90, 0.95, 1.00)),
]


def _iso_scale(
    vertices: np.ndarray, width: int, height: int, margin: int = 30
) -> float:
    from rocketsmith.cadsmith.assets.ascii.project import rotate_y

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


def _project_iso(
    vertices: np.ndarray,
    normals: np.ndarray,
    scale: float,
    width: int,
    height: int,
    angle_deg: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from rocketsmith.cadsmith.assets.ascii.project import rotate_y

    rv = rotate_y(vertices, angle_deg)
    rn = rotate_y(normals, angle_deg)

    cos30 = math.cos(math.radians(30))
    sin30 = math.sin(math.radians(30))

    x, y, z = rv[:, 0], rv[:, 1], rv[:, 2]
    sx = (x - z) * cos30 * scale + width / 2.0
    sy = (-y + (x + z) * sin30) * scale + height / 2.0
    depth = x + y + z

    return np.stack([sx, sy], axis=1), depth, rn


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
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        diffuse = np.clip(tri_normals @ _LIGHT_DIR, 0.0, 1.0)
    diffuse = np.where(np.isfinite(diffuse), diffuse, 0.0)
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


def render_isometric_frame(
    verts: np.ndarray,
    tris: np.ndarray,
    normals: np.ndarray,
    width: int,
    height: int,
    angle_deg: float,
    scale: float,
) -> np.ndarray:
    """Render one isometric frame → float32 (H, W) intensity. Background = -1."""
    xy, depth, rot_normals = _project_iso(
        verts, normals, scale, width, height, angle_deg
    )
    return _rasterize_intensity(xy, depth, tris, rot_normals, width, height)


def render_step_png(
    step_path: Path,
    output_path: Path,
    width: int = 560,
    height: int = 420,
    angle_deg: float = 45.0,
    tolerance: float = 0.5,
) -> Path:
    """Render a STEP file to a single isometric PNG thumbnail.

    Args:
        step_path:   Path to the STEP file.
        output_path: Where to save the PNG.
        width:       Image width in pixels.
        height:      Image height in pixels.
        angle_deg:   Y-axis rotation angle for the isometric view.
        tolerance:   Tessellation tolerance in mm.

    Returns:
        output_path on success.
    """
    import matplotlib.pyplot as plt

    plt.switch_backend("agg")
    from matplotlib.colors import LinearSegmentedColormap

    from rocketsmith.cadsmith.assets.ascii import _load_centered_mesh

    verts, tris, normals = _load_centered_mesh(step_path, tolerance=tolerance)
    if len(verts) == 0:
        raise ValueError(f"No geometry found in STEP file: {step_path}")

    scale = _iso_scale(verts, width, height)
    intensity = render_isometric_frame(
        verts, tris, normals, width, height, angle_deg, scale
    )

    part_cmap = LinearSegmentedColormap.from_list("rocket_part", _PART_COLORS)

    rgba = np.zeros((height, width, 4), dtype=np.float32)
    rgba[:, :, 0] = _BG[0]
    rgba[:, :, 1] = _BG[1]
    rgba[:, :, 2] = _BG[2]
    rgba[:, :, 3] = 1.0

    mask = intensity >= 0
    if mask.any():
        rgba[mask, :3] = part_cmap(intensity[mask])[:, :3]

    dpi = 100
    fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)
    ax.axis("off")
    ax.imshow(rgba, origin="upper", interpolation="bilinear", aspect="equal")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor=_BG, pad_inches=0)
    plt.close(fig)

    return output_path
