"""Tests for the gui_server MCP tool."""

import os
import signal
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from rocketsmith.gui.mcp.server import register_gui_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-gui")
    register_gui_server(app)
    return app


@pytest.fixture
def tool(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    return tools[0]


# ── Registration ─────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "gui_server"


# ── Invalid action ───────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_invalid_action(tool):
    result = await tool.fn(action="restart")
    assert result.success is False
    assert result.error_code == "INVALID_ACTION"


# ── Start: error cases ──────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_missing_project_dir(tool):
    result = await tool.fn(action="start")
    assert result.success is False
    assert result.error_code == "MISSING_PARAMETER"


@pytest.mark.anyio
async def test_start_nonexistent_dir(tool, tmp_path):
    result = await tool.fn(action="start", project_dir=str(tmp_path / "nope"))
    assert result.success is False
    assert result.error_code == "DIR_NOT_FOUND"


@pytest.mark.anyio
async def test_start_path_is_file(tool, tmp_path):
    f = tmp_path / "not_a_dir.txt"
    f.write_text("hello")
    result = await tool.fn(action="start", project_dir=str(f))
    assert result.success is False
    assert result.error_code == "NOT_A_DIRECTORY"


# ── Start: success ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_launches_server(tool, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    # Mock GUI build directory exists
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.Path.is_dir",
        lambda p: True if "data/gui" in str(p) else os.path.isdir(str(p)),
    )
    # Mock file operations
    monkeypatch.setattr("shutil.copy2", lambda src, dst: None)
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.Path.mkdir", lambda p, **kwargs: None
    )
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.Path.write_text", lambda p, text, **kwargs: None
    )
    monkeypatch.setattr(
        "rocketsmith.gui.server.write_files_tree_snapshot", lambda p: None
    )
    monkeypatch.setattr("rocketsmith.gui.server.write_offline_data", lambda p: None)

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)

    result = await tool.fn(action="start", project_dir=str(tmp_path), port=0)

    assert result.success is True
    assert result.data["pid"] == 12345
    assert result.data["server_url"].startswith("http://127.0.0.1:")
    assert result.data["project_dir"] == str(tmp_path)
    assert len(opened) == 1


@pytest.mark.anyio
async def test_start_uses_default_port(tool, tmp_path, monkeypatch):
    monkeypatch.setattr("webbrowser.open", lambda url: None)
    # Mock port free
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server._is_port_in_use",
        lambda port, host="127.0.0.1": False,
    )
    # Mock GUI build directory exists
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.Path.is_dir",
        lambda p: True if "data/gui" in str(p) else os.path.isdir(str(p)),
    )
    # Mock file operations
    monkeypatch.setattr("shutil.copy2", lambda src, dst: None)
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.Path.mkdir", lambda p, **kwargs: None
    )
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.Path.write_text", lambda p, text, **kwargs: None
    )
    monkeypatch.setattr(
        "rocketsmith.gui.server.write_files_tree_snapshot", lambda p: None
    )
    monkeypatch.setattr("rocketsmith.gui.server.write_offline_data", lambda p: None)

    mock_proc = MagicMock()
    mock_proc.pid = 12346
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)

    result = await tool.fn(action="start", project_dir=str(tmp_path))

    assert result.success is True
    assert result.data["server_url"] == "http://127.0.0.1:24880"
    assert result.data["pid"] == 12346


# ── Stop: error cases ───────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_stop_missing_pid(tool):
    result = await tool.fn(action="stop")
    assert result.success is False
    assert result.error_code == "MISSING_PARAMETER"


@pytest.mark.anyio
async def test_stop_nonexistent_pid(tool):
    result = await tool.fn(action="stop", pid=999999999)
    assert result.success is False
    assert result.error_code == "PROCESS_NOT_FOUND"


# ── Stop: success ───────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_stop_kills_process(tool, monkeypatch):
    monkeypatch.setattr("rocketsmith.gui.mcp.server._kill_pid", lambda pid: True)

    result = await tool.fn(action="stop", pid=54321)
    assert result.success is True
    assert 54321 in result.data["killed_pids"]
