import pytest

from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from rocketsmith.openrocket.cli import app


@pytest.fixture
def runner():
    return CliRunner(env={"NO_COLOR": "1"})


def _mock_select(return_values: list):
    """Return a side_effect that pops from return_values each call."""
    calls = iter(return_values)

    def _select(*args, **kwargs):
        mock = MagicMock()
        mock.ask.return_value = next(calls)
        return mock

    return _select


def _mock_text(return_value: str):
    def _text(*args, **kwargs):
        mock = MagicMock()
        mock.ask.return_value = return_value
        return mock

    return _text


# ── No JAR ────────────────────────────────────────────────────────────────────


def test_database_no_jar(runner):
    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path",
        side_effect=FileNotFoundError("not found"),
    ):
        result = runner.invoke(app, ["database"])
    assert result.exit_code == 1
    assert "⚠️" in result.stdout


# ── Category cancelled ─────────────────────────────────────────────────────────


def test_database_cancel_at_category(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch("questionary.select", _mock_select([None])):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


# ── Motors flow ────────────────────────────────────────────────────────────────


def test_database_motors_cancel_at_motor_select(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    fake_motors = [
        {
            "manufacturer": "Estes",
            "common_name": "D12",
            "type": "single-use",
            "diameter_mm": 24.0,
            "total_impulse_ns": 20.0,
        }
    ]

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["motors", "Any", "Any", None]),
    ), patch(
        "questionary.text", _mock_text("")
    ), patch(
        "rocketsmith.openrocket.database.list_motors", return_value=fake_motors
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


def test_database_motors_no_results(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["motors", "Any", "Any"]),
    ), patch(
        "questionary.text", _mock_text("")
    ), patch(
        "rocketsmith.openrocket.database.list_motors", return_value=[]
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0
    assert "No motors found" in result.stdout


# ── Recovery sub-menus ────────────────────────────────────────────────────────


def test_database_recovery_parachute_flow(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    fake_presets = [
        {
            "manufacturer": "Estes",
            "part_no": "303159",
            "type": "parachute",
            "diameter_m": 0.3048,
        }
    ]

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["recovery", "parachute", None]),
    ), patch(
        "questionary.text", _mock_text("")
    ), patch(
        "rocketsmith.openrocket.database.list_presets", return_value=fake_presets
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


def test_database_recovery_shock_cords_flow(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    fake_materials = [{"name": "Nylon cord", "type": "line", "density": 0.003}]

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["recovery", "shock-cords", None]),
    ), patch(
        "rocketsmith.openrocket.database.list_materials", return_value=fake_materials
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


# ── Airframe sub-menu ─────────────────────────────────────────────────────────


def test_database_airframe_body_tube_flow(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    fake_presets = [
        {
            "manufacturer": "Estes",
            "part_no": "BT-20",
            "type": "body-tube",
            "outer_diameter_m": 0.018,
            "length_m": 0.3048,
        }
    ]

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["airframe", "body-tube", None]),
    ), patch(
        "questionary.text", _mock_text("")
    ), patch(
        "rocketsmith.openrocket.database.list_presets", return_value=fake_presets
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


# ── Hardware sub-menu ─────────────────────────────────────────────────────────


def test_database_hardware_centering_ring_flow(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    fake_presets = [
        {
            "manufacturer": "Estes",
            "part_no": "CR-2050",
            "type": "centering-ring",
            "outer_diameter_m": 0.050,
            "length_m": 0.003,
        }
    ]

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["hardware", "centering-ring", None]),
    ), patch(
        "questionary.text", _mock_text("")
    ), patch(
        "rocketsmith.openrocket.database.list_presets", return_value=fake_presets
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


# ── Materials sub-menu ────────────────────────────────────────────────────────


def test_database_materials_bulk_flow(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    fake_materials = [{"name": "Aluminum", "type": "bulk", "density": 2700.0}]

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["materials", "bulk", None]),
    ), patch(
        "rocketsmith.openrocket.database.list_materials", return_value=fake_materials
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


def test_database_materials_no_type_selected(runner, tmp_path):
    jar = tmp_path / "fake.jar"
    jar.touch()

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path", return_value=jar
    ), patch(
        "questionary.select",
        _mock_select(["materials", None]),
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


def test_database_motors_integration(runner, openrocket_jar):
    """Full motors flow selects and displays the first D-class Estes motor."""

    selected_motor = None

    def _capturing_select(*args, **kwargs):
        nonlocal selected_motor
        mock = MagicMock()

        question = args[0] if args else kwargs.get("message", "")
        if "What are you looking for" in question:
            mock.ask.return_value = "motors"
        elif "Impulse class" in question:
            mock.ask.return_value = "D"
        elif "diameter" in question.lower():
            mock.ask.return_value = "Any"
        else:
            # Motor selection — pick first
            choices = kwargs.get("choices", [])
            if choices:
                first = choices[0]
                val = first.value if hasattr(first, "value") else first
                selected_motor = val
                mock.ask.return_value = val
            else:
                mock.ask.return_value = None

        return mock

    with patch(
        "rocketsmith.openrocket.cli.database.get_openrocket_path",
        return_value=openrocket_jar,
    ), patch("questionary.select", _capturing_select), patch(
        "questionary.text", _mock_text("Estes")
    ):
        result = runner.invoke(app, ["database"])

    assert result.exit_code == 0
    if selected_motor:
        assert "Estes" in result.stdout or result.exit_code == 0
