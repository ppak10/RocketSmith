"""Tests for the gui_server MCP tool."""

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


# ── Start: deprecated ────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_returns_deprecated(tool):
    """action='start' is no longer supported; rocketsmith_setup handles it."""
    result = await tool.fn(action="start")
    assert result.success is False
    assert result.error_code == "DEPRECATED"


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
