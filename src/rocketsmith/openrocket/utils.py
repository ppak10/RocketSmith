import glob as _glob
import sys

from pathlib import Path

# Bundled JVM paths relative to the app bundle root (Contents/Resources or equivalent)
# Derived from the install4j structure used by OpenRocket 23+
_BUNDLED_JVM_RELATIVE = {
    "darwin": ["jre.bundle/Contents/Home/lib/server/libjvm.dylib"],
    "linux":  ["jre/lib/server/libjvm.so"],
    "win32":  ["jre/bin/server/jvm.dll"],
}


# Known app bundle roots to search for a bundled JVM when the JAR is standalone
_BUNDLE_ROOTS = {
    "darwin": [
        Path("/Applications/OpenRocket.app/Contents/Resources"),
        Path.home() / "Applications/OpenRocket.app/Contents/Resources",
    ],
    "linux": [],
    "win32": [
        Path("C:/Program Files/OpenRocket"),
        Path("C:/Program Files (x86)/OpenRocket"),
        Path.home() / "AppData/Local/OpenRocket",
    ],
}


# Glob patterns for system-installed JVMs (last resort, no app bundle required)
_SYSTEM_JVM_GLOBS = {
    "darwin": [
        "/Library/Java/JavaVirtualMachines/*/Contents/Home/lib/server/libjvm.dylib",
        "/opt/homebrew/opt/openjdk*/libexec/openjdk.jdk/Contents/Home/lib/server/libjvm.dylib",
        "/usr/local/opt/openjdk*/libexec/openjdk.jdk/Contents/Home/lib/server/libjvm.dylib",
    ],
    "linux": [
        "/usr/lib/jvm/*/lib/server/libjvm.so",
        "/usr/lib/jvm/*/jre/lib/*/server/libjvm.so",
    ],
    "win32": [
        "C:/Program Files/Java/*/bin/server/jvm.dll",
        "C:/Program Files/Eclipse Adoptium/*/bin/server/jvm.dll",
        str(Path.home() / "AppData/Local/Programs/Eclipse Adoptium/*/bin/server/jvm.dll"),
    ],
}


# Common OpenRocket JAR installation locations per platform
_SEARCH_PATHS = {
    "darwin": [
        # Direct JAR download location (used by rocketsmith openrocket install)
        Path.home() / ".local/share/openrocket",
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
        # install4j bundled installer (winget / direct download) - OpenRocket 23+
        Path("C:/Program Files/OpenRocket/app/jar"),
        Path("C:/Program Files (x86)/OpenRocket/app/jar"),
        Path.home() / "AppData/Local/OpenRocket/app/jar",
        # Legacy locations
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


def get_openrocket_jvm(jar_path: Path) -> Path | None:
    """
    Derive the bundled JVM path from a known OpenRocket JAR path.

    For install4j bundles (Homebrew cask, winget), the JVM is shipped alongside
    the JAR inside the app bundle. Walking up from the JAR to the bundle root
    and appending the platform-specific JVM relative path locates it without
    requiring a system Java installation.

    Args:
        jar_path: Path to the OpenRocket JAR file.

    Returns:
        Path to the bundled JVM, or None if not found (e.g. bare JAR on Linux).
    """
    platform = sys.platform if sys.platform in _BUNDLED_JVM_RELATIVE else "linux"
    relatives = _BUNDLED_JVM_RELATIVE[platform]

    # Walk up the directory tree from the JAR looking for a matching JVM
    for parent in jar_path.parents:
        for relative in relatives:
            candidate = parent / relative
            if candidate.exists():
                return candidate

    # Fall back to known app bundle locations (e.g. when using a standalone JAR
    # but an OpenRocket app bundle with a bundled JRE is installed separately)
    for root in _BUNDLE_ROOTS.get(platform, []):
        for relative in relatives:
            candidate = root / relative
            if candidate.exists():
                return candidate

    # Last resort: search system-installed JVMs
    for pattern in _SYSTEM_JVM_GLOBS.get(platform, []):
        matches = sorted(_glob.glob(pattern))
        if matches:
            return Path(matches[-1])

    return None
