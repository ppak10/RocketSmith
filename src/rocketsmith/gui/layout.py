"""Canonical project directory layout.

Tools use these as default output subdirectories.  Every path is relative
to the project root.  Users can override individual tool outputs with
an explicit ``out_path`` parameter.
"""

OPENROCKET_DIR = "openrocket"
GCODE_DIR = "gcode"
MANIFEST_FILE = "parts_manifest.json"

# Parts directory with format-specific subdirectories.
PARTS_DIR = "parts"
PARTS_CADSMITH_DIR = "parts/cadsmith"
PARTS_STEP_DIR = "parts/step"
PARTS_STL_DIR = "parts/stl"
PARTS_GIF_DIR = "parts/gif"
PARTS_PNG_DIR = "parts/png"
