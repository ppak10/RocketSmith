"""Tests for rocketsmith.mcp.__main__.main() exit-code behaviour.

The server runs over stdio; clean exit (0) on transport errors prevents the
MCP client from treating a normal disconnection as a crash.
"""

import pytest
import rocketsmith.mcp.__main__ as mcp_main


def test_broken_pipe_exits_cleanly(monkeypatch):
    """BrokenPipeError (stdio transport closed) exits with code 0."""
    monkeypatch.setattr(
        mcp_main.app, "run", lambda: (_ for _ in ()).throw(BrokenPipeError())
    )
    with pytest.raises(SystemExit) as exc_info:
        mcp_main.main()
    assert exc_info.value.code == 0


def test_eof_error_exits_cleanly(monkeypatch):
    """EOFError (stdin exhausted) exits with code 0."""
    monkeypatch.setattr(mcp_main.app, "run", lambda: (_ for _ in ()).throw(EOFError()))
    with pytest.raises(SystemExit) as exc_info:
        mcp_main.main()
    assert exc_info.value.code == 0


def test_unexpected_exception_exits_with_error(monkeypatch, capsys):
    """An unexpected exception exits with code 1 and prints to stderr."""
    monkeypatch.setattr(
        mcp_main.app,
        "run",
        lambda: (_ for _ in ()).throw(RuntimeError("something went wrong")),
    )
    with pytest.raises(SystemExit) as exc_info:
        mcp_main.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err
    assert "something went wrong" in captured.err


def test_clean_run_does_not_exit(monkeypatch):
    """Normal app.run() return does not call sys.exit."""
    monkeypatch.setattr(mcp_main.app, "run", lambda: None)
    # Should return normally without raising SystemExit.
    mcp_main.main()
