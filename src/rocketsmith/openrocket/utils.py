import sys

from pathlib import Path


# Common OpenRocket JAR installation locations per platform
_SEARCH_PATHS = {
    "darwin": [
        # Homebrew cask (install4j bundled app) - OpenRocket 23+
        Path("/Applications/OpenRocket.app/Contents/Resources/app/jar"),
        Path.home() / "Applications/OpenRocket.app/Contents/Resources/app/jar",
        # Legacy locations
        Path("/Applications/OpenRocket.app/Contents/Java"),
        Path("/Applications/OpenRocket.app/Contents/Resources/Java"),
        Path.home() / "Applications/OpenRocket.app/Contents/Java",
        Path.home() / "Applications/OpenRocket.app/Contents/Resources/Java",
    ],
    "linux": [
        Path("/usr/share/openrocket"),
        Path("/usr/local/share/openrocket"),
        Path.home() / ".local/share/openrocket",
        Path("/opt/openrocket"),
    ],
    "win32": [
        Path("C:/Program Files/OpenRocket"),
        Path("C:/Program Files (x86)/OpenRocket"),
        Path.home() / "AppData/Local/OpenRocket",
    ],
}


def get_openrocket_path(hint: Path | None = None) -> Path:
    """
    Resolve the path to the OpenRocket JAR file.

    Checks in order:
      1. The provided hint path (if given)
      2. The OPENROCKET_JAR environment variable
      3. Common installation locations for the current platform

    Args:
        hint: Optional explicit path to the OpenRocket JAR or its parent directory.

    Returns:
        Path to the OpenRocket JAR file.

    Raises:
        FileNotFoundError: If no OpenRocket JAR can be located.
    """
    import os

    candidates: list[Path] = []

    # 1. Explicit hint
    if hint is not None:
        hint = Path(hint)
        if hint.is_file():
            return hint
        if hint.is_dir():
            candidates.append(hint)

    # 2. Environment variable
    env_path = os.environ.get("OPENROCKET_JAR")
    if env_path:
        env = Path(env_path)
        if env.is_file():
            return env
        if env.is_dir():
            candidates.append(env)

    # 3. Platform-specific search paths
    platform = sys.platform if sys.platform in _SEARCH_PATHS else "linux"
    candidates.extend(_SEARCH_PATHS[platform])

    for directory in candidates:
        if not directory.is_dir():
            continue
        matches = sorted(directory.glob("OpenRocket*.jar"))
        if matches:
            return matches[-1]  # Take highest version (last alphabetically)

    raise FileNotFoundError(
        "OpenRocket JAR not found. Install OpenRocket or set the OPENROCKET_JAR "
        "environment variable to its path."
    )
