import pytest

from mcp.server.fastmcp import FastMCP
from rocketsmith.openrocket.mcp.component import register_openrocket_component


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-openrocket")
    register_openrocket_component(app)
    return app


@pytest.fixture
def tmp_ork(tmp_path, openrocket_jar):
    from rocketsmith.openrocket.components import new_ork
    path = tmp_path / "test.ork"
    new_ork("Test Rocket", path, openrocket_jar)
    return path


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "openrocket_component"


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_missing_component_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="create",
        ork_path=tmp_path / "test.ork",
        openrocket_path=tmp_path / "fake.jar",
        # component_type intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_read_missing_component_name_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="read",
        ork_path=tmp_path / "test.ork",
        openrocket_path=tmp_path / "fake.jar",
        # component_name intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_update_missing_component_name_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="update",
        ork_path=tmp_path / "test.ork",
        openrocket_path=tmp_path / "fake.jar",
        # component_name intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_delete_missing_component_name_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="delete",
        ork_path=tmp_path / "test.ork",
        openrocket_path=tmp_path / "fake.jar",
        # component_name intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_create_unknown_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="create",
        ork_path=tmp_path / "test.ork",
        openrocket_path=tmp_path / "fake.jar",
        component_type="laser-cannon",
    )

    assert result.success is False
    assert result.error_code == "INVALID_ARGUMENT"


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


@pytest.mark.anyio
async def test_create_nose_cone(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="TestNose",
        length=0.3,
        diameter=0.1,
        shape="ogive",
    )

    assert result.success is True
    assert result.data["type"] == "NoseCone"
    assert result.data["name"] == "TestNose"
    assert abs(result.data["length_m"] - 0.3) < 1e-4
    assert result.data["shape"] == "ogive"


@pytest.mark.anyio
async def test_create_body_tube(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="MainTube",
        length=0.6,
        diameter=0.1,
    )

    assert result.success is True
    assert result.data["type"] == "BodyTube"
    assert abs(result.data["outer_diameter_m"] - 0.1) < 1e-4


@pytest.mark.anyio
async def test_read_component(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    # Create first
    await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="ReadMe",
        length=0.3,
    )

    result = await tool.fn(
        action="read",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="ReadMe",
    )

    assert result.success is True
    assert result.data["type"] == "NoseCone"
    assert result.data["name"] == "ReadMe"
    assert abs(result.data["length_m"] - 0.3) < 1e-4


@pytest.mark.anyio
async def test_read_nonexistent_component_returns_error(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="read",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="NoSuchComponent",
    )

    assert result.success is False
    assert result.error_code == "INVALID_ARGUMENT"


@pytest.mark.anyio
async def test_update_component(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="UpdateMe",
        length=0.3,
    )

    result = await tool.fn(
        action="update",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="UpdateMe",
        length=0.45,
    )

    assert result.success is True
    assert abs(result.data["length_m"] - 0.45) < 1e-4


@pytest.mark.anyio
async def test_update_preserves_other_properties(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="Preserve",
        length=0.3,
        diameter=0.1,
    )

    result = await tool.fn(
        action="update",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Preserve",
        length=0.35,
    )

    assert result.success is True
    assert abs(result.data["aft_diameter_m"] - 0.1) < 1e-4


@pytest.mark.anyio
async def test_delete_component(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="DeleteMe",
    )

    result = await tool.fn(
        action="delete",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="DeleteMe",
    )

    assert result.success is True
    assert result.data["deleted"] == "DeleteMe"


@pytest.mark.anyio
async def test_delete_persists(mcp_app, tmp_ork, openrocket_jar):
    """Deleted component is gone from the file on disk."""
    from rocketsmith.openrocket.components import inspect_ork

    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="Gone",
    )

    await tool.fn(
        action="delete",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Gone",
    )

    names = [c["name"] for c in inspect_ork(tmp_ork, openrocket_jar)]
    assert "Gone" not in names


@pytest.mark.anyio
async def test_create_fin_set_with_explicit_parent(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="Tube",
        length=0.6,
        diameter=0.1,
    )

    result = await tool.fn(
        action="create",
        ork_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="fin-set",
        parent="Tube",
        count=3,
        root_chord=0.1,
        tip_chord=0.05,
        span=0.08,
    )

    assert result.success is True
    assert result.data["type"] == "TrapezoidFinSet"
    assert result.data["fin_count"] == 3
