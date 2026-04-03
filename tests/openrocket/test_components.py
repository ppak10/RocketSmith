import pytest

from rocketsmith.openrocket.components import (
    COMPONENT_TYPES,
    create_component,
    delete_component,
    inspect_ork,
    new_ork,
    read_component,
    update_component,
)
from rocketsmith.data import DATA_DIR


# ── Unit tests (no JAR required) ──────────────────────────────────────────────


def test_component_types_keys():
    """COMPONENT_TYPES contains exactly the expected CLI type names."""
    assert set(COMPONENT_TYPES) == {
        "nose-cone",
        "body-tube",
        "inner-tube",
        "transition",
        "tube-coupler",
        "fin-set",
        "parachute",
        "mass",
    }


def test_create_component_invalid_type_raises(tmp_path):
    """ValueError is raised before JVM startup for unknown component types."""
    with pytest.raises(ValueError, match="Unknown component type"):
        create_component(tmp_path / "test.ork", "not-a-type", None)


# ── Integration tests (requires OpenRocket JAR) ───────────────────────────────


def test_new_ork_creates_file(tmp_path, openrocket_jar):
    path = tmp_path / "test.ork"
    new_ork("TestRocket", path, openrocket_jar)
    assert path.exists()


def test_new_ork_has_rocket_and_stage(tmp_path, openrocket_jar):
    path = tmp_path / "test.ork"
    new_ork("TestRocket", path, openrocket_jar)
    result = inspect_ork(path, openrocket_jar)
    types = [c["type"] for c in result["components"]]
    assert "Rocket" in types
    assert "AxialStage" in types


@pytest.fixture
def tmp_ork(tmp_path, openrocket_jar):
    path = tmp_path / "test.ork"
    new_ork("Test Rocket", path, openrocket_jar)
    return path


# ── inspect_ork ───────────────────────────────────────────────────────────────


def test_inspect_example_ork(openrocket_jar):
    """inspect_ork returns a non-empty list starting with the Rocket root."""
    ork = DATA_DIR / "openrocket" / "example.ork"
    result = inspect_ork(ork, openrocket_jar)
    components = result["components"]
    assert len(components) > 0
    assert components[0]["type"] == "Rocket"


def test_inspect_depth_field(tmp_ork, openrocket_jar):
    """Each entry in the component list carries a 'depth' field."""
    result = inspect_ork(tmp_ork, openrocket_jar)
    assert all("depth" in c for c in result["components"])


# ── create_component ──────────────────────────────────────────────────────────


def test_create_nose_cone(tmp_ork, openrocket_jar):
    info = create_component(
        tmp_ork,
        "nose-cone",
        openrocket_jar,
        length=0.3,
        diameter=0.1,
        shape="ogive",
    )
    assert info["type"] == "NoseCone"
    assert abs(info["length_m"] - 0.3) < 1e-4
    assert info["shape"] == "ogive"

    result = inspect_ork(tmp_ork, openrocket_jar)
    types = [c["type"] for c in result["components"]]
    assert "NoseCone" in types


def test_create_body_tube(tmp_ork, openrocket_jar):
    info = create_component(
        tmp_ork,
        "body-tube",
        openrocket_jar,
        length=0.5,
        diameter=0.1,
        thickness=0.002,
    )
    assert info["type"] == "BodyTube"
    assert abs(info["length_m"] - 0.5) < 1e-4
    assert abs(info["outer_diameter_m"] - 0.1) < 1e-4


def test_create_fin_set_requires_body_tube(tmp_ork, openrocket_jar):
    """Creating a fin set without a body tube raises ValueError."""
    with pytest.raises(ValueError, match="expected BodyTube"):
        create_component(
            tmp_ork,
            "fin-set",
            openrocket_jar,
            count=3,
            root_chord=0.1,
            tip_chord=0.05,
            span=0.08,
        )


