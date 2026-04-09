import json
import pytest
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from rocketsmith.manufacturing.mcp.manifest import register_manufacturing_manifest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-manufacturing")
    register_manufacturing_manifest(app)
    return app


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "manufacturing_manifest"


# ── Unit tests (no JVM required) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_generate_missing_rocket_file_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="generate",
        project_root=tmp_path,
        # rocket_file_path omitted
    )
    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_generate_nonexistent_rocket_file_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="generate",
        project_root=tmp_path,
        rocket_file_path=tmp_path / "does_not_exist.ork",
    )
    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"


@pytest.mark.anyio
async def test_read_nonexistent_manifest_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="read",
        project_root=tmp_path,
    )
    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"


@pytest.mark.anyio
async def test_read_invalid_json_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    (tmp_path / "parts_manifest.json").write_text("not valid json {")
    result = await tool.fn(
        action="read",
        project_root=tmp_path,
    )
    assert result.success is False
    assert result.error_code == "INVALID_MANIFEST"


@pytest.mark.anyio
async def test_hybrid_method_returns_not_implemented(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    fake_ork = tmp_path / "fake.ork"
    fake_ork.touch()

    result = await tool.fn(
        action="generate",
        project_root=tmp_path,
        rocket_file_path=fake_ork,
        method="hybrid",  # type: ignore[arg-type]
    )
    assert result.success is False
    assert result.error_code == "NOT_IMPLEMENTED"


# ── Integration tests (require OpenRocket JAR) ────────────────────────────────


@pytest.fixture
def minimal_rocket(tmp_path, openrocket_jar):
    from rocketsmith.openrocket.components import new_ork, create_component

    p = tmp_path / "test.ork"
    new_ork("TestRocket", p, openrocket_jar)
    create_component(
        p,
        "nose-cone",
        openrocket_jar,
        diameter=0.064,
        length=0.12,
        shape="ogive",
    )
    create_component(
        p,
        "body-tube",
        openrocket_jar,
        diameter=0.064,
        length=0.4,
        name="Upper Airframe",
    )
    create_component(p, "inner-tube", openrocket_jar, diameter=0.029, length=0.1)
    create_component(
        p,
        "fin-set",
        openrocket_jar,
        count=3,
        root_chord=0.08,
        tip_chord=0.04,
        span=0.06,
    )
    return p


@pytest.mark.anyio
async def test_generate_writes_manifest_file(
    mcp_app, minimal_rocket, tmp_path, openrocket_jar
):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="generate",
        project_root=tmp_path,
        rocket_file_path=minimal_rocket,
        openrocket_path=openrocket_jar,
    )
    assert result.success is True
    # File was written
    manifest_path = tmp_path / "parts_manifest.json"
    assert manifest_path.exists()
    # File is valid JSON
    data = json.loads(manifest_path.read_text())
    assert data["schema_version"] == 1
    assert data["default_policy"] == "additive"


@pytest.mark.anyio
async def test_read_returns_written_manifest(
    mcp_app, minimal_rocket, tmp_path, openrocket_jar
):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    # Generate first
    gen_result = await tool.fn(
        action="generate",
        project_root=tmp_path,
        rocket_file_path=minimal_rocket,
        openrocket_path=openrocket_jar,
    )
    assert gen_result.success is True

    # Then read
    read_result = await tool.fn(
        action="read",
        project_root=tmp_path,
    )
    assert read_result.success is True
    assert read_result.data["schema_version"] == 1
    assert len(read_result.data["parts"]) > 0


@pytest.mark.anyio
async def test_fusion_overrides_propagate(
    mcp_app, minimal_rocket, tmp_path, openrocket_jar
):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="generate",
        project_root=tmp_path,
        rocket_file_path=minimal_rocket,
        fusion_overrides={"motor_mount_fate": "separate"},
        openrocket_path=openrocket_jar,
    )
    assert result.success is True
    # Standalone motor mount should now exist
    part_names = [p["name"] for p in result.data["parts"]]
    assert "inner_tube" in part_names


@pytest.mark.anyio
async def test_generate_creates_project_root_if_missing(
    mcp_app, minimal_rocket, tmp_path, openrocket_jar
):
    """If the project_root doesn't exist yet, the tool should create it."""
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    new_project = tmp_path / "new_project_dir"
    assert not new_project.exists()

    result = await tool.fn(
        action="generate",
        project_root=new_project,
        rocket_file_path=minimal_rocket,
        openrocket_path=openrocket_jar,
    )
    assert result.success is True
    assert new_project.exists()
    assert (new_project / "parts_manifest.json").exists()
