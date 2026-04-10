"""
Lightweight STEP file viewer with hot-reload.

Uses build123d for STEP tessellation (already installed) and PySide6 + OpenGL
for rendering. Watches the STEP file for mtime changes and reloads automatically.

Dependencies beyond the rocketsmith install:
    PySide6  — Qt bindings with OpenGL widget
    PyOpenGL — OpenGL Python bindings

The MCP tool launches this as ``uv run --with PySide6,PyOpenGL python viewer.py <path>``.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

POLL_INTERVAL_MS = 500
DEBOUNCE_SEC = 0.3


# ---- Mesh loading (reuses rocketsmith's existing tessellator) ----


def _load_mesh(step_path: Path, tolerance: float = 0.5, angular_tolerance: float = 0.1):
    """Load a STEP file and tessellate all faces into a triangle mesh."""
    from build123d import import_step

    shape = import_step(str(step_path))

    all_verts: list[np.ndarray] = []
    all_tris: list[np.ndarray] = []
    offset = 0

    for face in shape.faces():
        rv, rt = face.tessellate(tolerance, angular_tolerance)
        if not rv or not rt:
            continue
        fv = np.array([(v.X, v.Y, v.Z) for v in rv], dtype=np.float64)
        ft = np.array(rt, dtype=np.int32)
        all_verts.append(fv)
        all_tris.append(ft + offset)
        offset += len(fv)

    if not all_verts:
        empty = np.zeros((0, 3), dtype=np.float32)
        return empty, np.zeros((0, 3), dtype=np.int32), empty

    verts = np.vstack(all_verts)
    tris = np.vstack(all_tris)

    # Center the mesh
    center = (verts.min(axis=0) + verts.max(axis=0)) / 2
    verts = verts - center

    # Per-triangle normals
    v0, v1, v2 = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    normals = np.cross(v1 - v0, v2 - v0)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-12, 1.0, lengths)
    normals = normals / lengths

    return verts.astype(np.float32), tris, normals.astype(np.float32)


# ---- OpenGL 3D widget ----


class GLViewer:
    """Manages the OpenGL state and orbit camera for the mesh."""

    # Display modes (cycled by the toggle button)
    MODES = ["shaded", "wireframe", "shaded+wireframe"]

    def __init__(self):
        self.verts: np.ndarray | None = None
        self.tris: np.ndarray | None = None
        self.normals: np.ndarray | None = None
        self.vert_normals: np.ndarray | None = None

        # Camera state (Z-up convention: a -90° base tilt maps Z to screen-up)
        self.rot_x = -25.0  # pitch (user orbit)
        self.rot_y = 45.0  # yaw (user orbit)
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._extent = 100.0  # bounding sphere radius

        # Display mode
        self._mode_idx = 0  # starts on "shaded"

    @property
    def mode(self) -> str:
        return self.MODES[self._mode_idx]

    def cycle_mode(self) -> str:
        """Advance to the next display mode and return its name."""
        self._mode_idx = (self._mode_idx + 1) % len(self.MODES)
        return self.mode

    def set_mesh(self, verts, tris, normals):
        """Update the displayed mesh."""
        self.verts = verts
        self.tris = tris
        self.normals = normals

        # Compute per-vertex normals by averaging face normals
        self.vert_normals = np.zeros_like(verts)
        for i in range(3):
            np.add.at(self.vert_normals, tris[:, i], normals)
        norms = np.linalg.norm(self.vert_normals, axis=1, keepdims=True)
        norms[norms < 1e-10] = 1.0
        self.vert_normals = (self.vert_normals / norms).astype(np.float32)

        self._extent = max(np.linalg.norm(verts, axis=1).max(), 1.0)

    def paint(self, width: int, height: int):
        """Render the current mesh with OpenGL fixed-function pipeline."""
        from OpenGL import GL

        GL.glViewport(0, 0, width, height)
        GL.glClearColor(1.0, 1.0, 1.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        # -- Studio backdrop (radial vignette, drawn in 2D, no depth) --
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_LIGHTING)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

        # Build a radial gradient: bright center, darker edges — like a
        # softbox-lit studio backdrop. Uses a triangle fan from center.
        cx, cy = 0.0, 0.05  # slightly above center
        # Center color (bright warm white)
        cr, cg, cb = 0.95, 0.95, 0.96
        # Edge color (soft gray, like shadow falloff on a curved backdrop)
        er, eg, eb = 0.72, 0.73, 0.76
        segments = 64
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glColor3f(cr, cg, cb)
        GL.glVertex2f(cx, cy)
        GL.glColor3f(er, eg, eb)
        for i in range(segments + 1):
            angle = 2.0 * math.pi * i / segments
            # Stretch to fill corners (ellipse > 1.0 radius)
            GL.glVertex2f(cx + math.cos(angle) * 1.8, cy + math.sin(angle) * 1.8)
        GL.glEnd()

        # -- 3D scene setup --
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT)

        # Projection
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        aspect = width / max(height, 1)
        r = self._extent * 1.5 / self.zoom
        GL.glOrtho(-r * aspect, r * aspect, -r, r, -r * 10, r * 10)

        # Model-view
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glTranslatef(self.pan_x, self.pan_y, 0.0)
        GL.glRotatef(self.rot_x, 1, 0, 0)
        GL.glRotatef(self.rot_y, 0, 1, 0)
        GL.glRotatef(-90.0, 1, 0, 0)  # Z-up: rotate so +Z points screen-up

        if self.verts is None or self.tris is None:
            return

        flat_tris = self.tris.astype(np.uint32).flatten()

        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)
        GL.glEnableClientState(GL.GL_NORMAL_ARRAY)
        GL.glVertexPointer(3, GL.GL_FLOAT, 0, self.verts)
        GL.glNormalPointer(GL.GL_FLOAT, 0, self.vert_normals)

        mode = self.mode

        # -- Shaded pass --
        if mode in ("shaded", "shaded+wireframe"):
            GL.glEnable(GL.GL_LIGHTING)
            GL.glLightModelfv(GL.GL_LIGHT_MODEL_AMBIENT, [0.15, 0.15, 0.17, 1.0])
            GL.glLightModeli(GL.GL_LIGHT_MODEL_TWO_SIDE, GL.GL_FALSE)

            # Key light — upper-right, warm white
            GL.glEnable(GL.GL_LIGHT0)
            GL.glLightfv(GL.GL_LIGHT0, GL.GL_POSITION, [1.0, 2.0, 2.5, 0.0])
            GL.glLightfv(GL.GL_LIGHT0, GL.GL_DIFFUSE, [0.7, 0.7, 0.68, 1.0])
            GL.glLightfv(GL.GL_LIGHT0, GL.GL_SPECULAR, [0.9, 0.9, 0.85, 1.0])
            GL.glLightfv(GL.GL_LIGHT0, GL.GL_AMBIENT, [0.0, 0.0, 0.0, 1.0])

            # Fill light — lower-left, cool and softer
            GL.glEnable(GL.GL_LIGHT1)
            GL.glLightfv(GL.GL_LIGHT1, GL.GL_POSITION, [-1.5, -1.0, 1.0, 0.0])
            GL.glLightfv(GL.GL_LIGHT1, GL.GL_DIFFUSE, [0.28, 0.30, 0.35, 1.0])
            GL.glLightfv(GL.GL_LIGHT1, GL.GL_SPECULAR, [0.0, 0.0, 0.0, 1.0])
            GL.glLightfv(GL.GL_LIGHT1, GL.GL_AMBIENT, [0.0, 0.0, 0.0, 1.0])

            # Rim light — behind, subtle edge definition
            GL.glEnable(GL.GL_LIGHT2)
            GL.glLightfv(GL.GL_LIGHT2, GL.GL_POSITION, [0.0, 0.5, -2.0, 0.0])
            GL.glLightfv(GL.GL_LIGHT2, GL.GL_DIFFUSE, [0.2, 0.2, 0.22, 1.0])
            GL.glLightfv(GL.GL_LIGHT2, GL.GL_SPECULAR, [0.3, 0.3, 0.3, 1.0])
            GL.glLightfv(GL.GL_LIGHT2, GL.GL_AMBIENT, [0.0, 0.0, 0.0, 1.0])

            # Material — clean white with specular highlight
            GL.glMaterialfv(
                GL.GL_FRONT_AND_BACK, GL.GL_AMBIENT, [0.35, 0.35, 0.35, 1.0]
            )
            GL.glMaterialfv(
                GL.GL_FRONT_AND_BACK, GL.GL_DIFFUSE, [0.88, 0.88, 0.88, 1.0]
            )
            GL.glMaterialfv(GL.GL_FRONT_AND_BACK, GL.GL_SPECULAR, [0.7, 0.7, 0.7, 1.0])
            GL.glMaterialf(GL.GL_FRONT_AND_BACK, GL.GL_SHININESS, 50.0)

            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)
            GL.glDrawElements(
                GL.GL_TRIANGLES, len(flat_tris), GL.GL_UNSIGNED_INT, flat_tris
            )
            GL.glDisable(GL.GL_LIGHT0)
            GL.glDisable(GL.GL_LIGHT1)
            GL.glDisable(GL.GL_LIGHT2)
            GL.glDisable(GL.GL_LIGHTING)

        # -- Wireframe pass --
        if mode in ("wireframe", "shaded+wireframe"):
            GL.glDisable(GL.GL_LIGHTING)
            if mode == "shaded+wireframe":
                # Offset filled polygons back so wireframe draws on top
                GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
                GL.glPolygonOffset(1.0, 1.0)
                GL.glColor3f(0.15, 0.15, 0.15)
            else:
                GL.glColor3f(0.2, 0.2, 0.2)
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
            GL.glLineWidth(1.0)
            GL.glDrawElements(
                GL.GL_TRIANGLES, len(flat_tris), GL.GL_UNSIGNED_INT, flat_tris
            )
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)
            GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)

        GL.glDisableClientState(GL.GL_VERTEX_ARRAY)
        GL.glDisableClientState(GL.GL_NORMAL_ARRAY)

        # -- Axis triad (bottom-left corner, fixed screen position) --
        GL.glDisable(GL.GL_LIGHTING)
        GL.glDisable(GL.GL_DEPTH_TEST)

        # Small viewport in the bottom-left corner
        triad_size = min(width, height) // 6
        margin = 10
        GL.glViewport(margin, margin, triad_size, triad_size)

        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glOrtho(-1.6, 1.6, -1.6, 1.6, -10, 10)

        # Apply same rotation as the model so axes track the view
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glRotatef(self.rot_x, 1, 0, 0)
        GL.glRotatef(self.rot_y, 0, 1, 0)
        GL.glRotatef(-90.0, 1, 0, 0)  # Z-up

        axis_len = 1.0
        GL.glLineWidth(2.5)
        GL.glBegin(GL.GL_LINES)
        # X — red
        GL.glColor3f(0.9, 0.2, 0.2)
        GL.glVertex3f(0, 0, 0)
        GL.glVertex3f(axis_len, 0, 0)
        # Y — green
        GL.glColor3f(0.2, 0.75, 0.2)
        GL.glVertex3f(0, 0, 0)
        GL.glVertex3f(0, axis_len, 0)
        # Z — blue
        GL.glColor3f(0.2, 0.4, 0.9)
        GL.glVertex3f(0, 0, 0)
        GL.glVertex3f(0, 0, axis_len)
        GL.glEnd()

        # Restore full viewport
        GL.glViewport(0, 0, width, height)
        GL.glEnable(GL.GL_DEPTH_TEST)

        # Compute screen positions of axis tips for QPainter labels
        rad_x = math.radians(self.rot_x)
        rad_y = math.radians(self.rot_y)
        cos_x, sin_x = math.cos(rad_x), math.sin(rad_x)
        cos_y, sin_y = math.cos(rad_y), math.sin(rad_y)

        def _project_axis(ax, ay, az):
            """Rotate axis tip by view angles and map to triad viewport pixels."""
            # Z-up base rotation (-90° around X): x'=x, y'=z, z'=-y
            bx, by, bz = ax, az, -ay
            # Y-rotation then X-rotation (matches GL calls)
            rx = bx * cos_y + bz * sin_y
            ry = by
            rz = -bx * sin_y + bz * cos_y
            ry2 = ry * cos_x - rz * sin_x
            rz2 = ry * sin_x + rz * cos_x
            # Map from [-1.6, 1.6] clip space to pixel coords in triad viewport
            px = margin + (rx / 1.6 + 1.0) * 0.5 * triad_size
            # Qt Y is flipped vs OpenGL
            py = height - margin - (ry2 / 1.6 + 1.0) * 0.5 * triad_size
            return int(px), int(py)

        label_len = 1.25  # slightly past the axis line end
        self._axis_labels = [
            ("X", (0.9, 0.2, 0.2), _project_axis(label_len, 0, 0)),
            ("Y", (0.2, 0.75, 0.2), _project_axis(0, label_len, 0)),
            ("Z", (0.2, 0.4, 0.9), _project_axis(0, 0, label_len)),
        ]


# ---- Qt application ----


def _build_app(step_path: Path):
    """Create and return the Qt application, window, and GL widget."""
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QVBoxLayout,
        QHBoxLayout,
        QWidget,
        QLabel,
        QPushButton,
    )
    from PySide6.QtOpenGLWidgets import QOpenGLWidget
    from PySide6.QtCore import Qt, QTimer, QPoint
    from PySide6.QtGui import QSurfaceFormat, QPainter, QFont, QColor

    gl_viewer = GLViewer()

    class MeshGLWidget(QOpenGLWidget):
        def __init__(self, parent=None):
            fmt = QSurfaceFormat()
            fmt.setDepthBufferSize(24)
            fmt.setSamples(4)
            super().__init__(parent)
            self.setFormat(fmt)
            self._last_pos = QPoint()
            self._right_last_pos = QPoint()

        def initializeGL(self):
            from OpenGL import GL

            GL.glEnable(GL.GL_MULTISAMPLE)

        def paintGL(self):
            gl_viewer.paint(self.width(), self.height())

            # Draw axis labels with QPainter overlay
            if hasattr(gl_viewer, "_axis_labels"):
                painter = QPainter(self)
                font = QFont("sans-serif", 11, QFont.Bold)
                painter.setFont(font)
                for label, (r, g, b), (px, py) in gl_viewer._axis_labels:
                    painter.setPen(QColor(int(r * 255), int(g * 255), int(b * 255)))
                    painter.drawText(px - 5, py + 5, label)
                painter.end()

        def mousePressEvent(self, event):
            if event.button() == Qt.LeftButton:
                self._last_pos = event.position().toPoint()
            elif event.button() == Qt.RightButton:
                self._right_last_pos = event.position().toPoint()

        def mouseMoveEvent(self, event):
            pos = event.position().toPoint()
            if event.buttons() & Qt.LeftButton:
                dx = pos.x() - self._last_pos.x()
                dy = pos.y() - self._last_pos.y()
                gl_viewer.rot_y += dx * 0.5
                gl_viewer.rot_x += dy * 0.5
                self._last_pos = pos
                self.update()
            if event.buttons() & Qt.RightButton:
                dx = pos.x() - self._right_last_pos.x()
                dy = pos.y() - self._right_last_pos.y()
                scale = gl_viewer._extent * 2.0 / max(self.height(), 1) / gl_viewer.zoom
                gl_viewer.pan_x += dx * scale
                gl_viewer.pan_y -= dy * scale
                self._right_last_pos = pos
                self.update()

        def wheelEvent(self, event):
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9
            gl_viewer.zoom = max(0.01, gl_viewer.zoom * factor)
            self.update()

    qapp = QApplication.instance() or QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle(f"RocketSmith Viewer — {step_path.name}")
    window.resize(1024, 768)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    gl_widget = MeshGLWidget(central)
    layout.addWidget(gl_widget, stretch=1)

    # ---- Bottom toolbar ----
    toolbar = QWidget()
    toolbar.setStyleSheet("background: #23272e;")
    tb_layout = QHBoxLayout(toolbar)
    tb_layout.setContentsMargins(8, 4, 8, 4)
    tb_layout.setSpacing(8)

    status = QLabel(f"  {step_path}")
    status.setStyleSheet("color: #aab2bf; font-size: 12px;")
    tb_layout.addWidget(status, stretch=1)

    mode_btn = QPushButton("Shaded")
    mode_btn.setFixedWidth(140)
    mode_btn.setStyleSheet(
        "QPushButton { background: #3b4048; color: #dcdfe4; border: 1px solid #555;"
        " border-radius: 3px; padding: 4px 12px; font-size: 12px; }"
        "QPushButton:hover { background: #4b5058; }"
    )
    LABELS = {
        "shaded": "Shaded",
        "wireframe": "Wireframe",
        "shaded+wireframe": "Shaded + Wire",
    }

    def toggle_mode():
        new_mode = gl_viewer.cycle_mode()
        mode_btn.setText(LABELS[new_mode])
        gl_widget.update()

    mode_btn.clicked.connect(toggle_mode)
    tb_layout.addWidget(mode_btn)

    layout.addWidget(toolbar)

    window.setCentralWidget(central)

    # ---- File watcher ----
    last_mtime = [0.0]

    def reload_mesh():
        if not step_path.exists():
            status.setText(f"  Waiting for {step_path.name}...")
            return
        try:
            verts, tris, normals = _load_mesh(step_path)
        except Exception as e:
            status.setText(f"  Load error: {e}")
            return
        gl_viewer.set_mesh(verts, tris, normals)
        gl_widget.update()
        last_mtime[0] = step_path.stat().st_mtime
        ts = time.strftime("%H:%M:%S")
        status.setText(
            f"  {step_path.name}  |  " f"{len(tris):,} triangles  |  " f"reloaded {ts}"
        )

    def check_file():
        if not step_path.exists():
            return
        try:
            mt = step_path.stat().st_mtime
        except OSError:
            return
        if mt > last_mtime[0] + DEBOUNCE_SEC:
            reload_mesh()

    timer = QTimer()
    timer.setInterval(POLL_INTERVAL_MS)
    timer.timeout.connect(check_file)
    timer.start()

    # Initial load
    reload_mesh()

    window.show()
    return qapp, window, timer


def launch_viewer(step_path: Path) -> None:
    """Entry point — create and run the viewer (blocks until window closed)."""
    step_path = step_path.resolve()
    qapp, window, timer = _build_app(step_path)
    qapp.exec()


def main():
    """CLI entry point for the viewer subprocess."""
    if len(sys.argv) < 2:
        print("Usage: python -m rocketsmith.build123d.viewer.viewer <step_file>")
        sys.exit(1)
    launch_viewer(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
