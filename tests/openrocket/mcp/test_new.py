import pytest

from mcp.server.fastmcp import FastMCP
from rocketsmith.openrocket.mcp.new import register_openrocket_new


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-openrocket")
    register_openrocket_new(app)
    return app


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "openrocket_new"


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_jar_not_found_returns_error(mcp_app, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "rocketsmith.openrocket.utils.get_openrocket_path",
        lambda: (_ for _ in ()).throw(FileNotFoundError("OpenRocket not installed")),
    )
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        name="TestRocket",
        out_path=tmp_path / "test.ork",
    )

    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


@pytest.mark.anyio
async def test_creates_ork_file(mcp_app, tmp_path, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    out_path = tmp_path / "test.ork"
    result = await tool.fn(
        name="My Rocket",
        out_path=out_path,
        openrocket_path=openrocket_jar,
    )

    assert result.success is True
    assert result.data["name"] == "My Rocket"
    assert out_path.stat().st_size > 0


@pytest.mark.anyio
async def test_returns_path_in_data(mcp_app, tmp_path, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    out_path = tmp_path / "test.ork"
    result = await tool.fn(
        name="Path Test",
        out_path=out_path,
        openrocket_path=openrocket_jar,
    )

    assert result.success is True
    assert str(out_path) == result.data["path"]
