import pytest
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from rocketsmith.prusaslicer.mcp.slice import register_prusaslicer_slice


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-prusaslicer")
    register_prusaslicer_slice(app)
    return app


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "prusaslicer_slice"


# ── Unit tests (no PrusaSlicer required) ─────────────────────────────────────


@pytest.mark.anyio
async def test_missing_model_file_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        model_file_path=tmp_path / "nonexistent.stl",
    )
    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"


@pytest.mark.anyio
async def test_gcode_dir_not_created_when_model_missing(mcp_app, tmp_path):
    """gcode/ directory must not be created if the model file does not exist.

    Regression: previously mkdir was called before the model-existence check,
    leaving an empty prusaslicer/gcode/ directory on every failed slice attempt.
    The fix moved mkdir into the try block after the model check.
    """
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    step_dir = tmp_path / "cadsmith" / "step"
    step_dir.mkdir(parents=True)
    missing_step = step_dir / "nose_cone.step"  # intentionally not created

    result = await tool.fn(model_file_path=missing_step)

    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"

    gcode_dir = tmp_path / "prusaslicer" / "gcode"
    assert (
        not gcode_dir.exists()
    ), "gcode/ was pre-created even though the model file was missing"
