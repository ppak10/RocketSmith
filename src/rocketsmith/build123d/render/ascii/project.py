"""Isometric projection and rotation for STEP ASCII rendering."""

from __future__ import annotations

import math

import numpy as np

from .core import CHAR_ASPECT


def rotate_y(points: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate points (or vectors) around the Y axis.

    Args:
        points: (N, 3) array of 3D points or direction vectors.
        angle_deg: Rotation angle in degrees.

    Returns:
        (N, 3) rotated array (same shape as input).
    """
    a = math.radians(angle_deg)
    cos_a, sin_a = math.cos(a), math.sin(a)
    rot = np.array(
        [
            [cos_a, 0.0, sin_a],
            [0.0, 1.0, 0.0],
            [-sin_a, 0.0, cos_a],
        ],
        dtype=np.float64,
    )
    # Suppress spurious BLAS warnings (e.g. macOS Accelerate false positives)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        return points @ rot.T


def compute_projected_spans(
    vertices: np.ndarray,
    char_aspect: float = CHAR_ASPECT,
    sample_angles: int = 8,
) -> tuple[float, float]:
    """Compute max projected X and Y spans over all sampled rotation angles.

    Args:
        vertices: (N, 3) centered vertex positions.
        char_aspect: Terminal character width/height ratio.
        sample_angles: Number of rotation angles to sample.

    Returns:
        (max_sx_span, max_sy_span) in projected units (before scaling).
    """
    if len(vertices) == 0:
        return 1.0, 1.0

    cos30 = math.cos(math.radians(30))
    sin30 = math.sin(math.radians(30))

    max_sx_span = 0.0
    max_sy_span = 0.0

    for i in range(sample_angles):
        angle_deg = 360.0 * i / sample_angles
        rotated = rotate_y(vertices, angle_deg)
        x, y, z = rotated[:, 0], rotated[:, 1], rotated[:, 2]
        sx = (x - z) * cos30 / char_aspect
        sy = -y + (x + z) * sin30
        max_sx_span = max(max_sx_span, float(sx.max() - sx.min()))
        max_sy_span = max(max_sy_span, float(sy.max() - sy.min()))

    return max_sx_span, max_sy_span


def compute_scale(
    vertices: np.ndarray,
    width: int,
    height: int,
    margin: int = 2,
    char_aspect: float = CHAR_ASPECT,
    sample_angles: int = 8,
) -> float:
    """Compute a rotation-stable scale factor by sampling projected extents.

    Projects the mesh at ``sample_angles`` evenly-spaced Y-axis rotation angles
    and uses the maximum projected bounding box so the shape stays fully on-screen
    throughout the animation without changing size.

    Args:
        vertices: (N, 3) centered vertex positions.
        width: Canvas width in characters.
        height: Canvas height in characters.
        margin: Padding on each side in characters.
        char_aspect: Terminal character width/height ratio.
        sample_angles: Number of rotation angles to sample (more = safer).

    Returns:
        Scale factor (world mm → canvas characters).
    """
    if len(vertices) == 0:
        return 1.0

    max_sx_span, max_sy_span = compute_projected_spans(
        vertices, char_aspect, sample_angles
    )

    if max_sx_span < 1e-10 or max_sy_span < 1e-10:
        return 1.0

    scale_x = (width - 2 * margin) / max_sx_span
    scale_y = (height - 2 * margin) / max_sy_span
    return min(scale_x, scale_y)


def project(
    vertices: np.ndarray,
    scale: float,
    width: int,
    height: int,
    char_aspect: float = CHAR_ASPECT,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply isometric projection and map to canvas coordinates.

    Uses standard isometric projection (Y-up, camera at top-right-front):
        screen_x = (world_x - world_z) * cos30 / char_aspect
        screen_y = -world_y + (world_x + world_z) * sin30

    Args:
        vertices: (N, 3) 3D positions centered at origin.
        scale: Scale factor from :func:`compute_scale`.
        width: Canvas width in characters.
        height: Canvas height in characters.
        char_aspect: Terminal character width/height ratio.

    Returns:
        screen_xy: (N, 2) float64 canvas coordinates [col, row].
        depth: (N,) float64 depth values — larger means closer to camera.
    """
    cos30 = math.cos(math.radians(30))
    sin30 = math.sin(math.radians(30))

    x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]

    # Isometric projection (screen Y increases downward)
    sx = (x - z) * cos30 / char_aspect
    sy = -y + (x + z) * sin30

    # Scale and center on canvas
    cx = sx * scale + width / 2.0
    cy = sy * scale + height / 2.0

    # Depth: dot with (1,1,1) view direction — larger = closer to camera
    depth = x + y + z

    return np.stack([cx, cy], axis=1), depth
