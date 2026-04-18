"""Tests for cadsmith script pre-execution validation."""

import json
from pathlib import Path

import pytest

from rocketsmith.cadsmith.validate_script import validate_script

# ── Minimal valid script ───────────────────────────────────────────────────────

VALID_SCRIPT = """\
from build123d import *
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / "step" / "nose_cone.step"

with BuildPart() as part:
    Cylinder(10, 20)

export_step(part.part, str(OUTPUT))
"""


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def script_dir(tmp_path):
    """Simulate <project>/cadsmith/source/ layout."""
    source = tmp_path / "cadsmith" / "source"
    source.mkdir(parents=True)
    return source


@pytest.fixture
def manifest_path(tmp_path):
    """A component_tree.json with one printable part (nose_cone)."""
    gui = tmp_path / "gui"
    gui.mkdir()
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
    p = gui / "component_tree.json"
    p.write_text(json.dumps(tree), encoding="utf-8")
    return p


# ── Tests: no manifest (backward-compatible) ──────────────────────────────────


def test_valid_script_no_manifest(script_dir):
    p = script_dir / "nose_cone.py"
    p.write_text(VALID_SCRIPT)
    assert validate_script(p) == []


def test_missing_export_step(script_dir):
    p = script_dir / "nose_cone.py"
    p.write_text("from build123d import *\n")
    errors = validate_script(p)
    assert any("export_step" in e for e in errors)


def test_disallowed_import(script_dir):
    p = script_dir / "nose_cone.py"
    p.write_text("import numpy\nexport_step(None, '')\n")
    errors = validate_script(p)
    assert any("numpy" in e for e in errors)


def test_syntax_error(script_dir):
    p = script_dir / "nose_cone.py"
    p.write_text("def (:\n")
    errors = validate_script(p)
    assert any("Syntax error" in e for e in errors)


# ── Tests: with manifest ───────────────────────────────────────────────────────


def test_valid_script_matches_manifest(script_dir, manifest_path):
    p = script_dir / "nose_cone.py"
    p.write_text(VALID_SCRIPT)
    assert validate_script(p, manifest_path=manifest_path) == []


def test_script_not_in_manifest_rejected(script_dir, manifest_path):
    p = script_dir / "nose_cone_pass2.py"
    p.write_text(VALID_SCRIPT)
    errors = validate_script(p, manifest_path=manifest_path)
    assert any("nose_cone_pass2.py" in e for e in errors)
    assert any("nose_cone.py" in e for e in errors)


def test_missing_manifest_skips_name_check(script_dir, tmp_path):
    p = script_dir / "anything.py"
    p.write_text(VALID_SCRIPT)
    missing = tmp_path / "gui" / "component_tree.json"
    assert validate_script(p, manifest_path=missing) == []


def test_empty_manifest_cadsmith_paths_skips_check(script_dir, tmp_path):
    """If manifest exists but no cadsmith_path is set yet, skip the check."""
    gui = tmp_path / "gui"
    gui.mkdir()
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
                        "cadsmith_path": None,
                        "agent": None,
                        "children": [],
                    }
                ],
            }
        ],
    }
    manifest = gui / "component_tree.json"
    manifest.write_text(json.dumps(tree), encoding="utf-8")

    p = script_dir / "anything.py"
    p.write_text(VALID_SCRIPT)
    assert validate_script(p, manifest_path=manifest) == []


def test_nested_component_cadsmith_path_recognised(script_dir, tmp_path):
    """cadsmith_path on a nested child component is found."""
    gui = tmp_path / "gui"
    gui.mkdir()
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
                        "type": "BodyTube",
                        "name": "Body Tube",
                        "category": "structural",
                        "dimensions": {
                            "kind": "tube",
                            "length": [600.0, "millimeter"],
                            "od": [64.0, "millimeter"],
                            "id": [58.0, "millimeter"],
                            "motor_mount": False,
                        },
                        "cadsmith_path": "body_tube.py",
                        "agent": {"fate": "print"},
                        "children": [
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
        ],
    }
    manifest = gui / "component_tree.json"
    manifest.write_text(json.dumps(tree), encoding="utf-8")

    p = script_dir / "nose_cone.py"
    p.write_text(VALID_SCRIPT)
    assert validate_script(p, manifest_path=manifest) == []
