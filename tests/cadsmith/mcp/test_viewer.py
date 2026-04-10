"""Tests for the cadsmith_viewer MCP tool."""

import os
import signal

import pytest
from mcp.server.fastmcp import FastMCP

from rocketsmith.cadsmith.mcp.viewer import register_cadsmith_viewer


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-cadsmith")
    register_cadsmith_viewer(app)
    return app


@pytest.fixture
def tool(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    return tools[0]


@pytest.fixture
def sample_step():
    """Path to a known-good STEP file in the test data."""
    from pathlib import Path

    p = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "src"
        / "rocketsmith"
        / "data"
        / "part"
        / "lower_airframe.step"
    )
    if not p.exists():
        pytest.skip("Sample STEP file not available")
    return p


# ── Registration ─────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "cadsmith_viewer"


# ── Error cases ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_missing_parent_dir_returns_error(tool, tmp_path):
    result = await tool.fn(
        step_file_path=tmp_path / "nonexistent_dir" / "part.step",
    )
    assert result.success is False
    assert result.error_code == "DIR_NOT_FOUND"


@pytest.mark.anyio
async def test_file_not_required_to_exist(tool, tmp_path):
    """The viewer should launch even if the STEP file doesn't exist yet
    (it waits for the file to appear)."""
    result = await tool.fn(
        step_file_path=tmp_path / "future_part.step",
    )
    assert result.success is True
    assert result.data["pid"] > 0

    # Clean up the spawned process
    os.kill(result.data["pid"], signal.SIGTERM)


# ── Success cases ────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_launches_viewer_process(tool, sample_step):
    result = await tool.fn(step_file_path=sample_step)

    assert result.success is True
    assert "pid" in result.data
    assert result.data["pid"] > 0
    assert result.data["step_file_path"] == str(sample_step)
    assert "message" in result.data

    # Clean up the spawned process
    os.kill(result.data["pid"], signal.SIGTERM)


@pytest.mark.anyio
async def test_viewer_process_is_running(tool, sample_step):
    result = await tool.fn(step_file_path=sample_step)
    pid = result.data["pid"]

    # Process should be alive (os.kill with signal 0 checks existence)
    try:
        os.kill(pid, 0)
        alive = True
    except OSError:
        alive = False

    assert alive

    # Clean up
    os.kill(pid, signal.SIGTERM)


@pytest.mark.anyio
async def test_returns_absolute_path(tool, tmp_path):
    result = await tool.fn(step_file_path=tmp_path / "part.step")

    assert result.success is True
    assert os.path.isabs(result.data["step_file_path"])

    os.kill(result.data["pid"], signal.SIGTERM)
