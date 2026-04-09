import pytest

from mcp.server.fastmcp import FastMCP
from rocketsmith.openrocket.mcp.cad_handoff import register_openrocket_cad_handoff


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-openrocket")
    register_openrocket_cad_handoff(app)
    return app


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "openrocket_cad_handoff"


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


def test_convert_component_unit_rewrite():
    from rocketsmith.openrocket.cad_handoff import _convert_component

    result = _convert_component(
        {
            "type": "BodyTube",
            "name": "Upper",
            "length_m": 0.4,
            "outer_diameter_m": 0.064,
            "inner_diameter_m": 0.060,
            "thickness_m": 0.002,
            "motor_mount": False,
            "shape": None,
        }
    )

    assert result["type"] == "BodyTube"
    assert result["name"] == "Upper"
    assert result["length_mm"] == 400.0
    assert result["outer_diameter_mm"] == 64.0
    assert result["inner_diameter_mm"] == 60.0
    assert result["thickness_mm"] == 2.0
    assert result["motor_mount"] is False
    # No leftover metre keys
    assert not any(k.endswith("_m") for k in result if k.endswith("_m") and k != "_mm")


def test_handoff_notes_include_unit_and_fin_rule():
    from rocketsmith.openrocket.cad_handoff import _build_handoff_notes

    notes = _build_handoff_notes([], motor_mount=None, body_tube_id_mm=None)
    joined = " ".join(notes)
    assert "mm" in joined.lower()
    assert "fin" in joined.lower()
    assert "lower airframe" in joined.lower()


def test_handoff_notes_warn_when_no_mount():
    from rocketsmith.openrocket.cad_handoff import _build_handoff_notes

    notes = _build_handoff_notes(
        [{"type": "BodyTube", "name": "b"}],
        motor_mount=None,
        body_tube_id_mm=60.0,
    )
    assert any("No motor mount" in n for n in notes)


def test_handoff_notes_include_body_id_for_couplers():
    from rocketsmith.openrocket.cad_handoff import _build_handoff_notes

    notes = _build_handoff_notes(
        [{"type": "BodyTube", "name": "b"}],
        motor_mount={"type": "InnerTube", "name": "m", "outer_diameter_mm": 29.0},
        body_tube_id_mm=60.0,
    )
    joined = " ".join(notes)
    assert "60.00" in joined
    assert "29.00" in joined


def test_find_motor_mount_prefers_inner_tube():
    from rocketsmith.openrocket.cad_handoff import _find_motor_mount

    components = [
        {"type": "BodyTube", "name": "airframe", "motor_mount": True},
        {"type": "InnerTube", "name": "mount"},
    ]
    assert _find_motor_mount(components)["name"] == "mount"


def test_find_motor_mount_falls_back_to_body_tube():
    from rocketsmith.openrocket.cad_handoff import _find_motor_mount

    components = [
        {"type": "BodyTube", "name": "airframe", "motor_mount": True},
    ]
    assert _find_motor_mount(components)["name"] == "airframe"


def test_find_motor_mount_returns_none():
    from rocketsmith.openrocket.cad_handoff import _find_motor_mount

    components = [{"type": "BodyTube", "name": "a"}]
    assert _find_motor_mount(components) is None


@pytest.mark.anyio
async def test_missing_file_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(rocket_file_path=tmp_path / "does_not_exist.ork")
    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"


# ── Integration tests (require OpenRocket JAR) ────────────────────────────────


@pytest.mark.anyio
async def test_cad_handoff_full_rocket(mcp_app, openrocket_jar, tmp_path):
    from rocketsmith.openrocket.components import new_ork, create_component

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

    result = await tool.fn(rocket_file_path=ork_path, openrocket_path=openrocket_jar)
    assert result.success is True

    data = result.data
    assert data["units"] == "mm"

    # Every length is in mm
    comps = data["components"]
    body_tube = next(c for c in comps if c["type"] == "BodyTube")
    assert body_tube["outer_diameter_mm"] == pytest.approx(64.0, rel=1e-3)
    assert body_tube["length_mm"] == pytest.approx(400.0, rel=1e-3)

    nose = next(c for c in comps if c["type"] == "NoseCone")
    assert nose["length_mm"] == pytest.approx(120.0, rel=1e-3)
    assert nose["shape"] == "ogive"

    fins = next(c for c in comps if c["type"] == "TrapezoidFinSet")
    assert fins["fin_count"] == 3
    assert fins["root_chord_mm"] == pytest.approx(80.0, rel=1e-3)
    assert fins["tip_chord_mm"] == pytest.approx(40.0, rel=1e-3)
    assert fins["span_mm"] == pytest.approx(60.0, rel=1e-3)

    # Derived: motor mount identified, body tube ID present
    derived = data["derived"]
    assert derived["motor_mount"] is not None
    assert derived["motor_mount"]["type"] == "InnerTube"
    assert derived["motor_mount"]["outer_diameter_mm"] == pytest.approx(29.0, rel=1e-3)
    assert derived["max_diameter_mm"] == pytest.approx(64.0, rel=1e-3)

    # Handoff notes mention key rules
    notes = " ".join(data["handoff_notes"]).lower()
    assert "mm" in notes
    assert "fin" in notes and "lower airframe" in notes
