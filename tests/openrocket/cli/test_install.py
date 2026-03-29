import subprocess
import sys
import pytest

from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


def test_install_macos(runner):
    """macOS: invokes brew with the correct arguments."""
    with (
        patch("sys.platform", "darwin"),
        patch("shutil.which", return_value="/usr/local/bin/brew"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["brew", "install", "--cask", "openrocket"], check=True
        )


def test_install_macos_no_brew(runner):
    """macOS: exits with code 1 when Homebrew is not installed."""
    with (
        patch("sys.platform", "darwin"),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "homebrew" in result.stdout.lower()


def test_install_windows(runner):
    """Windows: invokes winget with the correct arguments."""
    with (
        patch("sys.platform", "win32"),
        patch("shutil.which", return_value="winget"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["winget", "install", "--exact", "--id", "OpenRocket.OpenRocket"],
            check=True,
        )


def test_install_windows_no_winget(runner):
    """Windows: exits with code 1 when winget is not available."""
    with (
        patch("sys.platform", "win32"),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "winget" in result.stdout.lower()


def test_install_linux_already_installed(runner, tmp_path):
    """Linux: skips download when the JAR already exists."""
    jar = tmp_path / "OpenRocket-24.12.jar"
    jar.touch()

    mock_asset = {"name": "OpenRocket-24.12.jar", "browser_download_url": "https://example.com/OpenRocket-24.12.jar"}
    mock_release = {"tag_name": "release-24.12", "assets": [mock_asset]}

    with (
        patch("sys.platform", "linux"),
        patch("rocketsmith.openrocket.install._get_latest_jar_asset", return_value=("24.12", mock_asset["browser_download_url"])),
        patch("rocketsmith.openrocket.install._download_jar") as mock_download,
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["install"])
        mock_download.assert_not_called()


def test_install_integration(runner):
    """Integration: install command succeeds on the current platform."""
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
