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

    Tessellates each face individually and uses each face's analytic bounding
    box to discard tessellation artifacts (common on degenerate torus surfaces).

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
        bb = face.bounding_box()
        # For axisymmetric rocket parts, X and Y extents should be symmetric.
        # Degenerate torus faces often report huge analytic bounds on one side.
        max_x = min(abs(bb.min.X), abs(bb.max.X))
        max_y = min(abs(bb.min.Y), abs(bb.max.Y))

        # If the face isn't centered at the origin, we don't want to overly constrain it,
        # but for RocketSmith components, the main axis is Z, so we clamp X/Y symmetrically.
        # Use a fallback to original bounds if max_x/max_y is too small (e.g. off-axis fins).
        # Actually, the simplest fix for degenerate torus artifacts is to use the max absolute
        # bound of X and Y if they are symmetric-ish, but for the spike we want the MIN absolute bound
        # of the "base".
        # Let's just use the max of the min absolute values of X and Y across the face's vertices,
        # but since we don't know the vertices yet, we'll bound to the overall shape's valid faces?
        # A simpler robust approach: if the bounding box spans across 0 and is wildly asymmetric,
        # clamp to the smaller side, because physical rocket parts are symmetric.
        clamp_r = None
        if (
            bb.min.X < 0
            and bb.max.X > 0
            and max(abs(bb.min.X), bb.max.X) > 5 * min(abs(bb.min.X), bb.max.X)
        ):
            clamp_x = min(abs(bb.min.X), bb.max.X)
            bb_min_X, bb_max_X = -clamp_x, clamp_x
            clamp_r = clamp_x
        else:
            bb_min_X, bb_max_X = bb.min.X, bb.max.X

        if (
            bb.min.Y < 0
            and bb.max.Y > 0
            and max(abs(bb.min.Y), bb.max.Y) > 5 * min(abs(bb.min.Y), bb.max.Y)
        ):
            clamp_y = min(abs(bb.min.Y), bb.max.Y)
            bb_min_Y, bb_max_Y = -clamp_y, clamp_y
            if clamp_r is None:
                clamp_r = clamp_y
        else:
            bb_min_Y, bb_max_Y = bb.min.Y, bb.max.Y

        bb_min = np.array([bb_min_X, bb_min_Y, bb.min.Z])
        bb_max = np.array([bb_max_X, bb_max_Y, bb.max.Z])

        rv, rt = face.tessellate(tolerance, angular_tolerance)
        if not rv or not rt:
            continue

        fv = np.array([(v.X, v.Y, v.Z) for v in rv], dtype=np.float64)
        ft = np.array(rt, dtype=np.int32)

        if clamp_r is not None:
            # Degenerate torus artifacts often curve back into the valid X/Y region.
            # We find the Z bound where the huge artifact begins, and clamp Z to it.
            R = np.sqrt(fv[:, 0] ** 2 + fv[:, 1] ** 2)
            artifact_mask = R > clamp_r * 1.5
            if np.any(artifact_mask):
                artifact_Z = fv[artifact_mask, 2]
                if artifact_Z.mean() > fv[:, 2].mean():
                    z_cap = artifact_Z.min()
                    bb_max[2] = min(bb_max[2], z_cap)
                else:
                    z_cap = artifact_Z.max()
                    bb_min[2] = max(bb_min[2], z_cap)

        # Tolerance: 0.2% of each dimension, minimum 0.5 mm
        tol_vec = np.maximum((bb_max - bb_min) * 0.002, 0.5)

        # Filter vertices outside this face's analytic bounding box
        valid_v = np.all((fv >= bb_min - tol_vec) & (fv <= bb_max + tol_vec), axis=1)
        if not valid_v.all():
            valid_t = valid_v[ft].all(axis=1)
            ft = ft[valid_t]
            if len(ft) == 0:
                continue
            used = np.unique(ft)
            remap = np.full(len(fv), -1, dtype=np.int32)
            remap[used] = np.arange(len(used), dtype=np.int32)
            fv = fv[used]
            ft = remap[ft]

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
