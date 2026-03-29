import pytest

from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


def test_version_not_found(runner, tmp_path):
    """Exits with code 1 and prints a warning when JAR is not found."""
    result = runner.invoke(app, ["version", "--openrocket-path", str(tmp_path)])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower() or "⚠️" in result.stdout


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
