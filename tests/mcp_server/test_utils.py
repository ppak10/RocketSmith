"""Tests for rocketsmith.mcp.utils."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from rocketsmith.mcp.utils import (
    get_project_dir,
    resolve_path,
    safe_resolve,
    set_project_dir,
    tool_error,
    tool_success,
)
from rocketsmith.mcp.types import ToolError, ToolSuccess


# ── safe_resolve ──────────────────────────────────────────────────────────────


def test_safe_resolve_returns_absolute_path(tmp_path):
    p = tmp_path / "subdir"
    p.mkdir()
    result = safe_resolve(p)
    assert result.is_absolute()


def test_safe_resolve_collapses_dotdot(tmp_path):
    p = tmp_path / "a" / ".." / "b"
    result = safe_resolve(p)
    assert ".." not in result.parts


def test_safe_resolve_falls_back_on_oserror(tmp_path):
    p = tmp_path / "some" / "path"
    with patch.object(Path, "resolve", side_effect=OSError("WinError 87")):
        result = safe_resolve(p)
    assert result.is_absolute()
    assert isinstance(result, Path)


def test_safe_resolve_fallback_matches_abspath(tmp_path):
    p = tmp_path / "some" / "path"
    expected = Path(os.path.abspath(p))
    with patch.object(Path, "resolve", side_effect=OSError):
        result = safe_resolve(p)
    assert result == expected


# ── set_project_dir / get_project_dir ─────────────────────────────────────────


def test_set_and_get_project_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("ROCKETSMITH_PROJECT_DIR", raising=False)

    import rocketsmith.mcp.utils as utils_mod

    rocketsmith_dir = tmp_path / ".rocketsmith"
    monkeypatch.setattr(utils_mod, "_ROCKETSMITH_DIR", rocketsmith_dir)
    monkeypatch.setattr(utils_mod, "_atexit_registered", False)

    project = tmp_path / "myproject"
    project.mkdir()

    set_project_dir(project)

    result = get_project_dir()
    assert result == project.resolve()


def test_set_project_dir_creates_rocketsmith_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("ROCKETSMITH_PROJECT_DIR", raising=False)

    import rocketsmith.mcp.utils as utils_mod

    rocketsmith_dir = tmp_path / ".rocketsmith"
    monkeypatch.setattr(utils_mod, "_ROCKETSMITH_DIR", rocketsmith_dir)
    monkeypatch.setattr(utils_mod, "_atexit_registered", False)

    project = tmp_path / "proj"
    project.mkdir()

    assert not rocketsmith_dir.exists()
    set_project_dir(project)
    assert rocketsmith_dir.exists()


def test_get_project_dir_prefers_env_var(tmp_path, monkeypatch):
    env_dir = tmp_path / "env_project"
    env_dir.mkdir()
    monkeypatch.setenv("ROCKETSMITH_PROJECT_DIR", str(env_dir))

    result = get_project_dir()
    assert result == env_dir.resolve()


def test_get_project_dir_ignores_unresolved_env_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKETSMITH_PROJECT_DIR", "${cwd}/project")

    import rocketsmith.mcp.utils as utils_mod

    rocketsmith_dir = tmp_path / ".rocketsmith"
    monkeypatch.setattr(utils_mod, "_ROCKETSMITH_DIR", rocketsmith_dir)
    # No pid file written → falls back to cwd
    result = get_project_dir()
    assert "${" not in str(result)


def test_get_project_dir_falls_back_to_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("ROCKETSMITH_PROJECT_DIR", raising=False)

    import rocketsmith.mcp.utils as utils_mod

    # Point to a dir with no pid file
    rocketsmith_dir = tmp_path / ".rocketsmith_empty"
    monkeypatch.setattr(utils_mod, "_ROCKETSMITH_DIR", rocketsmith_dir)

    result = get_project_dir()
    assert result == Path.cwd().resolve()


def test_get_project_dir_ignores_nonexistent_env_path(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKETSMITH_PROJECT_DIR", str(tmp_path / "does_not_exist"))

    import rocketsmith.mcp.utils as utils_mod

    rocketsmith_dir = tmp_path / ".rocketsmith"
    monkeypatch.setattr(utils_mod, "_ROCKETSMITH_DIR", rocketsmith_dir)

    # Falls through to cwd since the env path doesn't exist
    result = get_project_dir()
    assert result == Path.cwd().resolve()


# ── tool_error / tool_success ─────────────────────────────────────────────────


def test_tool_error_returns_tool_error_model():
    result = tool_error("something went wrong", "ERR_001", detail="value")
    assert isinstance(result, ToolError)
    assert result.success is False
    assert result.error == "something went wrong"
    assert result.error_code == "ERR_001"
    assert result.details["detail"] == "value"


def test_tool_error_no_details():
    result = tool_error("oops", "ERR_002")
    assert result.details == {}


def test_tool_success_returns_tool_success_model():
    result = tool_success({"key": "value"})
    assert isinstance(result, ToolSuccess)
    assert result.success is True
    assert result.data == {"key": "value"}


def test_tool_success_with_primitive():
    result = tool_success(42)
    assert result.data == 42


# ── resolve_path ──────────────────────────────────────────────────────────────


def test_resolve_path_absolute_returned_unchanged(tmp_path):
    p = tmp_path / "file.txt"
    p.touch()
    result = resolve_path(p)
    assert result == p.resolve()


def test_resolve_path_relative_resolved_against_project_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKETSMITH_PROJECT_DIR", str(tmp_path))
    result = resolve_path("subdir/file.txt")
    assert result == (tmp_path / "subdir" / "file.txt").resolve()


def test_resolve_path_expands_tilde(monkeypatch):
    result = resolve_path("~/somefile.txt")
    assert not str(result).startswith("~")
    assert result.is_absolute()


def test_resolve_path_must_exist_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKETSMITH_PROJECT_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        resolve_path("nonexistent.txt", must_exist=True)


def test_resolve_path_must_exist_passes_when_present(tmp_path, monkeypatch):
    monkeypatch.setenv("ROCKETSMITH_PROJECT_DIR", str(tmp_path))
    f = tmp_path / "present.txt"
    f.touch()
    result = resolve_path("present.txt", must_exist=True)
    assert result == f.resolve()
