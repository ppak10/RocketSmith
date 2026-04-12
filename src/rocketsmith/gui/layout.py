"""Canonical project directory layout.

Tools use these as default output subdirectories.  Every path is relative
to the project root.  Users can override individual tool outputs with
an explicit ``out_path`` parameter.
"""

OPENROCKET_DIR = "openrocket"
TREE_FILE = "component_tree.json"
ASSEMBLY_FILE = "assembly.json"

# Top-level format directories.
CADSMITH_DIR = "cadsmith"
STEP_DIR = "step"
STL_DIR = "stl"
GCODE_DIR = "gcode"

# Per-part JSON metadata directory.
PARTS_DIR = "parts"

# Preview format directories (top-level).
PNG_DIR = "png"
GIF_DIR = "gif"
TXT_DIR = "txt"
PROGRESS_DIR = "progress"

# Logs directory for agentic session logs.
LOGS_DIR = "logs"
