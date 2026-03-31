import pytest

from mcp.server.fastmcp import FastMCP
from rocketsmith.openrocket.mcp.database import register_openrocket_database


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-openrocket")
    register_openrocket_database(app)
    return app


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "openrocket_database"


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_presets_missing_preset_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="presets",
        openrocket_path=tmp_path / "fake.jar",
        # preset_type intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_materials_missing_material_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="materials",
        openrocket_path=tmp_path / "fake.jar",
        # material_type intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_presets_invalid_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="presets",
        openrocket_path=tmp_path / "fake.jar",
        preset_type="laser-cannon",
    )

    assert result.success is False
    assert result.error_code == "INVALID_ARGUMENT"


@pytest.mark.anyio
async def test_materials_invalid_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="materials",
        openrocket_path=tmp_path / "fake.jar",
        material_type="plasma",
    )

    assert result.success is False
    assert result.error_code == "INVALID_ARGUMENT"


# ── Limit parameter ───────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_limit_caps_results(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    from unittest.mock import patch

    fake_motors = [{"common_name": f"D{i}", "manufacturer": "Test"} for i in range(100)]

    with patch("rocketsmith.openrocket.database.list_motors", return_value=fake_motors):
        result = await tool.fn(
            action="motors",
            openrocket_path=tmp_path / "fake.jar",
            limit=10,
        )

    assert result.success is True
    assert len(result.data) == 10


@pytest.mark.anyio
async def test_limit_none_returns_all(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    from unittest.mock import patch

    fake_motors = [{"common_name": f"D{i}", "manufacturer": "Test"} for i in range(100)]

    with patch("rocketsmith.openrocket.database.list_motors", return_value=fake_motors):
        result = await tool.fn(
            action="motors",
            openrocket_path=tmp_path / "fake.jar",
            limit=None,
        )

    assert result.success is True
    assert len(result.data) == 100


@pytest.mark.anyio
async def test_default_limit_is_50(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    from unittest.mock import patch

    fake_motors = [{"common_name": f"D{i}", "manufacturer": "Test"} for i in range(200)]

    with patch("rocketsmith.openrocket.database.list_motors", return_value=fake_motors):
        result = await tool.fn(
            action="motors",
            openrocket_path=tmp_path / "fake.jar",
        )

    assert result.success is True
    assert len(result.data) == 50


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


@pytest.mark.anyio
async def test_motors_returns_list(mcp_app, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="motors",
        openrocket_path=openrocket_jar,
        impulse_class="D",
        manufacturer="Estes",
    )

    assert result.success is True
    assert isinstance(result.data, list)
    assert len(result.data) > 0
    assert all(m["common_name"].upper().startswith("D") for m in result.data)


@pytest.mark.anyio
async def test_motors_empty_filter_returns_empty(mcp_app, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="motors",
        openrocket_path=openrocket_jar,
        manufacturer="NoSuchManufacturerXYZ",
    )

    assert result.success is True
    assert result.data == []


@pytest.mark.anyio
async def test_presets_body_tube(mcp_app, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="presets",
        openrocket_path=openrocket_jar,
        preset_type="body-tube",
        manufacturer="Estes",
    )

    assert result.success is True
    assert len(result.data) > 0
    assert all("outer_diameter_m" in p for p in result.data)


@pytest.mark.anyio
async def test_presets_parachute(mcp_app, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="presets",
        openrocket_path=openrocket_jar,
        preset_type="parachute",
    )

    assert result.success is True
    assert len(result.data) > 0
    assert all("diameter_m" in p for p in result.data)


@pytest.mark.anyio
async def test_materials_bulk(mcp_app, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="materials",
        openrocket_path=openrocket_jar,
        material_type="bulk",
    )

    assert result.success is True
    names = [m["name"] for m in result.data]
    assert "Aluminum" in names


@pytest.mark.anyio
async def test_materials_surface(mcp_app, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="materials",
        openrocket_path=openrocket_jar,
        material_type="surface",
    )

    assert result.success is True
    assert len(result.data) > 0


@pytest.mark.anyio
async def test_materials_line(mcp_app, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="materials",
        openrocket_path=openrocket_jar,
        material_type="line",
    )

    assert result.success is True
    assert len(result.data) > 0
