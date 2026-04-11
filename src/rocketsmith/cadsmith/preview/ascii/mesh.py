"""STEP file tessellation to triangle mesh via build123d."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def load_step_mesh(
    step_path: Path,
    tolerance: float = 1.0,
    angular_tolerance: float = 0.1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load a STEP file and tessellate it into a triangle mesh.

    Args:
        step_path: Path to the STEP file.
        tolerance: Linear deflection tolerance in mm (smaller = finer mesh).
        angular_tolerance: Angular deflection tolerance in radians.

    Returns:
        vertices:    (N, 3) float64 array of vertex positions in mm.
        tri_indices: (M, 3) int32 array of vertex indices per triangle.
        tri_normals: (M, 3) float64 array of unit outward per-triangle normals.
    """
    from build123d import import_step

    _empty = (
        np.zeros((0, 3), dtype=np.float64),
        np.zeros((0, 3), dtype=np.int32),
        np.zeros((0, 3), dtype=np.float64),
    )

    shape = import_step(str(step_path))

    all_verts: list[np.ndarray] = []
    all_tris: list[np.ndarray] = []
    vert_offset = 0

    for face in shape.faces():
        rv, rt = face.tessellate(tolerance, angular_tolerance)
        if not rv or not rt:
            continue

        fv = np.array([(v.X, v.Y, v.Z) for v in rv], dtype=np.float64)
        ft = np.array(rt, dtype=np.int32)

        all_verts.append(fv)
        all_tris.append(ft + vert_offset)
        vert_offset += len(fv)

    if not all_verts:
        return _empty

    verts = np.vstack(all_verts)
    tris = np.vstack(all_tris)

    # Compute per-triangle normals via cross product
    v0 = verts[tris[:, 0]]
    v1 = verts[tris[:, 1]]
    v2 = verts[tris[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-12, 1.0, lengths)
    normals = normals / lengths

    return verts, tris, normals
