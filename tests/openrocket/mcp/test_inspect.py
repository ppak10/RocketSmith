import pytest

from mcp.server.fastmcp import FastMCP
from rocketsmith.openrocket.mcp.inspect import register_openrocket_inspect


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-openrocket")
    register_openrocket_inspect(app)
    return app


@pytest.fixture
def tmp_ork(tmp_path, openrocket_jar):
    from rocketsmith.openrocket.components import new_ork

    path = tmp_path / "workspaces" / "test_ws" / "openrocket" / "test.ork"
    path.parent.mkdir(parents=True, exist_ok=True)
    new_ork("Test Rocket", path, openrocket_jar)
    return path


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "openrocket_inspect"


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_ork_not_found_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        workspace_name="test_ws",
        ork_filename="missing.ork",
        openrocket_path=tmp_path / "fake.jar",
    )

    assert result.success is False
    assert result.error_code in ("FILE_NOT_FOUND", "INSPECT_FAILED")


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


@pytest.mark.anyio
async def test_returns_component_list(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        workspace_name="test_ws",
        ork_filename="test.ork",
        openrocket_path=openrocket_jar,
    )

    assert result.success is True
    # result.data is now a dict with 'components' and 'ascii_art'
    assert isinstance(result.data, dict)
    assert "components" in result.data
    assert "ascii_art" in result.data
    assert isinstance(result.data["components"], list)
    assert len(result.data["components"]) > 0


@pytest.mark.anyio
async def test_root_is_rocket(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        workspace_name="test_ws",
        ork_filename="test.ork",
        openrocket_path=openrocket_jar,
    )

    assert result.success is True
    assert result.data["components"][0]["type"] == "Rocket"
    assert result.data["components"][0]["depth"] == 0


@pytest.mark.anyio
async def test_contains_axial_stage(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        workspace_name="test_ws",
        ork_filename="test.ork",
        openrocket_path=openrocket_jar,
    )

    assert result.success is True
    types = [c["type"] for c in result.data["components"]]
    assert "AxialStage" in types


@pytest.mark.anyio
async def test_each_entry_has_depth_and_name(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        workspace_name="test_ws",
        ork_filename="test.ork",
        openrocket_path=openrocket_jar,
    )

    assert result.success is True
    for entry in result.data["components"]:
        assert "depth" in entry
        assert "name" in entry
        assert "type" in entry
