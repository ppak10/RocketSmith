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

    p = tmp_path / "test.ork"
    p.touch()

    result = await tool.fn(
        action="create",
        rocket_file_path=p,
        openrocket_path=tmp_path / "fake.jar",
        # component_type intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_update_missing_component_name_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    p = tmp_path / "test.ork"
    p.touch()

    result = await tool.fn(
        action="update",
        rocket_file_path=p,
        openrocket_path=tmp_path / "fake.jar",
        # component_name intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_delete_missing_component_name_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    p = tmp_path / "test.ork"
    p.touch()

    result = await tool.fn(
        action="delete",
        rocket_file_path=p,
        openrocket_path=tmp_path / "fake.jar",
        # component_name intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_create_unknown_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    p = tmp_path / "test.ork"
    p.touch()

    result = await tool.fn(
        action="create",
        rocket_file_path=p,
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
        rocket_file_path=tmp_ork,
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
        rocket_file_path=tmp_ork,
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
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="ReadMe",
        length=0.3,
    )

    result = await tool.fn(
        action="read",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="ReadMe",
    )

    assert result.success is True
    assert result.data["type"] == "NoseCone"
    assert result.data["name"] == "ReadMe"
    assert abs(result.data["length_m"] - 0.3) < 1e-4


@pytest.mark.anyio
async def test_read_nonexistent_component_returns_error(
    mcp_app, tmp_ork, openrocket_jar
):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="read",
        rocket_file_path=tmp_ork,
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
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="UpdateMe",
        length=0.3,
    )

    result = await tool.fn(
        action="update",
        rocket_file_path=tmp_ork,
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
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="Preserve",
        length=0.3,
        diameter=0.1,
    )

    result = await tool.fn(
        action="update",
        rocket_file_path=tmp_ork,
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
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="DeleteMe",
    )

    result = await tool.fn(
        action="delete",
        rocket_file_path=tmp_ork,
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
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        name="Gone",
    )

    await tool.fn(
        action="delete",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Gone",
    )

    result = inspect_ork(tmp_ork, openrocket_jar)
    names = [c["name"] for c in result["components"]]
    assert "Gone" not in names


@pytest.mark.anyio
async def test_create_centering_ring(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="BT",
        diameter=0.1,
        length=0.4,
    )

    result = await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="centering-ring",
        parent="BT",
        diameter=0.1,
        inner_diameter=0.03,
        length=0.005,
    )

    assert result.success is True
    assert result.data["type"] == "CenteringRing"


@pytest.mark.anyio
async def test_create_rail_button(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="BT",
        diameter=0.1,
        length=0.4,
    )

    result = await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="rail-button",
        parent="BT",
    )

    assert result.success is True
    assert result.data["type"] == "RailButton"


@pytest.mark.anyio
async def test_create_launch_lug(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="BT",
        diameter=0.1,
        length=0.4,
    )

    result = await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="launch-lug",
        parent="BT",
        diameter=0.012,
        inner_diameter=0.01,
        length=0.05,
    )

    assert result.success is True
    assert result.data["type"] == "LaunchLug"


@pytest.mark.anyio
async def test_create_streamer(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="BT",
        diameter=0.1,
        length=0.4,
    )

    result = await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="streamer",
        parent="BT",
        length=0.5,
        width=0.05,
    )

    assert result.success is True
    assert result.data["type"] == "Streamer"


@pytest.mark.anyio
async def test_create_shock_cord(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="BT",
        diameter=0.1,
        length=0.4,
    )

    result = await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="shock-cord",
        parent="BT",
        length=1.5,
    )

    assert result.success is True
    assert result.data["type"] == "ShockCord"


@pytest.mark.anyio
async def test_create_fin_set_with_explicit_parent(mcp_app, tmp_ork, openrocket_jar):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="Tube",
        length=0.6,
        diameter=0.1,
    )

    result = await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
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


# ── Mass override ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_mass_override_set_and_enabled(mcp_app, tmp_ork, openrocket_jar):
    """Setting override_mass_kg alone should implicitly enable the flag."""
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="Upper",
        length=0.4,
        diameter=0.064,
    )

    result = await tool.fn(
        action="update",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Upper",
        override_mass_kg=0.125,
    )
    assert result.success is True
    assert result.data["override_mass_enabled"] is True
    assert abs(result.data["override_mass_kg"] - 0.125) < 1e-6


@pytest.mark.anyio
async def test_mass_override_persists_across_reload(mcp_app, tmp_ork, openrocket_jar):
    """Override value and flag should survive a save + reload cycle."""
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="Upper",
        length=0.4,
        diameter=0.064,
    )
    await tool.fn(
        action="update",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Upper",
        override_mass_kg=0.250,
    )

    # Read in a fresh load
    result = await tool.fn(
        action="read",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Upper",
    )
    assert result.success is True
    assert result.data["override_mass_enabled"] is True
    assert abs(result.data["override_mass_kg"] - 0.250) < 1e-6


@pytest.mark.anyio
async def test_mass_override_affects_flight(mcp_app, tmp_ork, openrocket_jar):
    """A heavy mass override should reduce flight apogee."""
    from rocketsmith.openrocket.simulation import (
        create_simulation,
        run_simulation,
    )
    from orhelper import FlightDataType

    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="nose-cone",
        diameter=0.064,
        length=0.12,
        shape="ogive",
    )
    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="Body",
        diameter=0.064,
        length=0.4,
    )
    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="inner-tube",
        diameter=0.029,
        length=0.1,
    )
    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="fin-set",
        count=3,
        root_chord=0.08,
        tip_chord=0.04,
        span=0.06,
    )

    create_simulation(tmp_ork, openrocket_jar, "D12", sim_name="s")
    base = run_simulation(tmp_ork, openrocket_jar)[0]
    base_alt = float(base.timeseries.get(FlightDataType.TYPE_ALTITUDE).max())

    # Slam the body tube with a 500 g override — flight should be much shorter
    await tool.fn(
        action="update",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Body",
        override_mass_kg=0.500,
    )

    heavy = run_simulation(tmp_ork, openrocket_jar)[0]
    heavy_alt = float(heavy.timeseries.get(FlightDataType.TYPE_ALTITUDE).max())

    assert heavy_alt < base_alt * 0.5, (
        f"Mass override did not affect flight: baseline {base_alt:.1f} m "
        f"vs overridden {heavy_alt:.1f} m"
    )


@pytest.mark.anyio
async def test_mass_override_toggle_off(mcp_app, tmp_ork, openrocket_jar):
    """override_mass_enabled=False should disable the override flag."""
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    await tool.fn(
        action="create",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_type="body-tube",
        name="Upper",
        length=0.4,
        diameter=0.064,
        override_mass_kg=0.300,
    )

    result = await tool.fn(
        action="update",
        rocket_file_path=tmp_ork,
        openrocket_path=openrocket_jar,
        component_name="Upper",
        override_mass_enabled=False,
    )
    assert result.success is True
    assert result.data["override_mass_enabled"] is False
