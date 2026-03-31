import pytest

from rocketsmith.openrocket.database import (
    PRESET_TYPES,
    MATERIAL_TYPES,
    list_motors,
    list_presets,
    list_materials,
)


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


def test_preset_types_keys():
    assert "body-tube" in PRESET_TYPES
    assert "nose-cone" in PRESET_TYPES
    assert "parachute" in PRESET_TYPES
    assert len(PRESET_TYPES) == 11


def test_material_types():
    assert MATERIAL_TYPES == {"bulk", "surface", "line"}


def test_list_presets_invalid_type_raises(tmp_path):
    with pytest.raises(ValueError, match="Unknown preset type"):
        list_presets(tmp_path / "fake.jar", "laser-cannon")


def test_list_materials_invalid_type_raises(tmp_path):
    with pytest.raises(ValueError, match="Unknown material type"):
        list_materials(tmp_path / "fake.jar", "plasma")


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


def test_list_motors_returns_results(openrocket_jar):
    motors = list_motors(openrocket_jar)
    assert len(motors) > 0


def test_list_motors_result_fields(openrocket_jar):
    motors = list_motors(openrocket_jar)
    m = motors[0]
    assert "manufacturer" in m
    assert "common_name" in m
    assert "type" in m
    assert "diameter_mm" in m
    assert "length_mm" in m
    assert "total_impulse_ns" in m
    assert "avg_thrust_n" in m
    assert "burn_time_s" in m
    assert "variant_count" in m


def test_list_motors_filter_by_manufacturer(openrocket_jar):
    motors = list_motors(openrocket_jar, manufacturer="Estes")
    assert len(motors) > 0
    assert all("Estes" in m["manufacturer"] for m in motors)


def test_list_motors_filter_by_impulse_class(openrocket_jar):
    motors = list_motors(openrocket_jar, impulse_class="D")
    assert len(motors) > 0
    assert all(m["common_name"].upper().startswith("D") for m in motors)


def test_list_motors_filter_by_diameter(openrocket_jar):
    motors = list_motors(openrocket_jar, diameter_mm=18.0)
    assert len(motors) > 0
    assert all(abs(m["diameter_mm"] - 18.0) <= 0.5 for m in motors)


def test_list_motors_filter_no_results(openrocket_jar):
    motors = list_motors(openrocket_jar, manufacturer="NoSuchManufacturerXYZ")
    assert motors == []


def test_list_presets_body_tube(openrocket_jar):
    presets = list_presets(openrocket_jar, "body-tube")
    assert len(presets) > 0
    assert all(p["type"] == "body-tube" for p in presets)


def test_list_presets_body_tube_fields(openrocket_jar):
    presets = list_presets(openrocket_jar, "body-tube")
    p = presets[0]
    assert "manufacturer" in p
    assert "part_no" in p
    assert "outer_diameter_m" in p
    assert "length_m" in p


def test_list_presets_parachute(openrocket_jar):
    presets = list_presets(openrocket_jar, "parachute")
    assert len(presets) > 0
    assert all("diameter_m" in p for p in presets)


def test_list_presets_filter_by_manufacturer(openrocket_jar):
    presets = list_presets(openrocket_jar, "body-tube", manufacturer="Estes")
    assert len(presets) > 0
    assert all("Estes" in p["manufacturer"] for p in presets)


def test_list_presets_filter_no_results(openrocket_jar):
    presets = list_presets(openrocket_jar, "parachute", manufacturer="NoSuchMfr")
    assert presets == []


def test_list_materials_bulk(openrocket_jar):
    materials = list_materials(openrocket_jar, "bulk")
    assert len(materials) > 0
    names = [m["name"] for m in materials]
    assert "Aluminum" in names
    assert all(m["type"] == "bulk" for m in materials)


def test_list_materials_surface(openrocket_jar):
    materials = list_materials(openrocket_jar, "surface")
    assert len(materials) > 0
    assert all(m["type"] == "surface" for m in materials)


def test_list_materials_line(openrocket_jar):
    materials = list_materials(openrocket_jar, "line")
    assert len(materials) > 0
    assert all(m["type"] == "line" for m in materials)


def test_list_materials_sorted(openrocket_jar):
    materials = list_materials(openrocket_jar, "bulk")
    names = [m["name"] for m in materials]
    assert names == sorted(names)
