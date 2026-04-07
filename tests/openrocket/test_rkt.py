import pytest
import os
from pathlib import Path

from rocketsmith.openrocket.components import (
    new_ork,
    inspect_rocket_file,
    create_component,
    read_component,
    update_component,
    delete_component,
    _or_context,
    _save_doc,
)

# ── .rkt (RockSim) support tests ──────────────────────────────────────────────


@pytest.fixture
def tmp_rkt(tmp_path, openrocket_jar):
    """
    Create a .rkt file for testing by loading a .ork and saving it with a .rkt extension.
    """
    ork_path = tmp_path / "test.ork"
    rkt_path = tmp_path / "test.rkt"

    # Create a base .ork file
    new_ork("Test RockSim", ork_path, openrocket_jar)

    # Load the document and save it as .rkt
    with _or_context(openrocket_jar) as instance:
        import orhelper

        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))
        _save_doc(doc, rkt_path)

    # Now add a component to the .rkt file to make it more interesting
    create_component(
        path=rkt_path,
        component_type="nose-cone",
        jar_path=openrocket_jar,
        name="MyNoseCone",
        length=0.2,
        diameter=0.05,
    )

    return rkt_path


def test_inspect_rkt_file(tmp_rkt, openrocket_jar):
    """inspect_rocket_file can read a .rkt file."""
    result = inspect_rocket_file(tmp_rkt, openrocket_jar)
    assert result["components"][0]["type"] == "Rocket"

    # Verify our added component is there
    names = [c["name"] for c in result["components"]]
    assert "MyNoseCone" in names


def test_read_component_rkt(tmp_rkt, openrocket_jar):
    """read_component works with .rkt files."""
    info = read_component(tmp_rkt, "MyNoseCone", openrocket_jar)
    assert info["name"] == "MyNoseCone"
    assert abs(info["length_m"] - 0.2) < 1e-4


def test_update_component_rkt(tmp_rkt, openrocket_jar):
    """update_component works with .rkt files."""
    update_component(
        path=tmp_rkt, component_name="MyNoseCone", jar_path=openrocket_jar, length=0.5
    )

    info = read_component(tmp_rkt, "MyNoseCone", openrocket_jar)
    assert abs(info["length_m"] - 0.5) < 1e-4


def test_delete_component_rkt(tmp_rkt, openrocket_jar):
    """delete_component works with .rkt files."""
    delete_component(tmp_rkt, "MyNoseCone", openrocket_jar)

    result = inspect_rocket_file(tmp_rkt, openrocket_jar)
    names = [c["name"] for c in result["components"]]
    assert "MyNoseCone" not in names
