"""Unit tests for cadsmith_run_script MCP tool.

Tests that do not require uv or build123d — they exercise pre-execution
validation (file-not-found, dir-not-found, and manifest-based name check)
without actually spawning a subprocess.
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from rocketsmith.cadsmith.mcp.run_script import register_cadsmith_run_script


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp_app():
    app = FastMCP(name="test-cadsmith")
    register_cadsmith_run_script(app)
    return app


@pytest.fixture
def tool(mcp_app):
    return mcp_app._tool_manager.list_tools()[0]


# ── Registration ───────────────────────────────────────────────────────────────


def test_tool_registered(mcp_app):
    tools = mcp_app._tool_manager.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "cadsmith_run_script"


# ── Pre-execution guard: missing files ────────────────────────────────────────


@pytest.mark.anyio
async def test_missing_script_returns_error(tool, tmp_path):
    out_dir = tmp_path / "step"
    out_dir.mkdir()

    result = await tool.fn(
        script_path=tmp_path / "cadsmith" / "source" / "nose_cone.py",
        out_dir=out_dir,
    )

    assert result.success is False
    assert result.error_code == "FILE_NOT_FOUND"


@pytest.mark.anyio
async def test_missing_out_dir_returns_error(tool, tmp_path):
    script = tmp_path / "cadsmith" / "source" / "nose_cone.py"
    script.parent.mkdir(parents=True)
    script.write_text("from build123d import *\nexport_step(None, '')\n")

    result = await tool.fn(
        script_path=script,
        out_dir=tmp_path / "nonexistent_dir",
    )

    assert result.success is False
    assert result.error_code == "DIR_NOT_FOUND"


# ── Manifest inference ─────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_manifest_rejection_when_name_not_in_tree(tool, tmp_path):
    """When component_tree.json exists at the inferred path and the script
    stem is not a valid cadsmith_path, validation should reject the script
    before attempting to run it."""
    # Build the directory layout:  <tmp>/cadsmith/source/<name>.py
    #                              <tmp>/gui/component_tree.json
    source_dir = tmp_path / "cadsmith" / "source"
    source_dir.mkdir(parents=True)
    out_dir = tmp_path / "step"
    out_dir.mkdir()

    # Valid script content but with a name that's not in the manifest
    script = source_dir / "body_tube_pass2.py"
    script.write_text(
        "from build123d import *\nfrom pathlib import Path\n"
        "export_step(None, str(Path('x.step')))\n"
    )

    # Manifest with only "nose_cone" as a valid part
    gui_dir = tmp_path / "gui"
    gui_dir.mkdir()
    tree = {
        "schema_version": 1,
        "source_ork": "/fake/rocket.ork",
        "project_root": str(tmp_path),
        "generated_at": "2026-01-01T00:00:00+00:00",
        "rocket_name": "Test Rocket",
        "stages": [
            {
                "name": "Sustainer",
                "components": [
                    {
                        "type": "NoseCone",
                        "name": "Nose Cone",
                        "category": "structural",
                        "dimensions": {
                            "kind": "nose_cone",
                            "shape": "ogive",
                            "length": [120.0, "millimeter"],
                            "base_od": [64.0, "millimeter"],
                            "wall": [3.0, "millimeter"],
                        },
                        "cadsmith_path": "nose_cone.py",
                        "agent": {"fate": "print"},
                        "children": [],
                    }
                ],
            }
        ],
    }
    (gui_dir / "component_tree.json").write_text(json.dumps(tree), encoding="utf-8")

    result = await tool.fn(script_path=script, out_dir=out_dir)

    assert result.success is False
    assert result.error_code == "VALIDATION_ERROR"
    # The error message should mention the offending filename
    assert any("body_tube_pass2.py" in e for e in result.details["validation_errors"])


@pytest.mark.anyio
async def test_no_manifest_skips_name_check_proceeds_to_validation(tool, tmp_path):
    """Without a manifest the name check is skipped; validation still catches
    a script that omits export_step."""
    source_dir = tmp_path / "cadsmith" / "source"
    source_dir.mkdir(parents=True)
    out_dir = tmp_path / "step"
    out_dir.mkdir()

    # Script with no export_step — should fail on the export check, not name check
    script = source_dir / "anything.py"
    script.write_text("from build123d import *\n")

    # No gui/component_tree.json created

    result = await tool.fn(script_path=script, out_dir=out_dir)

    assert result.success is False
    assert result.error_code == "VALIDATION_ERROR"
    assert any("export_step" in e for e in result.details["validation_errors"])
