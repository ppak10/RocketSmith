import pytest
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from rocketsmith.prusaslicer.mcp.config import register_prusaslicer_config
from rocketsmith.prusaslicer.models import ConfigType


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-prusaslicer")
    register_prusaslicer_config(app)
    return app


# ── Registration ──────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "prusaslicer_config"


# ── Unit tests ────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_list_empty_returns_empty(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="list",
        prusaslicer_config_path=tmp_path / "prusaslicer" / "configs",
    )
    assert result.success is True
    assert result.data.count == 0


@pytest.mark.anyio
async def test_missing_config_type_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="show",
        # config_type intentionally omitted
        config_name="default",
        prusaslicer_config_path=tmp_path,
    )
    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_missing_config_name_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="create",
        config_type=ConfigType.PRINTER,
        # config_name intentionally omitted
        settings={"bed_shape": "0x0,250x0,250x210,0x210"},
        prusaslicer_config_path=tmp_path,
    )
    assert result.success is False
    assert result.error_code == "MISSING_ARGUMENT"


@pytest.mark.anyio
async def test_create_and_list_config(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    base = tmp_path / "prusaslicer" / "configs"

    result = await tool.fn(
        action="create",
        config_type=ConfigType.PRINTER,
        config_name="voron",
        settings={"bed_shape": "0x0,350x0,350x350,0x350", "gcode_flavor": "klipper"},
        prusaslicer_config_path=base,
    )
    assert result.success is True
    # Config written to prusaslicer/configs/printer/voron.ini (plural 'configs')
    assert (base / "printer" / "voron.ini").exists()

    list_result = await tool.fn(
        action="list",
        prusaslicer_config_path=base,
    )
    assert list_result.success is True
    assert list_result.data.count == 1
    assert list_result.data.configs[0].name == "voron"


@pytest.mark.anyio
async def test_default_path_uses_configs_plural(mcp_app, tmp_path):
    """Default config root must be prusaslicer/configs/ (plural), not prusaslicer/config/.

    Regression: layout.py had PRUSASLICER_CONFIG_DIR = 'prusaslicer/config'
    (singular) which caused agents following documentation to create the wrong
    directory.
    """
    from rocketsmith.prusaslicer.config import DEFAULT_CONFIG_PATH

    assert (
        str(DEFAULT_CONFIG_PATH) == "prusaslicer/configs"
    ), f"DEFAULT_CONFIG_PATH should be 'prusaslicer/configs' (plural) but got {DEFAULT_CONFIG_PATH!r}"

    from rocketsmith.gui.layout import PRUSASLICER_CONFIG_DIR

    assert (
        PRUSASLICER_CONFIG_DIR == "prusaslicer/configs"
    ), f"PRUSASLICER_CONFIG_DIR should be 'prusaslicer/configs' but got {PRUSASLICER_CONFIG_DIR!r}"


@pytest.mark.anyio
async def test_show_nonexistent_config_returns_error(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    result = await tool.fn(
        action="show",
        config_type=ConfigType.PRINTER,
        config_name="does_not_exist",
        prusaslicer_config_path=tmp_path,
    )
    assert result.success is False
    assert result.error_code == "NOT_FOUND"


@pytest.mark.anyio
async def test_set_creates_if_absent(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    base = tmp_path / "prusaslicer" / "configs"

    result = await tool.fn(
        action="set",
        config_type=ConfigType.PRINT,
        config_name="standard",
        settings={"layer_height": "0.2", "infill_density": "20%"},
        prusaslicer_config_path=base,
    )
    assert result.success is True
    ini = base / "print" / "standard.ini"
    assert ini.exists()
    content = ini.read_text()
    assert "layer_height = 0.2" in content
    assert "infill_density = 20%" in content


@pytest.mark.anyio
async def test_delete_config(mcp_app, tmp_path):
    tools = mcp_app._tool_manager.list_tools()
    tool = tools[0]

    base = tmp_path / "prusaslicer" / "configs"

    await tool.fn(
        action="create",
        config_type=ConfigType.FILAMENT,
        config_name="pla",
        settings={"filament_type": "PLA"},
        prusaslicer_config_path=base,
    )

    result = await tool.fn(
        action="delete",
        config_type=ConfigType.FILAMENT,
        config_name="pla",
        prusaslicer_config_path=base,
    )
    assert result.success is True
    assert not (base / "filament" / "pla.ini").exists()
