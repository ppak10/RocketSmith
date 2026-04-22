import atexit
import os
from pathlib import Path

from rocketsmith.mcp.types import T, ToolError, ToolSuccess

_ROCKETSMITH_DIR = Path.home() / ".rocketsmith"
_atexit_registered = False


def _pid_file() -> Path:
    return _ROCKETSMITH_DIR / f"project_{os.getpid()}"


def _cleanup_pid_file() -> None:
    try:
        _pid_file().unlink(missing_ok=True)
    except Exception:
        pass


def safe_resolve(path: Path) -> Path:
    """Resolve a path to absolute form without raising on Windows.

    ``Path.resolve()`` on Windows calls ``GetFinalPathNameByHandle``, which can
    raise ``OSError: [WinError 87] The parameter is incorrect`` for certain path
    types (long paths, paths with trailing characters, non-existent roots).
    ``os.path.abspath`` performs the same ``..``-collapse and absolutisation
    without that API call and is safe on all platforms.
    """
    try:
        return path.resolve()
    except OSError:
        return Path(os.path.abspath(path))


def set_project_dir(path: Path) -> None:
    """Persist the project directory for this MCP server process (PID-scoped).

    Written to ``~/.rocketsmith/project_<pid>`` so concurrent sessions each
    maintain their own project context without clobbering each other.
    Automatically cleaned up when the process exits.
    """
    global _atexit_registered
    _ROCKETSMITH_DIR.mkdir(parents=True, exist_ok=True)
    _pid_file().write_text(str(safe_resolve(path)))
    if not _atexit_registered:
        atexit.register(_cleanup_pid_file)
        _atexit_registered = True


def get_project_dir() -> Path:
    """Return the user's project directory for use as a base for relative paths.

    Resolution order:

    1. ``ROCKETSMITH_PROJECT_DIR`` environment variable — set by the extension
       manifest (e.g. gemini-extension.json) to the user's session cwd.
    2. ``~/.rocketsmith/project_<pid>`` — written by ``rocketsmith_setup``
       when the agent passes ``project_dir`` at session start. PID-scoped so
       concurrent sessions don't clobber each other.
    3. ``Path.cwd()`` as a last resort.

    Tools that accept a user-supplied path should call ``resolve_path``, which
    uses this function as the base for any relative path.
    """
    # 1. Env var (Gemini CLI sets this via ${workspacePath} substitution).
    env_dir = os.environ.get("ROCKETSMITH_PROJECT_DIR")
    # Guard against unresolved client-side substitutions like ``${cwd}``.
    if env_dir and "${" not in env_dir:
        resolved = Path(env_dir).expanduser().resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved

    # 2. PID-scoped file written by rocketsmith_setup.
    pid_file = _pid_file()
    if pid_file.exists():
        try:
            p = Path(pid_file.read_text().strip()).resolve()
            if p.exists() and p.is_dir():
                return p
        except Exception:
            pass

    # 3. CWD fallback.
    return Path.cwd().resolve()


# Convenience function to create error responses
def tool_error(message: str, code: str, **details) -> ToolError:
    """Create a standardized tool error response."""
    return ToolError(error=message, error_code=code, details=details)


# Convenience function to create success responses
def tool_success(data: T) -> ToolSuccess[T]:
    """Create a standardized tool success response."""
    return ToolSuccess(data=data)


def resolve_path(path: Path | str, must_exist: bool = False) -> Path:
    """Normalize a user-supplied path for use inside an MCP tool.

    - Expands ``~`` to the user's home directory.
    - Resolves relative paths against the project directory (see
      ``get_project_dir``), which respects ``ROCKETSMITH_PROJECT_DIR`` if set.
    - Returns an absolute path without requiring the file to exist
      (unlike ``Path.resolve(strict=True)``).

    Args:
        path: A path-like value, possibly relative or containing ``~``.
        must_exist: When True, raise ``FileNotFoundError`` if the
            resolved path does not exist on disk.

    Returns:
        An absolute ``Path``.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = get_project_dir() / p
    # ``resolve()`` without ``strict`` collapses ``..`` segments and symlinks
    # without requiring the path to exist.
    p = p.resolve()
    if must_exist and not p.exists():
        raise FileNotFoundError(str(p))
    return p
