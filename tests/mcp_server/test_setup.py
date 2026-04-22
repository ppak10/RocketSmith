"""Tests for rocketsmith.mcp.setup."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import rocketsmith.mcp.setup as setup_mod
from rocketsmith.mcp.setup import DependencyStatus, _check, _start_gui, register_setup


# ── helpers ───────────────────────────────────────────────────────────────────


def _all_found_status(**overrides):
    defaults = dict(
        java="installed (/usr/bin/java)",
        openrocket="installed (/opt/OpenRocket.jar)",
        prusaslicer="installed (/usr/bin/prusa-slicer)",
        ready=True,
    )
    defaults.update(overrides)
    return DependencyStatus(**defaults)


def _missing_status(**overrides):
    defaults = dict(
        java="not found",
        openrocket="not found",
        prusaslicer="not found",
        ready=False,
    )
    defaults.update(overrides)
    return DependencyStatus(**defaults)


# ── _check ────────────────────────────────────────────────────────────────────


def test_check_all_installed(monkeypatch):
    monkeypatch.setattr(
        "rocketsmith.mcp.setup.get_openrocket_jvm",
        lambda _: "/usr/bin/java",
        raising=False,
    )
    with (
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_jvm",
            return_value="/usr/bin/java",
        ),
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_path",
            return_value=Path("/opt/OpenRocket.jar"),
        ),
        patch(
            "rocketsmith.prusaslicer.utils.get_prusaslicer_path",
            return_value=Path("/usr/bin/prusa-slicer"),
        ),
    ):
        status = _check()

    assert status.ready is True
    assert "installed" in status.java
    assert "installed" in status.openrocket
    assert "installed" in status.prusaslicer


def test_check_java_missing(monkeypatch):
    with (
        patch("rocketsmith.openrocket.utils.get_openrocket_jvm", return_value=None),
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_path",
            return_value=Path("/opt/OpenRocket.jar"),
        ),
        patch(
            "rocketsmith.prusaslicer.utils.get_prusaslicer_path",
            return_value=Path("/usr/bin/prusa-slicer"),
        ),
    ):
        status = _check()

    assert status.ready is False
    assert status.java == "not found"


def test_check_openrocket_missing(monkeypatch):
    with (
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_jvm",
            return_value="/usr/bin/java",
        ),
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_path",
            side_effect=FileNotFoundError,
        ),
        patch(
            "rocketsmith.prusaslicer.utils.get_prusaslicer_path",
            return_value=Path("/usr/bin/prusa-slicer"),
        ),
    ):
        status = _check()

    assert status.ready is False
    assert status.openrocket == "not found"


def test_check_prusaslicer_missing():
    with (
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_jvm",
            return_value="/usr/bin/java",
        ),
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_path",
            return_value=Path("/opt/OpenRocket.jar"),
        ),
        patch(
            "rocketsmith.prusaslicer.utils.get_prusaslicer_path",
            side_effect=FileNotFoundError,
        ),
    ):
        status = _check()

    assert status.ready is False
    assert status.prusaslicer == "not found"


def test_check_ready_false_when_all_missing():
    with (
        patch("rocketsmith.openrocket.utils.get_openrocket_jvm", return_value=None),
        patch(
            "rocketsmith.openrocket.utils.get_openrocket_path",
            side_effect=FileNotFoundError,
        ),
        patch(
            "rocketsmith.prusaslicer.utils.get_prusaslicer_path",
            side_effect=FileNotFoundError,
        ),
    ):
        status = _check()

    assert status.ready is False


# ── _start_gui ────────────────────────────────────────────────────────────────


def test_start_gui_success(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mod, "_gui_teardown_registered", False)
    mock_start = MagicMock(
        return_value={"server_url": "http://localhost:5000", "pid": 1234}
    )
    with patch("rocketsmith.gui.lifecycle.start_gui_server", mock_start):
        url, pid, error = _start_gui(tmp_path)

    assert url == "http://localhost:5000"
    assert pid == 1234
    assert error is None


def test_start_gui_returns_error_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mod, "_gui_teardown_registered", False)
    mock_start = MagicMock(return_value={"error": "bundle not found", "pid": None})
    with patch("rocketsmith.gui.lifecycle.start_gui_server", mock_start):
        url, pid, error = _start_gui(tmp_path)

    assert url is None
    assert pid is None
    assert error == "bundle not found"


def test_start_gui_registers_atexit_once(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mod, "_gui_teardown_registered", False)
    mock_start = MagicMock(
        return_value={"server_url": "http://localhost:5000", "pid": 99}
    )

    with patch("rocketsmith.gui.lifecycle.start_gui_server", mock_start):
        with patch("atexit.register") as mock_atexit:
            _start_gui(tmp_path)
            _start_gui(tmp_path)

    assert mock_atexit.call_count == 1


# ── rocketsmith_setup (via register_setup) ────────────────────────────────────


@pytest.fixture
def setup_tool(monkeypatch):
    """Return the unwrapped rocketsmith_setup callable."""
    app = MagicMock()
    captured = {}

    def fake_tool(**kwargs):
        def decorator(fn):
            captured["fn"] = fn
            return fn

        return decorator

    app.tool = fake_tool
    register_setup(app)
    return captured["fn"]


def test_setup_check_no_project_dir(setup_tool, monkeypatch):
    with patch("rocketsmith.mcp.setup._check", return_value=_all_found_status()):
        status = setup_tool(action="check", project_dir=None)

    assert status.ready is True
    assert status.gui_url is None
    assert status.gui_pid is None
    assert status.gui_error is None


def test_setup_check_with_project_dir(tmp_path, setup_tool, monkeypatch):
    monkeypatch.setattr(setup_mod, "_gui_teardown_registered", False)

    import rocketsmith.mcp.utils as utils_mod

    rocketsmith_dir = tmp_path / ".rocketsmith"
    monkeypatch.setattr(utils_mod, "_ROCKETSMITH_DIR", rocketsmith_dir)
    monkeypatch.setattr(utils_mod, "_atexit_registered", False)

    mock_gui = MagicMock(return_value=("http://localhost:5000", 42, None))

    with (
        patch("rocketsmith.mcp.setup._check", return_value=_all_found_status()),
        patch("rocketsmith.mcp.setup._start_gui", mock_gui),
    ):
        status = setup_tool(action="check", project_dir=tmp_path)

    assert status.gui_url == "http://localhost:5000"
    assert status.gui_pid == 42
    assert status.gui_error is None


def test_setup_check_propagates_gui_error(tmp_path, setup_tool, monkeypatch):
    monkeypatch.setattr(setup_mod, "_gui_teardown_registered", False)

    import rocketsmith.mcp.utils as utils_mod

    rocketsmith_dir = tmp_path / ".rocketsmith"
    monkeypatch.setattr(utils_mod, "_ROCKETSMITH_DIR", rocketsmith_dir)
    monkeypatch.setattr(utils_mod, "_atexit_registered", False)

    mock_gui = MagicMock(return_value=(None, None, "bundle not found"))

    with (
        patch("rocketsmith.mcp.setup._check", return_value=_all_found_status()),
        patch("rocketsmith.mcp.setup._start_gui", mock_gui),
    ):
        status = setup_tool(action="check", project_dir=tmp_path)

    assert status.gui_url is None
    assert status.gui_error == "bundle not found"


def test_setup_install_calls_installers_when_missing(setup_tool, monkeypatch):
    missing = _missing_status()
    ready = _all_found_status()

    mock_install_or = MagicMock()
    mock_install_ps = MagicMock()

    with (
        patch("rocketsmith.mcp.setup._check", side_effect=[missing, ready]),
        patch("rocketsmith.openrocket.install.install", mock_install_or),
        patch("rocketsmith.prusaslicer.install.install", mock_install_ps),
    ):
        status = setup_tool(action="install", project_dir=None)

    mock_install_or.assert_called_once()
    mock_install_ps.assert_called_once()
    assert status.ready is True


def test_setup_install_skips_installers_when_all_present(setup_tool):
    found = _all_found_status()

    mock_install_or = MagicMock()
    mock_install_ps = MagicMock()

    with (
        patch("rocketsmith.mcp.setup._check", side_effect=[found, found]),
        patch("rocketsmith.openrocket.install.install", mock_install_or),
        patch("rocketsmith.prusaslicer.install.install", mock_install_ps),
    ):
        setup_tool(action="install", project_dir=None)

    mock_install_or.assert_not_called()
    mock_install_ps.assert_not_called()


def test_setup_install_only_installs_openrocket_when_prusaslicer_present(setup_tool):
    partial = _missing_status(
        prusaslicer="installed (/usr/bin/prusa-slicer)", ready=False
    )
    ready = _all_found_status()

    mock_install_or = MagicMock()
    mock_install_ps = MagicMock()

    with (
        patch("rocketsmith.mcp.setup._check", side_effect=[partial, ready]),
        patch("rocketsmith.openrocket.install.install", mock_install_or),
        patch("rocketsmith.prusaslicer.install.install", mock_install_ps),
    ):
        setup_tool(action="install", project_dir=None)

    mock_install_or.assert_called_once()
    mock_install_ps.assert_not_called()
