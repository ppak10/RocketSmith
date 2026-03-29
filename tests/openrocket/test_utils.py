import os
import pytest

from pathlib import Path
from unittest.mock import patch

from rocketsmith.openrocket.utils import get_openrocket_path


def test_get_openrocket_path_hint_file(tmp_path):
    """Returns the hint directly when it points to an existing file."""
    jar = tmp_path / "OpenRocket-24.12.jar"
    jar.touch()
    assert get_openrocket_path(hint=jar) == jar


def test_get_openrocket_path_hint_directory(tmp_path):
    """Searches the hint directory when it is a folder."""
    jar = tmp_path / "OpenRocket-24.12.jar"
    jar.touch()
    assert get_openrocket_path(hint=tmp_path) == jar


def test_get_openrocket_path_hint_directory_picks_latest(tmp_path):
    """Picks the last alphabetically (highest version) when multiple JARs exist."""
    (tmp_path / "OpenRocket-15.03.jar").touch()
    (tmp_path / "OpenRocket-24.12.jar").touch()
    result = get_openrocket_path(hint=tmp_path)
    assert result.name == "OpenRocket-24.12.jar"


def test_get_openrocket_path_env_var(tmp_path):
    """Respects the OPENROCKET_JAR environment variable."""
    jar = tmp_path / "OpenRocket-24.12.jar"
    jar.touch()
    with patch.dict(os.environ, {"OPENROCKET_JAR": str(jar)}):
        assert get_openrocket_path() == jar


def test_get_openrocket_path_env_var_directory(tmp_path):
    """Accepts OPENROCKET_JAR pointing to a directory."""
    jar = tmp_path / "OpenRocket-24.12.jar"
    jar.touch()
    with patch.dict(os.environ, {"OPENROCKET_JAR": str(tmp_path)}):
        assert get_openrocket_path() == jar


def test_get_openrocket_path_not_found(tmp_path):
    """Raises FileNotFoundError when no JAR can be located."""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "rocketsmith.openrocket.utils._SEARCH_PATHS",
            {"darwin": [tmp_path], "linux": [tmp_path], "win32": [tmp_path]},
        ),
    ):
        with pytest.raises(FileNotFoundError):
            get_openrocket_path()


def test_get_openrocket_path_installed(openrocket_jar):
    """Integration: get_openrocket_path() resolves to a real file when installed."""
    assert openrocket_jar.exists()
    assert openrocket_jar.suffix == ".jar"
