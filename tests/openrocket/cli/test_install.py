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
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
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
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("sys.platform", "darwin"),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "homebrew" in result.stdout.lower()


def test_install_windows(runner):
    """Windows: invokes winget with the correct arguments."""
    with (
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
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
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("sys.platform", "win32"),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "winget" in result.stdout.lower()


def test_install_already_installed(runner, tmp_path):
    """Skips installation and reports version when already installed."""
    jar = tmp_path / "OpenRocket-24.12.jar"
    jar.touch()

    with (
        patch("rocketsmith.openrocket.install.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.install._download_jar") as mock_download,
        patch("subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        assert "24.12" in result.stdout
        mock_download.assert_not_called()
        mock_run.assert_not_called()


def test_install_integration(runner):
    """Integration: install command succeeds on the current platform."""
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
