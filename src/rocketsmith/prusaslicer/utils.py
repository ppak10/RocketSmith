import shutil
import sys

from pathlib import Path


# Known PrusaSlicer executable locations per platform
_SEARCH_PATHS = {
    "darwin": [
        Path("/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"),
        Path.home() / "Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer",
    ],
    "linux": [
        Path("/usr/bin/prusa-slicer"),
        Path("/usr/local/bin/prusa-slicer"),
        Path.home() / ".local/bin/prusa-slicer",
        Path("/opt/prusa-slicer/prusa-slicer"),
    ],
    "win32": [
        Path("C:/Program Files/Prusa3D/PrusaSlicer/prusa-slicer-console.exe"),
        Path("C:/Program Files (x86)/Prusa3D/PrusaSlicer/prusa-slicer-console.exe"),
        Path.home() / "AppData/Local/Programs/Prusa3D/PrusaSlicer/prusa-slicer-console.exe",
    ],
}

# CLI binary names to try with shutil.which
_WHICH_NAMES = {
    "darwin": ["PrusaSlicer", "prusa-slicer"],
    "linux":  ["prusa-slicer", "PrusaSlicer"],
    "win32":  ["prusa-slicer-console", "prusa-slicer", "PrusaSlicer"],
}


def get_prusaslicer_path(hint: Path | None = None) -> Path:
    """
    Resolve the path to the PrusaSlicer executable.

    Checks in order:
      1. The provided hint path (if given)
      2. The PRUSASLICER_PATH environment variable
      3. PATH (via shutil.which)
      4. Common installation locations for the current platform

    Args:
        hint: Optional explicit path to the PrusaSlicer executable.

    Returns:
        Path to the PrusaSlicer executable.

    Raises:
        FileNotFoundError: If no PrusaSlicer executable can be located.
    """
    import os

    platform = sys.platform if sys.platform in _SEARCH_PATHS else "linux"

    # 1. Explicit hint
    if hint is not None:
        hint = Path(hint)
        if hint.is_file():
            return hint

    # 2. Environment variable
    env_path = os.environ.get("PRUSASLICER_PATH")
    if env_path:
        env = Path(env_path)
        if env.is_file():
            return env

    # 3. PATH lookup
    for name in _WHICH_NAMES.get(platform, []):
        found = shutil.which(name)
        if found:
            return Path(found)

    # 4. Platform-specific known paths
    for candidate in _SEARCH_PATHS.get(platform, []):
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "PrusaSlicer executable not found. Install PrusaSlicer or set the "
        "PRUSASLICER_PATH environment variable to its path."
    )
