"""Tests for the gui_server MCP tool."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
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


# ── Start: error cases ───────────────────────────────────────────────────────


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


# ── Start: success ───────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_launches_server(tool, tmp_path, monkeypatch):
    mock_outcome = {
        "pid": 12345,
        "server_url": "http://127.0.0.1:24880",
        "reused": False,
        "error": None,
    }
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.start_gui_server",
        lambda resolved, host, port: mock_outcome,
    )

    result = await tool.fn(action="start", project_dir=str(tmp_path))
    assert result.success is True
    assert result.data["pid"] == 12345
    assert result.data["server_url"] == "http://127.0.0.1:24880"
    assert result.data["reused"] is False


@pytest.mark.anyio
async def test_start_reuses_existing(tool, tmp_path, monkeypatch):
    mock_outcome = {
        "pid": 9999,
        "server_url": "http://127.0.0.1:24880",
        "reused": True,
        "error": None,
    }
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.start_gui_server",
        lambda resolved, host, port: mock_outcome,
    )

    result = await tool.fn(action="start", project_dir=str(tmp_path))
    assert result.success is True
    assert result.data["reused"] is True


@pytest.mark.anyio
async def test_start_propagates_lifecycle_error(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "rocketsmith.gui.mcp.server.start_gui_server",
        lambda resolved, host, port: {
            "pid": None,
            "server_url": None,
            "reused": False,
            "error": "GUI build not found.",
        },
    )

    result = await tool.fn(action="start", project_dir=str(tmp_path))
    assert result.success is False
    assert result.error_code == "SERVER_LAUNCH_FAILED"


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
