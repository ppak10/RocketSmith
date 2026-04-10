"""Tests for STEP file tessellation (load_step_mesh and viewer _load_mesh)."""

from pathlib import Path

import numpy as np
import pytest

STEP_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "rocketsmith"
    / "data"
    / "part"
)

STEP_FILES = list(STEP_DIR.glob("*.step"))
STEP_IDS = [p.stem for p in STEP_FILES]


# ── load_step_mesh (ASCII/PNG renderer) ──────────────────────────────────────


class TestLoadStepMesh:
    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_returns_valid_arrays(self, step_file):
        from rocketsmith.cadsmith.render.ascii.mesh import load_step_mesh

        verts, tris, normals = load_step_mesh(step_file, tolerance=1.0)

        assert verts.ndim == 2 and verts.shape[1] == 3
        assert tris.ndim == 2 and tris.shape[1] == 3
        assert normals.ndim == 2 and normals.shape[1] == 3
        assert len(tris) == len(normals)
        assert len(verts) > 0
        assert len(tris) > 0

    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_triangle_indices_in_range(self, step_file):
        from rocketsmith.cadsmith.render.ascii.mesh import load_step_mesh

        verts, tris, _ = load_step_mesh(step_file, tolerance=1.0)

        assert tris.min() >= 0
        assert tris.max() < len(verts)

    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_normals_are_unit_length(self, step_file):
        from rocketsmith.cadsmith.render.ascii.mesh import load_step_mesh

        _, _, normals = load_step_mesh(step_file, tolerance=1.0)

        lengths = np.linalg.norm(normals, axis=1)
        # A small number of degenerate triangles (area ≈ 0) produce normals
        # that aren't perfectly unit-length; only check non-degenerate ones.
        non_degenerate = lengths > 0.5
        np.testing.assert_allclose(lengths[non_degenerate], 1.0, atol=1e-6)

    def test_empty_on_missing_file(self, tmp_path):
        from rocketsmith.cadsmith.render.ascii.mesh import load_step_mesh

        with pytest.raises(Exception):
            load_step_mesh(tmp_path / "nonexistent.step")

    def test_finer_tolerance_produces_more_triangles(self):
        from rocketsmith.cadsmith.render.ascii.mesh import load_step_mesh

        if not STEP_FILES:
            pytest.skip("No STEP files available")

        step_file = STEP_FILES[0]
        _, tris_coarse, _ = load_step_mesh(step_file, tolerance=2.0)
        _, tris_fine, _ = load_step_mesh(step_file, tolerance=0.5)

        assert len(tris_fine) > len(tris_coarse)


# ── _load_mesh (viewer) ─────────────────────────────────────────────────────


class TestViewerLoadMesh:
    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_returns_float32_arrays(self, step_file):
        from rocketsmith.cadsmith.viewer.viewer import _load_mesh

        verts, tris, normals = _load_mesh(step_file, tolerance=1.0)

        assert verts.dtype == np.float32
        assert normals.dtype == np.float32
        assert len(verts) > 0
        assert len(tris) > 0

    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_mesh_is_centered(self, step_file):
        from rocketsmith.cadsmith.viewer.viewer import _load_mesh

        verts, _, _ = _load_mesh(step_file, tolerance=1.0)

        center = (verts.min(axis=0) + verts.max(axis=0)) / 2
        np.testing.assert_allclose(center, 0.0, atol=1e-3)

    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_triangle_indices_in_range(self, step_file):
        from rocketsmith.cadsmith.viewer.viewer import _load_mesh

        verts, tris, _ = _load_mesh(step_file, tolerance=1.0)

        assert tris.min() >= 0
        assert tris.max() < len(verts)

    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_normals_are_unit_length(self, step_file):
        from rocketsmith.cadsmith.viewer.viewer import _load_mesh

        _, _, normals = _load_mesh(step_file, tolerance=1.0)

        lengths = np.linalg.norm(normals, axis=1)
        non_degenerate = lengths > 0.5
        np.testing.assert_allclose(lengths[non_degenerate], 1.0, atol=1e-3)
