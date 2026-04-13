"""Constants and core types for ASCII rendering."""

import shutil

BODY_TYPES = {"NoseCone", "BodyTube", "Transition"}
INTERNAL_TYPES = {
    "InnerTube",
    "TubeCoupler",
    "Parachute",
    "ShockCord",
    "Streamer",
    "MassComponent",
}
FIN_TYPES = {"TrapezoidFinSet", "EllipticalFinSet", "FreeformFinSet"}

# Radius change smaller than this fraction of max_outer_r is treated as flat.
SLOPE_THRESHOLD = 0.4


def fmt_mm(m: float) -> str:
    """Format meters to mm string."""
    return f"{round(m * 1000)}mm"


def get_default_width() -> int:
    """Return 90% of detected terminal width or 120 chars."""
    terminal_width = shutil.get_terminal_size((120, 40)).columns
    return max(40, int(terminal_width * 0.9))
