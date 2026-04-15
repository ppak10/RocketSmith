"""Canonical project directory layout.

Tools use these as default output subdirectories.  Every path is relative
to the project root.  Users can override individual tool outputs with
an explicit ``out_path`` parameter.
"""

OPENROCKET_DIR = "openrocket"
FLIGHTS_DIR = "openrocket/flights"

# GUI directory — holds the frontend bundle, data snapshot, and derived data.
GUI_DIR = "gui"
GUI_ASSETS_DIR = "gui/assets"
TREE_FILE = "gui/component_tree.json"
ASSEMBLY_FILE = "gui/assembly.json"
GUI_PID_FILE = "gui/.gui.pid"
GUI_MAIN_JS = "gui/main.js"
GUI_DATA_JS = "gui/data.js"

# Per-part JSON metadata directory.
PARTS_DIR = "gui/parts"

# Preview / visualization assets (under gui/assets/).
STL_DIR = "gui/assets/stl"
PNG_DIR = "gui/assets/png"
GIF_DIR = "gui/assets/gif"
TXT_DIR = "gui/assets/txt"
PROGRESS_DIR = "gui/progress"

# Logs directory for agentic session logs.
LOGS_DIR = "gui/logs"

# CAD directories — scripts and geometry.
CADSMITH_DIR = "cadsmith"
CADSMITH_SOURCE_DIR = "cadsmith/source"
STEP_DIR = "cadsmith/step"

# Slicer directories — configs and output.
PRUSASLICER_DIR = "prusaslicer"
PRUSASLICER_CONFIG_DIR = "prusaslicer/configs"
GCODE_DIR = "prusaslicer/gcode"
