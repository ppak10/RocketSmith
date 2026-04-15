"""Tests for gui.lifecycle — start_gui_server and stop_gui_server."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rocketsmith.gui.lifecycle import (
    DEFAULT_PORT,
    start_gui_server,
    stop_gui_server,
)


# ── start_gui_server ─────────────────────────────────────────────────────────


def test_start_returns_error_when_gui_not_built(tmp_path, monkeypatch):
    """Returns error dict (no raise) when data/gui/ bundle is missing."""
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.check_existing_servers",
        lambda pid_file, host, ports: "none",
    )
    # Point __file__ to a location with no data/gui sibling so the bundle lookup fails.
    fake_lifecycle = tmp_path / "src" / "rocketsmith" / "gui" / "lifecycle.py"
    fake_lifecycle.parent.mkdir(parents=True)
    fake_lifecycle.touch()
    # data/gui intentionally NOT created here.
    import rocketsmith.gui.lifecycle as lc

    monkeypatch.setattr(lc, "__file__", str(fake_lifecycle))

    result = start_gui_server(tmp_path)
    assert result["error"] is not None
    assert result["pid"] is None


def test_start_reuses_healthy_server(tmp_path, monkeypatch):
    """Returns reused=True when a server is already running on the port."""
    pid_file = tmp_path / "gui" / ".gui.pid"
    pid_file.parent.mkdir(parents=True)
    pid_file.write_text("11111")

    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.check_existing_servers",
        lambda pid_file, host, ports: "healthy",
    )
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle._read_pid_file",
        lambda p: [11111],
    )

    result = start_gui_server(tmp_path)
    assert result["reused"] is True
    assert result["pid"] == 11111
    assert result["error"] is None


def test_start_port_conflict(tmp_path, monkeypatch):
    """Returns error dict when the port is taken by another process."""
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.check_existing_servers",
        lambda pid_file, host, ports: "port_conflict",
    )

    result = start_gui_server(tmp_path)
    assert result["error"] is not None
    assert "already in use" in result["error"]
    assert result["pid"] is None


def test_start_launches_server(tmp_path, monkeypatch):
    """Copies bundle, spawns backend, opens browser, writes PID file."""
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.check_existing_servers",
        lambda pid_file, host, ports: "none",
    )

    # Create a fake data/gui build directory adjacent to a fake lifecycle.py.
    fake_lifecycle = tmp_path / "src" / "rocketsmith" / "gui" / "lifecycle.py"
    fake_lifecycle.parent.mkdir(parents=True)
    fake_lifecycle.touch()
    gui_data_dir = tmp_path / "src" / "rocketsmith" / "data" / "gui"
    gui_data_dir.mkdir(parents=True)
    (gui_data_dir / "index.html").write_text("<html></html>")
    (gui_data_dir / "main.js").write_text("console.log('ok')")

    import rocketsmith.gui.lifecycle as lc

    monkeypatch.setattr(lc, "__file__", str(fake_lifecycle))
    monkeypatch.setattr("shutil.copy2", lambda src, dst: None)
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.Path.mkdir", lambda p, **kwargs: None
    )
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.Path.write_text", lambda p, text, **kwargs: None
    )

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)

    result = start_gui_server(tmp_path)

    assert result["error"] is None
    assert result["pid"] == 12345
    assert result["reused"] is False
    assert result["server_url"] == f"http://127.0.0.1:{DEFAULT_PORT}"
    assert len(opened) == 1


def test_start_uses_default_port(tmp_path, monkeypatch):
    """Default port is 24880."""
    monkeypatch.setattr("webbrowser.open", lambda url: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.check_existing_servers",
        lambda pid_file, host, ports: "none",
    )

    fake_lifecycle = tmp_path / "src" / "rocketsmith" / "gui" / "lifecycle.py"
    fake_lifecycle.parent.mkdir(parents=True)
    fake_lifecycle.touch()
    gui_data_dir = tmp_path / "src" / "rocketsmith" / "data" / "gui"
    gui_data_dir.mkdir(parents=True)
    (gui_data_dir / "index.html").write_text("<html></html>")
    (gui_data_dir / "main.js").write_text("console.log('ok')")

    import rocketsmith.gui.lifecycle as lc

    monkeypatch.setattr(lc, "__file__", str(fake_lifecycle))
    monkeypatch.setattr("shutil.copy2", lambda src, dst: None)
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.Path.mkdir", lambda p, **kwargs: None
    )
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle.Path.write_text", lambda p, text, **kwargs: None
    )

    mock_proc = MagicMock()
    mock_proc.pid = 12346
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)

    result = start_gui_server(tmp_path)
    assert result["server_url"] == "http://127.0.0.1:24880"
    assert result["pid"] == 12346


# ── stop_gui_server ──────────────────────────────────────────────────────────


def test_stop_kills_pids_from_pid_files(tmp_path, monkeypatch):
    """Reads both PID files and kills all listed processes."""
    killed = []
    monkeypatch.setattr(
        "rocketsmith.gui.lifecycle._kill_all_from_pid_file",
        lambda f: killed.append(str(f)) or [1, 2],
    )

    result = stop_gui_server(tmp_path)
    assert result == [1, 2, 1, 2]  # prod + dev PID files each return [1, 2]
    assert len(killed) == 2


def test_stop_returns_empty_when_no_servers(tmp_path):
    """Returns empty list when no PID files exist."""
    result = stop_gui_server(tmp_path)
    assert result == []
