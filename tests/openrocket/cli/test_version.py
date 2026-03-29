import pytest

from unittest.mock import patch
from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


def test_version_not_found(runner):
    """Exits with code 1 and prints a warning when JAR is not found."""
    with patch(
        "rocketsmith.openrocket.cli.version.get_openrocket_path",
        side_effect=FileNotFoundError("OpenRocket JAR not found."),
    ):
        result = runner.invoke(app, ["version"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_version_with_explicit_jar(runner, tmp_path):
    """Shows version when given an explicit path to a JAR."""
    jar = tmp_path / "OpenRocket-24.12.jar"
    jar.touch()
    result = runner.invoke(app, ["version", "--openrocket-path", str(jar)])
    assert result.exit_code == 0
    assert "24.12" in result.stdout


def test_version_unknown_jar_name(runner, tmp_path):
    """Falls back to 'unknown' version when the JAR filename has no version number."""
    jar = tmp_path / "OpenRocket.jar"
    jar.touch()
    result = runner.invoke(app, ["version", "--openrocket-path", str(jar)])
    assert result.exit_code == 0
    assert "unknown" in result.stdout


def test_version_installed(runner, openrocket_jar):
    """Integration: version command succeeds and prints a version when installed."""
    result = runner.invoke(
        app, ["version", "--openrocket-path", str(openrocket_jar)]
    )
    assert result.exit_code == 0
    assert "✅" in result.stdout
