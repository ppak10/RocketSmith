"""Canonical project directory layout.

Tools use these as default output subdirectories.  Every path is relative
to the project root.  Users can override individual tool outputs with
an explicit ``out_path`` parameter.
"""

OPENROCKET_DIR = "openrocket"
TREE_FILE = "component_tree.json"
ASSEMBLY_FILE = "assembly.json"

# Parts directory with format-specific subdirectories.
PARTS_DIR = "parts"
PARTS_CADSMITH_DIR = "parts/cadsmith"
PARTS_STEP_DIR = "parts/step"
PARTS_STL_DIR = "parts/stl"
PARTS_GCODE_DIR = "parts/gcode"

# Preview directory with format-specific subdirectories.
PREVIEWS_DIR = "previews"
PREVIEWS_PNG_DIR = "previews/png"
PREVIEWS_GIF_DIR = "previews/gif"
PREVIEWS_TXT_DIR = "previews/txt"
PREVIEWS_PROGRESS_DIR = "previews/progress"
