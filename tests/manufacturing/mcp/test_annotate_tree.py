import json
import pytest
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from rocketsmith.manufacturing.mcp.annotate_tree import (
    register_manufacturing_annotate_tree,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-manufacturing")
    register_manufacturing_annotate_tree(app)
    return app


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "manufacturing_annotate_tree"


# ── Unit tests (no JVM required) ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_annotate_missing_project_dir_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        project_dir=tmp_path / "does_not_exist",
    )
    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"


@pytest.mark.anyio
async def test_annotate_invalid_json_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    # Create invalid component_tree.json
    (tmp_path / "gui").mkdir(parents=True)
    (tmp_path / "gui" / "component_tree.json").write_text("not valid json {")

    result = await tool.fn(
        project_dir=tmp_path,
    )
    assert result.success is False
    assert result.error_code == "PARSE_ERROR"


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
    return p


@pytest.mark.anyio
async def test_annotate_writes_back_to_file(
    mcp_app, minimal_rocket, tmp_path, openrocket_jar
):
    from rocketsmith.openrocket.generate_tree import generate_tree
    from rocketsmith.gui.layout import TREE_FILE

    # 1. Generate tree and write to project_dir/gui/component_tree.json
    tree, _ = generate_tree(minimal_rocket, tmp_path, jar_path=openrocket_jar)
    tree_path = tmp_path / TREE_FILE
    tree_path.parent.mkdir(parents=True, exist_ok=True)
    tree_path.write_text(tree.model_dump_json(indent=2))

    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    # 2. Annotate via tool
    result = await tool.fn(
        project_dir=tmp_path,
    )
    assert result.success is True

    # 3. Verify file was updated
    data = json.loads(tree_path.read_text())
    # Nose cone should have agent annotation
    sustainer = data["stages"][0]
    nc = sustainer["components"][0]
    assert nc["agent"]["fate"] == "print"
    assert nc["agent"]["updated_by"] == "manufacturing"
