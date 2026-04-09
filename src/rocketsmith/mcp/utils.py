from pathlib import Path

from rocketsmith.mcp.types import T, ToolError, ToolSuccess


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
    - Resolves relative paths against the current working directory.
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
        p = Path.cwd() / p
    # ``resolve()`` without ``strict`` collapses ``..`` segments and symlinks
    # without requiring the path to exist.
    p = p.resolve()
    if must_exist and not p.exists():
        raise FileNotFoundError(str(p))
    return p
