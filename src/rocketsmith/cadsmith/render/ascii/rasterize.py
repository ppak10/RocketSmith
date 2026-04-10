"""Z-buffer rasterization to ASCII canvas."""

from __future__ import annotations

import math

import numpy as np

from .core import SHADE_CHARS, LIGHT_DIR, VIEW_DIR


def _compute_shade_indices(
    tri_normals: np.ndarray,
    light_dir: np.ndarray = LIGHT_DIR,
) -> np.ndarray:
    """Compute shade character indices for each triangle.

    Args:
        tri_normals: (M, 3) unit normals.
        light_dir: (3,) unit light direction vector.

    Returns:
        (M,) int32 array of indices into SHADE_CHARS.
    """
    ambient = 0.15
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        diffuse = np.clip(tri_normals @ light_dir, 0.0, 1.0)
    intensity = ambient + (1.0 - ambient) * diffuse
    n_chars = len(SHADE_CHARS)
    return np.clip((intensity * (n_chars - 1)).astype(np.int32), 0, n_chars - 1)


def rasterize(
    screen_xy: np.ndarray,
    depth: np.ndarray,
    tri_indices: np.ndarray,
    shade_indices: np.ndarray,
    width: int,
    height: int,
) -> list[str]:
    """Rasterize shaded triangles to ASCII rows via z-buffer.

    Each pixel gets the character of the closest (highest-depth) triangle
    that covers it.

    Args:
        screen_xy:     (N, 2) canvas coordinates [col, row].
        depth:         (N,) per-vertex depth — larger = closer to camera.
        tri_indices:   (M, 3) vertex index triples.
        shade_indices: (M,) shade character index per triangle.
        width:         Canvas width in characters.
        height:        Canvas height in characters.

    Returns:
        List of ``height`` strings, each of length ``width``.
    """
    shade_buf = np.full((height, width), -1, dtype=np.int16)
    z_buf = np.full((height, width), -np.inf)

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

        d0, d1, d2 = depth[i0], depth[i1], depth[i2]
        z = w0 * d0 + w1 * d1 + w2 * d2

        sub_zbuf = z_buf[by0 : by1 + 1, bx0 : bx1 + 1]
        update = inside & (z > sub_zbuf)
        if not update.any():
            continue

        z_buf[by0 : by1 + 1, bx0 : bx1 + 1][update] = z[update]
        shade_buf[by0 : by1 + 1, bx0 : bx1 + 1][update] = shade_indices[idx]

    chars_arr = np.array(list(SHADE_CHARS), dtype="U1")
    result = np.full((height, width), " ", dtype="U1")
    mask = shade_buf >= 0
    result[mask] = chars_arr[shade_buf[mask]]

    return ["".join(row) for row in result]


def _draw_line(
    canvas: list[list[str]],
    z_buf: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    d0: float,
    d1: float,
    width: int,
    height: int,
) -> None:
    """Draw a line segment via Bresenham's algorithm with z-buffer test."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    steps = max(dx, dy)

    x, y, step = x0, y0, 0
    while True:
        if 0 <= x < width and 0 <= y < height:
            t = step / steps if steps > 0 else 0.0
            z = d0 + (d1 - d0) * t
            if z > z_buf[y, x]:
                z_buf[y, x] = z
                if dx > dy * 2:
                    canvas[y][x] = "-"
                elif dy > dx * 2:
                    canvas[y][x] = "|"
                elif sx == sy:
                    canvas[y][x] = "\\"
                else:
                    canvas[y][x] = "/"
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        step += 1


def rasterize_wireframe(
    screen_xy: np.ndarray,
    depth: np.ndarray,
    tri_indices: np.ndarray,
    tri_normals: np.ndarray,
    width: int,
    height: int,
) -> list[str]:
    """Render front-facing triangle edges to ASCII rows.

    Back-facing triangles are culled for a cleaner wireframe appearance.

    Args:
        screen_xy:   (N, 2) canvas coordinates [col, row].
        depth:       (N,) per-vertex depth — larger = closer to camera.
        tri_indices: (M, 3) vertex index triples.
        tri_normals: (M, 3) unit normals (used for back-face culling).
        width:       Canvas width in characters.
        height:      Canvas height in characters.

    Returns:
        List of ``height`` strings, each of length ``width``.
    """
    canvas = [[" "] * width for _ in range(height)]
    z_buf = np.full((height, width), -np.inf)

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        facing = tri_normals @ VIEW_DIR

    for idx in range(len(tri_indices)):
        if facing[idx] <= 0.0:
            continue

        i0, i1, i2 = (
            int(tri_indices[idx, 0]),
            int(tri_indices[idx, 1]),
            int(tri_indices[idx, 2]),
        )
        pts = [
            (int(round(screen_xy[i, 0])), int(round(screen_xy[i, 1])), depth[i])
            for i in (i0, i1, i2)
        ]
        for j in range(3):
            xa, ya, da = pts[j]
            xb, yb, db = pts[(j + 1) % 3]
            _draw_line(canvas, z_buf, xa, ya, xb, yb, da, db, width, height)

    return ["".join(row) for row in canvas]
