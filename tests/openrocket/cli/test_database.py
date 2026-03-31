import pytest

from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


# ── list-motors ───────────────────────────────────────────────────────────────


def test_list_motors_no_jar(runner):
    with patch("rocketsmith.openrocket.cli.list_motors.get_openrocket_path", side_effect=FileNotFoundError("not found")):
        result = runner.invoke(app, ["list-motors"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


# ── list-presets ──────────────────────────────────────────────────────────────


def test_list_presets_no_jar(runner):
    with patch("rocketsmith.openrocket.cli.list_presets.get_openrocket_path", side_effect=FileNotFoundError("not found")):
        result = runner.invoke(app, ["list-presets", "body-tube"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_list_presets_invalid_type(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with patch("rocketsmith.openrocket.cli.list_presets.get_openrocket_path", return_value=jar):
        result = runner.invoke(app, ["list-presets", "laser-cannon"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


# ── list-materials ────────────────────────────────────────────────────────────


def test_list_materials_no_jar(runner):
    with patch("rocketsmith.openrocket.cli.list_materials.get_openrocket_path", side_effect=FileNotFoundError("not found")):
        result = runner.invoke(app, ["list-materials", "bulk"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_list_materials_invalid_type(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with patch("rocketsmith.openrocket.cli.list_materials.get_openrocket_path", return_value=jar):
        result = runner.invoke(app, ["list-materials", "plasma"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


def test_cli_list_motors(runner, openrocket_jar):
    with patch("rocketsmith.openrocket.cli.list_motors.get_openrocket_path", return_value=openrocket_jar):
        result = runner.invoke(app, ["list-motors", "--class", "D", "--manufacturer", "Estes"])
    assert result.exit_code == 0
    assert "Estes" in result.stdout
    assert "D" in result.stdout


def test_cli_list_motors_no_results(runner, openrocket_jar):
    with patch("rocketsmith.openrocket.cli.list_motors.get_openrocket_path", return_value=openrocket_jar):
        result = runner.invoke(app, ["list-motors", "--manufacturer", "NoSuchManufacturerXYZ"])
    assert result.exit_code == 0
    assert "No motors found" in result.stdout


def test_cli_list_presets(runner, openrocket_jar):
    with patch("rocketsmith.openrocket.cli.list_presets.get_openrocket_path", return_value=openrocket_jar):
        result = runner.invoke(app, ["list-presets", "parachute", "--manufacturer", "Estes"])
    assert result.exit_code == 0


def test_cli_list_materials_bulk(runner, openrocket_jar):
    with patch("rocketsmith.openrocket.cli.list_materials.get_openrocket_path", return_value=openrocket_jar):
        result = runner.invoke(app, ["list-materials", "bulk"])
    assert result.exit_code == 0
    assert "Aluminum" in result.stdout


def test_cli_list_materials_line(runner, openrocket_jar):
    with patch("rocketsmith.openrocket.cli.list_materials.get_openrocket_path", return_value=openrocket_jar):
        result = runner.invoke(app, ["list-materials", "line"])
    assert result.exit_code == 0
    assert "nylon" in result.stdout.lower()
