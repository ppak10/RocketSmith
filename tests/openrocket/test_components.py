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
    assert set(COMPONENT_TYPES) == {"nose-cone", "body-tube", "inner-tube", "transition", "fin-set", "parachute", "mass"}


def test_create_component_invalid_type_raises(tmp_path):
    """ValueError is raised before JVM startup for unknown component types."""
    with pytest.raises(ValueError, match="Unknown component type"):
        create_component(
            ork_path=tmp_path / "test.ork",
            component_type="laser-cannon",
            jar_path=tmp_path / "fake.jar",
        )


# ── Integration fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def tmp_ork(tmp_path, openrocket_jar):
    """Fresh empty .ork file for each test."""
    path = tmp_path / "test.ork"
    new_ork("Test Rocket", path, openrocket_jar)
    return path


# ── new_ork ───────────────────────────────────────────────────────────────────

def test_new_ork_creates_file(tmp_path, openrocket_jar):
    path = tmp_path / "my_rocket.ork"
    result = new_ork("My Rocket", path, openrocket_jar)
    assert result == path
    assert path.exists()
    assert path.stat().st_size > 0


def test_new_ork_has_rocket_and_stage(tmp_path, openrocket_jar):
    path = tmp_path / "test.ork"
    new_ork("TestRocket", path, openrocket_jar)
    components = inspect_ork(path, openrocket_jar)
    types = [c["type"] for c in components]
    assert "Rocket" in types
    assert "AxialStage" in types


# ── inspect_ork ───────────────────────────────────────────────────────────────

def test_inspect_example_ork(openrocket_jar):
    """inspect_ork returns a non-empty list starting with the Rocket root."""
    ork = DATA_DIR / "openrocket" / "example.ork"
    components = inspect_ork(ork, openrocket_jar)
    assert len(components) > 0
    assert components[0]["type"] == "Rocket"


def test_inspect_depth_field(tmp_ork, openrocket_jar):
    """Each entry in the component list carries a 'depth' field."""
    components = inspect_ork(tmp_ork, openrocket_jar)
    assert all("depth" in c for c in components)
    assert components[0]["depth"] == 0  # Rocket is at depth 0


# ── create_component ──────────────────────────────────────────────────────────

def test_create_nose_cone(tmp_ork, openrocket_jar):
    info = create_component(
        tmp_ork, "nose-cone", openrocket_jar,
        length=0.3, diameter=0.1, shape="ogive",
    )
    assert info["type"] == "NoseCone"
    assert abs(info["length_m"] - 0.3) < 1e-4
    assert info["shape"] == "ogive"

    types = [c["type"] for c in inspect_ork(tmp_ork, openrocket_jar)]
    assert "NoseCone" in types


def test_create_body_tube(tmp_ork, openrocket_jar):
    info = create_component(
        tmp_ork, "body-tube", openrocket_jar,
        length=0.6, diameter=0.1, thickness=0.002,
    )
    assert info["type"] == "BodyTube"
    assert abs(info["length_m"] - 0.6) < 1e-4
    assert abs(info["outer_diameter_m"] - 0.1) < 1e-4


def test_create_fin_set_requires_body_tube(tmp_ork, openrocket_jar):
    """Creating a fin set without a body tube raises ValueError."""
    with pytest.raises(ValueError, match="BodyTube"):
        create_component(
            tmp_ork, "fin-set", openrocket_jar,
            count=3, root_chord=0.1, tip_chord=0.05, span=0.08,
        )


def test_create_fin_set_after_body_tube(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, length=0.6, diameter=0.1)
    info = create_component(
        tmp_ork, "fin-set", openrocket_jar,
        count=3, root_chord=0.1, tip_chord=0.05, span=0.08,
    )
    assert info["type"] == "TrapezoidFinSet"
    assert info["fin_count"] == 3
    assert abs(info["root_chord_m"] - 0.1) < 1e-4
    assert abs(info["span_m"] - 0.08) < 1e-4


