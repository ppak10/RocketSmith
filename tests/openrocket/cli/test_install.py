import pytest

from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app
from rocketsmith.openrocket.install import OPENROCKET_VERSION

_FAKE_JVM = Path("/fake/jvm/libjvm.dylib")


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


def test_install_downloads_jar(runner, tmp_path):
    """Downloads the pinned 23.09 JAR when OpenRocket is not installed."""
    with (
        patch("rocketsmith.openrocket.install.get_openrocket_jvm", return_value=_FAKE_JVM),
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("rocketsmith.openrocket.install._get_install_dir", return_value=tmp_path),
        patch("rocketsmith.openrocket.install._download_jar") as mock_download,
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        expected_dest = tmp_path / f"OpenRocket-{OPENROCKET_VERSION}.jar"
        mock_download.assert_called_once_with(
            f"https://github.com/openrocket/openrocket/releases/download/"
            f"release-{OPENROCKET_VERSION}/OpenRocket-{OPENROCKET_VERSION}.jar",
            expected_dest,
        )


def test_install_windows_download_dir(runner, tmp_path):
    """Windows: JAR is downloaded to AppData/Local/OpenRocket."""
    with (
        patch("rocketsmith.openrocket.install.get_openrocket_jvm", return_value=_FAKE_JVM),
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("sys.platform", "win32"),
        patch("rocketsmith.openrocket.install._download_jar") as mock_download,
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        expected_dest = tmp_path / "AppData" / "Local" / "OpenRocket" / f"OpenRocket-{OPENROCKET_VERSION}.jar"
        mock_download.assert_called_once_with(mock_download.call_args[0][0], expected_dest)


def test_install_unix_download_dir(runner, tmp_path):
    """macOS/Linux: JAR is downloaded to ~/.local/share/openrocket."""
    with (
        patch("rocketsmith.openrocket.install.get_openrocket_jvm", return_value=_FAKE_JVM),
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("sys.platform", "linux"),
        patch("rocketsmith.openrocket.install._download_jar") as mock_download,
        patch("pathlib.Path.home", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        expected_dest = tmp_path / ".local" / "share" / "openrocket" / f"OpenRocket-{OPENROCKET_VERSION}.jar"
        mock_download.assert_called_once_with(mock_download.call_args[0][0], expected_dest)


def test_install_java_macos(runner, tmp_path):
    """macOS: installs Java via brew when no JVM is found."""
    with (
        patch("rocketsmith.openrocket.install.get_openrocket_jvm", return_value=None),
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("sys.platform", "darwin"),
        patch("shutil.which", return_value="/usr/local/bin/brew"),
        patch("subprocess.run") as mock_run,
        patch("rocketsmith.openrocket.install._download_jar"),
        patch("rocketsmith.openrocket.install._get_install_dir", return_value=tmp_path),
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(["brew", "install", "openjdk"], check=True)


def test_install_java_linux(runner, tmp_path):
    """Linux: installs Java via apt when no JVM is found."""
    with (
        patch("rocketsmith.openrocket.install.get_openrocket_jvm", return_value=None),
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("sys.platform", "linux"),
        patch("subprocess.run") as mock_run,
        patch("rocketsmith.openrocket.install._download_jar"),
        patch("rocketsmith.openrocket.install._get_install_dir", return_value=tmp_path),
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["sudo", "apt-get", "install", "-y", "default-jre-headless"],
            check=True,
        )


def test_install_java_windows(runner, tmp_path):
    """Windows: installs Java via winget when no JVM is found."""
    with (
        patch("rocketsmith.openrocket.install.get_openrocket_jvm", return_value=None),
        patch("rocketsmith.openrocket.install.get_openrocket_path", side_effect=FileNotFoundError),
        patch("sys.platform", "win32"),
        patch("shutil.which", return_value="winget"),
        patch("subprocess.run") as mock_run,
        patch("rocketsmith.openrocket.install._download_jar"),
        patch("rocketsmith.openrocket.install._get_install_dir", return_value=tmp_path),
    ):
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            [
                "winget", "install",
                "--exact", "--id", "EclipseAdoptium.Temurin.21.JRE",
                "--accept-source-agreements",
                "--accept-package-agreements",
            ],
            check=True,
        )


def test_install_already_installed(runner, tmp_path):
    """Skips download and reports version when already installed."""
    jar = tmp_path / f"OpenRocket-{OPENROCKET_VERSION}.jar"
    jar.touch()

    with (
        patch("rocketsmith.openrocket.install.get_openrocket_jvm", return_value=_FAKE_JVM),
        patch("rocketsmith.openrocket.install.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.install._download_jar") as mock_download,
    ):
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0
        assert OPENROCKET_VERSION in result.stdout
        mock_download.assert_not_called()


def test_install_integration(runner):
    """Integration: install command succeeds on the current platform."""
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
