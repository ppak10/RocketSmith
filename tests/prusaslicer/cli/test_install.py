import pytest

from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from rocketsmith.prusaslicer.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


def test_install_macos(runner):
    """macOS: invokes brew --cask with the correct arguments."""
    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", side_effect=FileNotFoundError),
        patch("sys.platform", "darwin"),
        patch("shutil.which", return_value="/usr/local/bin/brew"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["brew", "install", "--cask", "prusaslicer"], check=True
        )


def test_install_macos_no_brew(runner):
    """macOS: exits with code 1 when Homebrew is not installed."""
    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", side_effect=FileNotFoundError),
        patch("sys.platform", "darwin"),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "homebrew" in result.stdout.lower()


def test_install_linux_brew(runner):
    """Linux: uses brew when available."""
    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", side_effect=FileNotFoundError),
        patch("sys.platform", "linux"),
        patch("shutil.which", side_effect=lambda cmd: "/home/linuxbrew/.linuxbrew/bin/brew" if cmd == "brew" else None),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["brew", "install", "prusaslicer"], check=True
        )


def test_install_linux_snap(runner):
    """Linux: falls back to snap when brew is not available."""
    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", side_effect=FileNotFoundError),
        patch("sys.platform", "linux"),
        patch("shutil.which", side_effect=lambda cmd: "/usr/bin/snap" if cmd == "snap" else None),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["sudo", "snap", "install", "prusaslicer"], check=True
        )


def test_install_linux_no_package_manager(runner):
    """Linux: exits with code 1 when no supported package manager is found."""
    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", side_effect=FileNotFoundError),
        patch("sys.platform", "linux"),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "snap" in result.stdout.lower() or "brew" in result.stdout.lower()


def test_install_windows(runner):
    """Windows: invokes winget with the correct arguments."""
    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", side_effect=FileNotFoundError),
        patch("sys.platform", "win32"),
        patch("shutil.which", return_value="winget"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            [
                "winget", "install",
                "--exact", "--id", "Prusa3D.PrusaSlicer",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ],
            check=True,
        )


def test_install_windows_no_winget(runner):
    """Windows: exits with code 1 when winget is not available."""
    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", side_effect=FileNotFoundError),
        patch("sys.platform", "win32"),
        patch("shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 1
        assert "winget" in result.stdout.lower()


def test_install_already_installed(runner, tmp_path):
    """Skips installation and reports path when already installed."""
    exe = tmp_path / "PrusaSlicer"
    exe.touch()

    with (
        patch("rocketsmith.prusaslicer.install.get_prusaslicer_path", return_value=exe),
        patch("subprocess.run") as mock_run,
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        assert exe.name in result.stdout
        mock_run.assert_not_called()


def test_install_integration(runner, prusaslicer_exe):
    """Integration: install command succeeds when PrusaSlicer is already installed."""
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
