import pytest

from mcp.server.fastmcp import FastMCP
from rocketsmith.openrocket.mcp.flight import register_openrocket_flight


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-openrocket")
    register_openrocket_flight(app)
    return app


# ── Registration ───────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "openrocket_flight"


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_create_missing_motor_designation_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    p = tmp_path / "test.ork"
    p.touch()

    result = await tool.fn(
        action="create",
        rocket_file_path=p,
        # motor_designation intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_delete_missing_sim_name_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    p = tmp_path / "test.ork"
    p.touch()

    result = await tool.fn(
        action="create",
        rocket_file_path=p,
        # sim_name intentionally omitted
    )

    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_motor_not_found_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    p = tmp_path / "test.ork"
    p.touch()

    result = await tool.fn(
        action="create",
        rocket_file_path=p,
        openrocket_path=tmp_path / "fake.jar",
        motor_designation="ZZZ999",
    )

    assert result.success is False
    assert result.error_code in (
        "INVALID_ARGUMENT",
        "FILE_NOT_FOUND",
        "SIMULATION_FAILED",
    )


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


@pytest.mark.anyio
async def test_create_flight(mcp_app, openrocket_jar, tmp_path):
    from rocketsmith.openrocket.components import new_ork, create_component

    ork_path = tmp_path / "test.ork"
    new_ork("Test Rocket", ork_path, openrocket_jar)
    create_component(ork_path, "body-tube", openrocket_jar, diameter=0.064, length=0.4)
    create_component(ork_path, "inner-tube", openrocket_jar, diameter=0.029, length=0.1)

    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="create",
        rocket_file_path=ork_path,
        openrocket_path=openrocket_jar,
        motor_designation="D12",
    )

    assert result.success is True
    assert result.data["motor_designation"] == "D12"
    assert "flight_name" in result.data
    assert "mount_component" in result.data


@pytest.mark.anyio
async def test_create_then_delete_flight(mcp_app, openrocket_jar, tmp_path):
    from rocketsmith.openrocket.components import new_ork, create_component

    ork_path = tmp_path / "test.ork"
    new_ork("Test Rocket", ork_path, openrocket_jar)
    create_component(ork_path, "body-tube", openrocket_jar, diameter=0.064, length=0.4)
    create_component(ork_path, "inner-tube", openrocket_jar, diameter=0.029, length=0.1)

    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    create_result = await tool.fn(
        action="create",
        rocket_file_path=ork_path,
        openrocket_path=openrocket_jar,
        motor_designation="D12",
        sim_name="My Sim",
    )
    assert create_result.success is True

    delete_result = await tool.fn(
        action="delete",
        rocket_file_path=ork_path,
        openrocket_path=openrocket_jar,
        sim_name="My Sim",
    )
    assert delete_result.success is True
    assert delete_result.data["deleted"] == "My Sim"


@pytest.mark.anyio
async def test_delete_nonexistent_sim_returns_error(mcp_app, openrocket_jar, tmp_path):
    from rocketsmith.openrocket.components import new_ork

    path = tmp_path / "test.ork"
    new_ork("Test Rocket", path, openrocket_jar)

    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="delete",
        rocket_file_path=path,
        openrocket_path=openrocket_jar,
        sim_name="NonExistent",
    )

    assert result.success is False
    assert result.error_code == "INVALID_ARGUMENT"


@pytest.mark.anyio
async def test_create_then_run_flight(mcp_app, openrocket_jar, tmp_path):
    """Full workflow: build rocket → assign motor → run flight → check stability."""
    from rocketsmith.openrocket.components import new_ork, create_component
    from rocketsmith.openrocket.simulation import run_simulation

    ork_path = tmp_path / "test.ork"
    new_ork("Test Rocket", ork_path, openrocket_jar)
    create_component(
        ork_path,
        "nose-cone",
        openrocket_jar,
        diameter=0.064,
        length=0.12,
        shape="ogive",
    )
    create_component(ork_path, "body-tube", openrocket_jar, diameter=0.064, length=0.4)
    create_component(ork_path, "inner-tube", openrocket_jar, diameter=0.029, length=0.1)
    create_component(
        ork_path,
        "fin-set",
        openrocket_jar,
        count=3,
        root_chord=0.08,
        tip_chord=0.04,
        span=0.06,
    )

    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="create",
        rocket_file_path=ork_path,
        openrocket_path=openrocket_jar,
        motor_designation="D12",
    )
    assert result.success is True

    sims = run_simulation(ork_path, openrocket_jar)
    assert len(sims) == 1

    # Verify the motor actually fired — a zero/tiny altitude would indicate
    # the motor was not persisted to the saved .ork file ("No motors defined"
    # class of bug). A D12 in a small test rocket should easily clear 50 m.
    from orhelper import FlightDataType

    altitude = sims[0].timeseries.get(FlightDataType.TYPE_ALTITUDE)
    assert altitude is not None, "No altitude timeseries returned"
    assert float(altitude.max()) > 50.0, (
        f"Motor did not fire: max altitude was {float(altitude.max()):.2f} m. "
        "This suggests the motor was not persisted to the .ork file."
    )
