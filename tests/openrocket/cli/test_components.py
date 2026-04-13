import pytest

from unittest.mock import patch
from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


# ── inspect ───────────────────────────────────────────────────────────────────


def test_inspect_no_jar(runner, tmp_path):
    p = tmp_path / "test.ork"
    p.touch()
    with patch(
        "rocketsmith.openrocket.cli.inspect.get_openrocket_path",
        side_effect=FileNotFoundError("not found"),
    ):
        result = runner.invoke(app, ["inspect", str(p)])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_inspect_ork_not_found(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with patch(
        "rocketsmith.openrocket.cli.inspect.get_openrocket_path", return_value=jar
    ):
        result = runner.invoke(app, ["inspect", str(tmp_path / "missing.ork")])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── new ───────────────────────────────────────────────────────────────────────


def test_new_no_jar(runner, tmp_path):
    with patch(
        "rocketsmith.openrocket.cli.new.get_openrocket_path",
        side_effect=FileNotFoundError("not found"),
    ):
        result = runner.invoke(
            app, ["new", "my_rocket", "--out", str(tmp_path / "my_rocket.ork")]
        )
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_new_file_already_exists(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    existing = tmp_path / "my_rocket.ork"
    existing.touch()
    with patch("rocketsmith.openrocket.cli.new.get_openrocket_path", return_value=jar):
        result = runner.invoke(app, ["new", "my_rocket", "--out", str(existing)])
    assert result.exit_code == 1
    assert "already exists" in result.stdout.lower()


# ── read-component ────────────────────────────────────────────────────────────


def test_read_component_no_jar(runner, tmp_path):
    p = tmp_path / "test.ork"
    p.touch()
    with patch(
        "rocketsmith.openrocket.cli.read_component.get_openrocket_path",
        side_effect=FileNotFoundError("not found"),
    ):
        result = runner.invoke(app, ["read-component", str(p), "Nose cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_read_component_ork_not_found(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with patch(
        "rocketsmith.openrocket.cli.read_component.get_openrocket_path",
        return_value=jar,
    ):
        result = runner.invoke(
            app, ["read-component", str(tmp_path / "missing.ork"), "Nose cone"]
        )
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── create-component ──────────────────────────────────────────────────────────


def test_create_component_no_jar(runner, tmp_path):
    p = tmp_path / "test.ork"
    p.touch()
    with patch(
        "rocketsmith.openrocket.cli.create_component.get_openrocket_path",
        side_effect=FileNotFoundError("not found"),
    ):
        result = runner.invoke(app, ["create-component", str(p), "nose-cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_create_component_ork_not_found(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with patch(
        "rocketsmith.openrocket.cli.create_component.get_openrocket_path",
        return_value=jar,
    ):
        result = runner.invoke(
            app, ["create-component", str(tmp_path / "missing.ork"), "nose-cone"]
        )
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── update-component ──────────────────────────────────────────────────────────


def test_update_component_no_jar(runner, tmp_path):
    p = tmp_path / "test.ork"
    p.touch()
    with patch(
        "rocketsmith.openrocket.cli.update_component.get_openrocket_path",
        side_effect=FileNotFoundError("not found"),
    ):
        result = runner.invoke(app, ["update-component", str(p), "Nose cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_update_component_ork_not_found(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with patch(
        "rocketsmith.openrocket.cli.update_component.get_openrocket_path",
        return_value=jar,
    ):
        result = runner.invoke(
            app, ["update-component", str(tmp_path / "missing.ork"), "Nose cone"]
        )
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── delete-component ──────────────────────────────────────────────────────────


def test_delete_component_no_jar(runner, tmp_path):
    p = tmp_path / "test.ork"
    p.touch()
    with patch(
        "rocketsmith.openrocket.cli.delete_component.get_openrocket_path",
        side_effect=FileNotFoundError("not found"),
    ):
        result = runner.invoke(app, ["delete-component", str(p), "Nose cone"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


def test_delete_component_ork_not_found(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()
    with patch(
        "rocketsmith.openrocket.cli.delete_component.get_openrocket_path",
        return_value=jar,
    ):
        result = runner.invoke(
            app, ["delete-component", str(tmp_path / "missing.ork"), "Nose cone"]
        )
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


# ── Integration ───────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_ork(tmp_path, openrocket_jar):
    from rocketsmith.openrocket.components import new_ork

    path = tmp_path / "test.ork"
    new_ork("Test Rocket", path, openrocket_jar)
    return path


def test_cli_new_creates_file_and_inspect_shows_tree(runner, tmp_path, openrocket_jar):
    out = tmp_path / "my_rocket.ork"
    result = runner.invoke(
        app,
        [
            "new",
            "my_rocket",
            "--out",
            str(out),
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    assert result.exit_code == 0
    assert "✅" in result.stdout

    result = runner.invoke(
        app, ["inspect", str(out), "--openrocket-path", str(openrocket_jar)]
    )
    assert result.exit_code == 0
    assert "Rocket" in result.stdout
    assert "AxialStage" in result.stdout


def test_cli_create_component(runner, tmp_ork, openrocket_jar):
    result = runner.invoke(
        app,
        [
            "create-component",
            str(tmp_ork),
            "nose-cone",
            "--name",
            "TestNose",
            "--length",
            "0.3",
            "--diameter",
            "0.1",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    assert result.exit_code == 0
    assert "NoseCone" in result.stdout
    assert "✅" in result.stdout


def test_cli_read_component(runner, tmp_ork, openrocket_jar):
    runner.invoke(
        app,
        [
            "create-component",
            str(tmp_ork),
            "nose-cone",
            "--name",
            "ReadMe",
            "--length",
            "0.3",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    result = runner.invoke(
        app,
        [
            "read-component",
            str(tmp_ork),
            "ReadMe",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    assert result.exit_code == 0
    assert "NoseCone" in result.stdout


def test_cli_update_component(runner, tmp_ork, openrocket_jar):
    runner.invoke(
        app,
        [
            "create-component",
            str(tmp_ork),
            "nose-cone",
            "--name",
            "UpdateMe",
            "--length",
            "0.3",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    result = runner.invoke(
        app,
        [
            "update-component",
            str(tmp_ork),
            "UpdateMe",
            "--length",
            "0.4",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    assert result.exit_code == 0
    assert "0.4" in result.stdout


def test_cli_delete_component(runner, tmp_ork, openrocket_jar):
    runner.invoke(
        app,
        [
            "create-component",
            str(tmp_ork),
            "nose-cone",
            "--name",
            "DeleteMe",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    result = runner.invoke(
        app,
        [
            "delete-component",
            str(tmp_ork),
            "DeleteMe",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    assert result.exit_code == 0
    assert "DeleteMe" in result.stdout
    assert "✅" in result.stdout


def test_cli_read_component_not_found(runner, tmp_ork, openrocket_jar):
    result = runner.invoke(
        app,
        [
            "read-component",
            str(tmp_ork),
            "NoSuchComponent",
            "--openrocket-path",
            str(openrocket_jar),
        ],
    )
    assert result.exit_code == 1
    assert "⚠️" in result.stdout
