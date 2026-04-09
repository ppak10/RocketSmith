import os
from pathlib import Path

from rocketsmith.mcp.types import T, ToolError, ToolSuccess


def get_project_dir() -> Path:
    """Return the user's project directory for use as a base for relative paths.

    Resolution order:

    1. ``ROCKETSMITH_PROJECT_DIR`` environment variable — set by the extension
       manifest (e.g. gemini-extension.json) to the user's session cwd. This is
       the right answer when the MCP subprocess is spawned from a different
       cwd than the user's project (which is always the case for Gemini CLI
       extensions spawned via ``uv run --directory ${extensionPath}``).
    2. ``Path.cwd()`` as a fallback. This is correct for ad-hoc invocations
       but wrong for extension-based installs, where cwd is the extension
       directory.

    Tools that accept a user-supplied path should call ``resolve_path``, which
    uses this function as the base for any relative path. Tools that need to
    construct a default path (e.g. ``openrocket_new`` with no ``out_path``)
    should use this directly and fail loudly rather than writing to an
    extension directory.
    """
    env_dir = os.environ.get("ROCKETSMITH_PROJECT_DIR")
    # Guard against unresolved client-side substitutions. If the extension
    # manifest uses a variable like ``${cwd}`` that the client does not
    # support, the literal string arrives here unchanged — fall back to
    # ``Path.cwd()`` rather than creating files under a bogus ``${cwd}``
    # directory.
    if env_dir and "${" not in env_dir:
        resolved = Path(env_dir).expanduser().resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved
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
