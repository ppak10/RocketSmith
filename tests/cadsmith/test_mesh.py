"""Tests for STEP tessellation and asset rendering (image, GIF, ASCII)."""

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


# ── load_step_mesh ─────────────────────────────────────────────────────────────


class TestLoadStepMesh:
    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_returns_valid_arrays(self, step_file):
        from rocketsmith.cadsmith.assets.ascii.mesh import load_step_mesh

        verts, tris, normals = load_step_mesh(step_file, tolerance=1.0)

        assert verts.ndim == 2 and verts.shape[1] == 3
        assert tris.ndim == 2 and tris.shape[1] == 3
        assert normals.ndim == 2 and normals.shape[1] == 3
        assert len(tris) == len(normals)
        assert len(verts) > 0
        assert len(tris) > 0

    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_triangle_indices_in_range(self, step_file):
        from rocketsmith.cadsmith.assets.ascii.mesh import load_step_mesh

        verts, tris, _ = load_step_mesh(step_file, tolerance=1.0)

        assert tris.min() >= 0
        assert tris.max() < len(verts)

    @pytest.mark.parametrize("step_file", STEP_FILES, ids=STEP_IDS)
    def test_normals_are_unit_length(self, step_file):
        from rocketsmith.cadsmith.assets.ascii.mesh import load_step_mesh

        _, _, normals = load_step_mesh(step_file, tolerance=1.0)

        lengths = np.linalg.norm(normals, axis=1)
        non_degenerate = lengths > 0.5
        np.testing.assert_allclose(lengths[non_degenerate], 1.0, atol=1e-6)

    def test_empty_on_missing_file(self, tmp_path):
        from rocketsmith.cadsmith.assets.ascii.mesh import load_step_mesh

        with pytest.raises(Exception):
            load_step_mesh(tmp_path / "nonexistent.step")

    def test_finer_tolerance_produces_more_triangles(self):
        if not STEP_FILES:
            pytest.skip("No STEP files available")

        step_file = STEP_FILES[0]
        from rocketsmith.cadsmith.assets.ascii.mesh import load_step_mesh

        _, tris_coarse, _ = load_step_mesh(step_file, tolerance=2.0)
        _, tris_fine, _ = load_step_mesh(step_file, tolerance=0.5)

        assert len(tris_fine) > len(tris_coarse)


# ── render_isometric_frame (synthetic mesh, no build123d needed) ───────────────


def _make_box_mesh():
    """Unit cube mesh for lightweight rendering tests."""
    verts = np.array(
        [
            [-1, -1, -1],
            [1, -1, -1],
            [1, 1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
            [1, -1, 1],
            [1, 1, 1],
            [-1, 1, 1],
        ],
        dtype=np.float64,
    )
    tris = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [2, 6, 7],
            [2, 7, 3],
            [0, 3, 7],
            [0, 7, 4],
            [1, 5, 6],
            [1, 6, 2],
        ],
        dtype=np.int32,
    )
    v0, v1, v2 = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.where(lengths < 1e-12, 1.0, lengths)
    return verts, tris, normals