def test_create_parachute(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "body-tube", openrocket_jar, length=0.6, diameter=0.1)
    info = create_component(tmp_ork, "parachute", openrocket_jar, diameter=0.6, cd=1.5)
    assert info["type"] == "Parachute"
    assert abs(info["diameter_m"] - 0.6) < 1e-4
    assert abs(info["cd"] - 1.5) < 1e-3


def test_create_component_with_explicit_parent(tmp_ork, openrocket_jar):
    """Components can be added to a named parent."""
    create_component(tmp_ork, "body-tube", openrocket_jar, length=0.6, diameter=0.1, name="Main Tube")
    info = create_component(
        tmp_ork, "fin-set", openrocket_jar,
        parent="Main Tube", count=4, root_chord=0.08, tip_chord=0.04, span=0.06,
    )
    assert info["type"] == "TrapezoidFinSet"
    assert info["fin_count"] == 4


# ── read_component ────────────────────────────────────────────────────────────

def test_read_component(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "nose-cone", openrocket_jar, length=0.3, diameter=0.1, name="My Nose")
    info = read_component(tmp_ork, "My Nose", openrocket_jar)
    assert info["type"] == "NoseCone"
    assert info["name"] == "My Nose"
    assert abs(info["length_m"] - 0.3) < 1e-4


def test_read_component_not_found(tmp_ork, openrocket_jar):
    with pytest.raises(ValueError, match="not found"):
        read_component(tmp_ork, "Nonexistent Component", openrocket_jar)


# ── update_component ──────────────────────────────────────────────────────────

def test_update_component_length(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "nose-cone", openrocket_jar, length=0.3, diameter=0.1, name="Nose")
    info = update_component(tmp_ork, "Nose", openrocket_jar, length=0.35)
    assert abs(info["length_m"] - 0.35) < 1e-4


def test_update_component_name(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "nose-cone", openrocket_jar, length=0.3, name="Old Name")
    info = update_component(tmp_ork, "Old Name", openrocket_jar, name="New Name")
    assert info["name"] == "New Name"
    # Verify persisted
    updated = read_component(tmp_ork, "New Name", openrocket_jar)
    assert updated["name"] == "New Name"


def test_update_component_not_found(tmp_ork, openrocket_jar):
    with pytest.raises(ValueError, match="not found"):
        update_component(tmp_ork, "Ghost", openrocket_jar, length=0.5)


def test_update_preserves_other_properties(tmp_ork, openrocket_jar):
    """Updating one property does not change others."""
    create_component(tmp_ork, "nose-cone", openrocket_jar, length=0.3, diameter=0.1, name="Nose")
    info = update_component(tmp_ork, "Nose", openrocket_jar, length=0.35)
    assert abs(info["aft_diameter_m"] - 0.1) < 1e-4


# ── delete_component ──────────────────────────────────────────────────────────

def test_delete_component(tmp_ork, openrocket_jar):
    create_component(tmp_ork, "nose-cone", openrocket_jar, name="DeleteMe")
    deleted = delete_component(tmp_ork, "DeleteMe", openrocket_jar)
    assert deleted == "DeleteMe"
    # Verify gone from tree
    names = [c["name"] for c in inspect_ork(tmp_ork, openrocket_jar)]
    assert "DeleteMe" not in names


def test_delete_component_not_found(tmp_ork, openrocket_jar):
    with pytest.raises(ValueError, match="not found"):
        delete_component(tmp_ork, "NoSuchThing", openrocket_jar)


def test_delete_component_persists(tmp_ork, openrocket_jar):
    """Deletion is saved: a subsequent inspect confirms the component is gone."""
    create_component(tmp_ork, "nose-cone", openrocket_jar, name="Temp")
    delete_component(tmp_ork, "Temp", openrocket_jar)
    # Re-read the file from disk
    names = [c["name"] for c in inspect_ork(tmp_ork, openrocket_jar)]
    assert "Temp" not in names