def test_create_fin_set_after_body_tube(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, name="BT")
    info = create_component(
        tmp_ork,
        "fin-set",
        openrocket_jar,
        parent="BT",
        count=4,
        root_chord=0.1,
        tip_chord=0.05,
        span=0.08,
    )
    assert info["type"] == "TrapezoidFinSet"
    assert info["fin_count"] == 4


def test_create_parachute(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, name="BT")
    info = create_component(
        tmp_ork,
        "parachute",
        openrocket_jar,
        parent="BT",
        diameter=0.5,
        cd=1.5,
    )
    assert info["type"] == "Parachute"
    assert abs(info["diameter_m"] - 0.5) < 1e-4


def test_create_component_with_explicit_parent(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, name="MainTube")
    info = create_component(
        tmp_ork,
        "fin-set",
        openrocket_jar,
        parent="MainTube",
        count=3,
        root_chord=0.1,
        tip_chord=0.05,
        span=0.08,
    )
    assert info["type"] == "TrapezoidFinSet"

    result = inspect_ork(tmp_ork, openrocket_jar)
    components = result["components"]
    # Find the fin set and its parent in the list
    fin_idx = next(
        i for i, c in enumerate(components) if c["type"] == "TrapezoidFinSet"
    )
    parent_idx = next(i for i, c in enumerate(components) if c["name"] == "MainTube")
    assert components[fin_idx]["depth"] == components[parent_idx]["depth"] + 1


# ── read_component ────────────────────────────────────────────────────────────


def test_read_component(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, name="Target")
    info = read_component(tmp_ork, "Target", openrocket_jar)
    assert info["name"] == "Target"
    assert info["type"] == "BodyTube"


def test_read_component_not_found(tmp_ork, openrocket_jar):
    with pytest.raises(ValueError, match="not found"):
        read_component(tmp_ork, "Missing", openrocket_jar)


# ── update_component ──────────────────────────────────────────────────────────


def test_update_component_length(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, name="BT", length=0.2)
    info = update_component(tmp_ork, "BT", openrocket_jar, length=0.5)
    assert abs(info["length_m"] - 0.5) < 1e-4


def test_update_component_name(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, name="OldName")
    info = update_component(tmp_ork, "OldName", openrocket_jar, name="NewName")
    assert info["name"] == "NewName"


def test_update_component_not_found(tmp_ork, openrocket_jar):
    with pytest.raises(ValueError, match="not found"):
        update_component(tmp_ork, "Missing", openrocket_jar, length=0.5)


def test_update_preserves_other_properties(tmp_ork, openrocket_jar):
    create_component(
        tmp_ork, "body-tube", openrocket_jar, name="BT", length=0.2, diameter=0.05
    )
    update_component(tmp_ork, "BT", openrocket_jar, length=0.3)
    info = read_component(tmp_ork, "BT", openrocket_jar)
    assert abs(info["length_m"] - 0.3) < 1e-4
    assert abs(info["outer_diameter_m"] - 0.05) < 1e-4


# ── delete_component ──────────────────────────────────────────────────────────


def test_delete_component(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "nose-cone", openrocket_jar, name="DeleteMe")
    deleted = delete_component(tmp_ork, "DeleteMe", openrocket_jar)
    assert deleted == "DeleteMe"
    # Verify gone from tree
    result = inspect_ork(tmp_ork, openrocket_jar)
    names = [c["name"] for c in result["components"]]
    assert "DeleteMe" not in names


def test_delete_component_not_found(tmp_ork, openrocket_jar):
    with pytest.raises(ValueError, match="not found"):
        delete_component(tmp_ork, "Missing", openrocket_jar)


def test_delete_component_persists(tmp_ork, openrocket_jar):
    """Deletion is saved: a subsequent inspect confirms the component is gone."""
    create_component(tmp_ork, "nose-cone", openrocket_jar, name="Temp")
    delete_component(tmp_ork, "Temp", openrocket_jar)
    # Re-read the file from disk
    result = inspect_ork(tmp_ork, openrocket_jar)
    names = [c["name"] for c in result["components"]]
    assert "Temp" not in names