class TestRenderIsometricFrame:
    def test_returns_correct_shape(self):
        from rocketsmith.cadsmith.assets.image import _iso_scale, render_isometric_frame

        verts, tris, normals = _make_box_mesh()
        W, H = 200, 150
        scale = _iso_scale(verts, W, H)
        result = render_isometric_frame(verts, tris, normals, W, H, 45.0, scale)

        assert result.shape == (H, W)
        assert result.dtype == np.float32

    def test_background_is_minus_one(self):
        from rocketsmith.cadsmith.assets.image import _iso_scale, render_isometric_frame

        verts, tris, normals = _make_box_mesh()
        W, H = 200, 150
        scale = _iso_scale(verts, W, H)
        result = render_isometric_frame(verts, tris, normals, W, H, 45.0, scale)

        assert (result[result < 0] == -1.0).all()

    def test_surface_pixels_in_range(self):
        from rocketsmith.cadsmith.assets.image import _iso_scale, render_isometric_frame

        verts, tris, normals = _make_box_mesh()
        W, H = 200, 150
        scale = _iso_scale(verts, W, H)
        result = render_isometric_frame(verts, tris, normals, W, H, 45.0, scale)

        surface = result[result >= 0]
        assert len(surface) > 0
        assert float(surface.min()) >= 0.0
        assert float(surface.max()) <= 1.0

    def test_rotation_changes_frame(self):
        from rocketsmith.cadsmith.assets.image import _iso_scale, render_isometric_frame

        verts, tris, normals = _make_box_mesh()
        W, H = 200, 150
        scale = _iso_scale(verts, W, H)
        frame_0 = render_isometric_frame(verts, tris, normals, W, H, 0.0, scale)
        frame_90 = render_isometric_frame(verts, tris, normals, W, H, 90.0, scale)

        assert not np.array_equal(frame_0, frame_90)


# ── render_step_png ────────────────────────────────────────────────────────────


class TestRenderStepPng:
    @pytest.mark.skipif(not STEP_FILES, reason="No STEP files available")
    def test_creates_png_file(self, tmp_path):
        from rocketsmith.cadsmith.assets.image import render_step_png

        output = tmp_path / "test.png"
        result = render_step_png(STEP_FILES[0], output, width=160, height=120)

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.skipif(not STEP_FILES, reason="No STEP files available")
    def test_missing_step_raises(self, tmp_path):
        from rocketsmith.cadsmith.assets.image import render_step_png

        with pytest.raises(Exception):
            render_step_png(tmp_path / "missing.step", tmp_path / "out.png")


# ── render_step_gif ────────────────────────────────────────────────────────────


class TestRenderStepGif:
    @pytest.mark.skipif(not STEP_FILES, reason="No STEP files available")
    def test_creates_gif_file(self, tmp_path):
        from rocketsmith.cadsmith.assets.gif import render_step_gif

        output = tmp_path / "test.gif"
        result = render_step_gif(STEP_FILES[0], output, frames=4, width=200, height=150)

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.skipif(not STEP_FILES, reason="No STEP files available")
    def test_gif_has_correct_frame_count(self, tmp_path):
        from PIL import Image

        from rocketsmith.cadsmith.assets.gif import render_step_gif

        output = tmp_path / "test.gif"
        render_step_gif(STEP_FILES[0], output, frames=4, width=200, height=150)

        with Image.open(output) as img:
            assert img.n_frames == 4


# ── render_ascii_animation ─────────────────────────────────────────────────────


class TestRenderAsciiAnimation:
    @pytest.mark.skipif(not STEP_FILES, reason="No STEP files available")
    def test_creates_txt_file(self, tmp_path):
        from rocketsmith.cadsmith.assets.ascii import render_ascii_animation

        output = tmp_path / "test.txt"
        result = render_ascii_animation(
            STEP_FILES[0], output, frames=4, width=40, height=20
        )

        assert result == output
        assert output.exists()

    @pytest.mark.skipif(not STEP_FILES, reason="No STEP files available")
    def test_correct_frame_count(self, tmp_path):
        from rocketsmith.cadsmith.assets.ascii import render_ascii_animation

        output = tmp_path / "test.txt"
        render_ascii_animation(STEP_FILES[0], output, frames=8, width=40, height=20)

        content = output.read_text(encoding="utf-8")
        assert len(content.split("\f")) == 8

    @pytest.mark.skipif(not STEP_FILES, reason="No STEP files available")
    def test_frames_contain_ascii(self, tmp_path):
        from rocketsmith.cadsmith.assets.ascii import render_ascii_animation

        output = tmp_path / "test.txt"
        render_ascii_animation(STEP_FILES[0], output, frames=4, width=40, height=20)

        content = output.read_text(encoding="utf-8")
        for frame in content.split("\f"):
            assert len(frame.strip()) > 0
