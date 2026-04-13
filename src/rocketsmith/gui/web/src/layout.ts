/** Canonical project directory layout — mirrors gui/layout.py. */

export const OPENROCKET_DIR = "openrocket";

// GUI directory — holds the frontend bundle, data snapshot, and derived data.
export const GUI_DIR = "gui";
export const GUI_ASSETS_DIR = "gui/assets";
export const TREE_FILE = "gui/component_tree.json";
export const ASSEMBLY_FILE = "gui/assembly.json";

// Per-part JSON metadata directory.
export const PARTS_DIR = "gui/parts";

// Preview / visualization assets (under gui/assets/).
export const STL_DIR = "gui/assets/stl";
export const PNG_DIR = "gui/assets/png";
export const GIF_DIR = "gui/assets/gif";
export const TXT_DIR = "gui/assets/txt";
export const PROGRESS_DIR = "gui/progress";

// CAD directories — scripts and geometry.
export const CADSMITH_DIR = "cadsmith";
export const CADSMITH_SOURCE_DIR = "cadsmith/source";
export const STEP_DIR = "cadsmith/step";

// Slicer directories — configs and output.
export const PRUSASLICER_DIR = "prusaslicer";
export const PRUSASLICER_CONFIG_DIR = "prusaslicer/config";
export const GCODE_DIR = "prusaslicer/gcode";
