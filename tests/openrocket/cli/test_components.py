import pytest

from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


@pytest.fixture
def mock_workspace(tmp_path):
    """A mock workspace whose openrocket/ folder exists but is empty."""
    (tmp_path / "openrocket").mkdir()
    ws = MagicMock()
    ws.path = tmp_path
    return ws


# ── inspect ───────────────────────────────────────────────────────────────────

def test_inspect_no_jar(runner, mock_workspace):
    with (
        patch("rocketsmith.openrocket.cli.inspect.get_openrocket_path", side_effect=FileNotFoundError("not found")),
        patch("rocketsmith.openrocket.cli.inspect.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["inspect", "test.ork"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_inspect_ork_not_found(runner, tmp_path, mock_workspace):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with (
        patch("rocketsmith.openrocket.cli.inspect.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.inspect.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["inspect", "missing.ork"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── new ───────────────────────────────────────────────────────────────────────

def test_new_no_jar(runner, mock_workspace):
    with (
        patch("rocketsmith.openrocket.cli.new.get_openrocket_path", side_effect=FileNotFoundError("not found")),
        patch("rocketsmith.openrocket.cli.new.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["new", "my_rocket"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_new_file_already_exists(runner, tmp_path, mock_workspace):
    jar = tmp_path / "fake.jar"
    jar.touch()
    (mock_workspace.path / "openrocket" / "my_rocket.ork").touch()
    with (
        patch("rocketsmith.openrocket.cli.new.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.new.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["new", "my_rocket"])
    assert result.exit_code == 1
    assert "already exists" in result.stdout.lower()


# ── read-component ────────────────────────────────────────────────────────────

def test_read_component_no_jar(runner, mock_workspace):
    with (
        patch("rocketsmith.openrocket.cli.read_component.get_openrocket_path", side_effect=FileNotFoundError("not found")),
        patch("rocketsmith.openrocket.cli.read_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["read-component", "test.ork", "Nose cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_read_component_ork_not_found(runner, tmp_path, mock_workspace):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with (
        patch("rocketsmith.openrocket.cli.read_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.read_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["read-component", "missing.ork", "Nose cone"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── create-component ──────────────────────────────────────────────────────────

def test_create_component_no_jar(runner, mock_workspace):
    with (
        patch("rocketsmith.openrocket.cli.create_component.get_openrocket_path", side_effect=FileNotFoundError("not found")),
        patch("rocketsmith.openrocket.cli.create_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["create-component", "test.ork", "nose-cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_create_component_ork_not_found(runner, tmp_path, mock_workspace):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with (
        patch("rocketsmith.openrocket.cli.create_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.create_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["create-component", "missing.ork", "nose-cone"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── update-component ──────────────────────────────────────────────────────────

def test_update_component_no_jar(runner, mock_workspace):
    with (
        patch("rocketsmith.openrocket.cli.update_component.get_openrocket_path", side_effect=FileNotFoundError("not found")),
        patch("rocketsmith.openrocket.cli.update_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["update-component", "test.ork", "Nose cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_update_component_ork_not_found(runner, tmp_path, mock_workspace):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with (
        patch("rocketsmith.openrocket.cli.update_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.update_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["update-component", "missing.ork", "Nose cone"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── delete-component ──────────────────────────────────────────────────────────

def test_delete_component_no_jar(runner, mock_workspace):
    with (
        patch("rocketsmith.openrocket.cli.delete_component.get_openrocket_path", side_effect=FileNotFoundError("not found")),
        patch("rocketsmith.openrocket.cli.delete_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["delete-component", "test.ork", "Nose cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_delete_component_ork_not_found(runner, tmp_path, mock_workspace):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with (
        patch("rocketsmith.openrocket.cli.delete_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.delete_component.get_workspace", return_value=mock_workspace),
    ):
        result = runner.invoke(app, ["delete-component", "missing.ork", "Nose cone"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── Integration ───────────────────────────────────────────────────────────────

@pytest.fixture
def workspace_with_ork(tmp_path, openrocket_jar):
    """Workspace containing a fresh empty .ork, used for CLI integration tests."""
    from rocketsmith.openrocket.components import new_ork

    ork_dir = tmp_path / "openrocket"
    ork_dir.mkdir()
    new_ork("Test Rocket", ork_dir / "test.ork", openrocket_jar)

    ws = MagicMock()
    ws.path = tmp_path
    return ws, openrocket_jar


def test_cli_new_creates_file_and_inspect_shows_tree(runner, tmp_path, openrocket_jar):
    ws = MagicMock()
    ws.path = tmp_path
    (tmp_path / "openrocket").mkdir()

    with (
        patch("rocketsmith.openrocket.cli.new.get_openrocket_path", return_value=openrocket_jar),
        patch("rocketsmith.openrocket.cli.new.get_workspace", return_value=ws),
    ):
        result = runner.invoke(app, ["new", "my_rocket"])
    assert result.exit_code == 0
    assert "✅" in result.stdout

    with (
        patch("rocketsmith.openrocket.cli.inspect.get_openrocket_path", return_value=openrocket_jar),
        patch("rocketsmith.openrocket.cli.inspect.get_workspace", return_value=ws),
    ):
        result = runner.invoke(app, ["inspect", "my_rocket.ork"])
    assert result.exit_code == 0
    assert "Rocket" in result.stdout
    assert "AxialStage" in result.stdout


def test_cli_create_component(runner, workspace_with_ork):
    ws, jar = workspace_with_ork
    with (
        patch("rocketsmith.openrocket.cli.create_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.create_component.get_workspace", return_value=ws),
    ):
        result = runner.invoke(app, [
            "create-component", "test.ork", "nose-cone",
            "--name", "TestNose", "--length", "0.3", "--diameter", "0.1",
        ])
    assert result.exit_code == 0
    assert "NoseCone" in result.stdout
    assert "✅" in result.stdout


def test_cli_read_component(runner, workspace_with_ork):
    ws, jar = workspace_with_ork
    # First create the component
    with (
        patch("rocketsmith.openrocket.cli.create_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.create_component.get_workspace", return_value=ws),
    ):
        runner.invoke(app, ["create-component", "test.ork", "nose-cone", "--name", "ReadMe", "--length", "0.3"])

    with (
        patch("rocketsmith.openrocket.cli.read_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.read_component.get_workspace", return_value=ws),
    ):
        result = runner.invoke(app, ["read-component", "test.ork", "ReadMe"])
    assert result.exit_code == 0
    assert "NoseCone" in result.stdout


def test_cli_update_component(runner, workspace_with_ork):
    ws, jar = workspace_with_ork
    with (
        patch("rocketsmith.openrocket.cli.create_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.create_component.get_workspace", return_value=ws),
    ):
        runner.invoke(app, ["create-component", "test.ork", "nose-cone", "--name", "UpdateMe", "--length", "0.3"])

    with (
        patch("rocketsmith.openrocket.cli.update_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.update_component.get_workspace", return_value=ws),
    ):
        result = runner.invoke(app, ["update-component", "test.ork", "UpdateMe", "--length", "0.4"])
    assert result.exit_code == 0
    assert "0.4" in result.stdout


def test_cli_delete_component(runner, workspace_with_ork):
    ws, jar = workspace_with_ork
    with (
        patch("rocketsmith.openrocket.cli.create_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.create_component.get_workspace", return_value=ws),
    ):
        runner.invoke(app, ["create-component", "test.ork", "nose-cone", "--name", "DeleteMe"])

    with (
        patch("rocketsmith.openrocket.cli.delete_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.delete_component.get_workspace", return_value=ws),
    ):
        result = runner.invoke(app, ["delete-component", "test.ork", "DeleteMe"])
    assert result.exit_code == 0
    assert "DeleteMe" in result.stdout
    assert "✅" in result.stdout


def test_cli_read_component_not_found(runner, workspace_with_ork):
    ws, jar = workspace_with_ork
    with (
        patch("rocketsmith.openrocket.cli.read_component.get_openrocket_path", return_value=jar),
        patch("rocketsmith.openrocket.cli.read_component.get_workspace", return_value=ws),
    ):
        result = runner.invoke(app, ["read-component", "test.ork", "NoSuchComponent"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout
