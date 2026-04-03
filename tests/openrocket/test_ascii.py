import pytest
from rocketsmith.openrocket.ascii import render_rocket_ascii


@pytest.fixture
def sample_components():
    return [
        {
            "type": "NoseCone",
            "name": "Nose",
            "length_m": 0.2,
            "fore_diameter_m": 0.0,
            "aft_diameter_m": 0.1,
            "position_x_m": 0.0,
            "depth": 1,
        },
        {
            "type": "BodyTube",
            "name": "Body",
            "length_m": 0.8,
            "outer_diameter_m": 0.1,
            "inner_diameter_m": 0.09,
            "position_x_m": 0.2,
            "depth": 1,
        },
        {
            "type": "TubeCoupler",
            "name": "Coupler",
            "length_m": 0.1,
            "outer_diameter_m": 0.09,
            "inner_diameter_m": 0.08,
            "position_x_m": 0.5,
            "depth": 2,
        },
    ]


def test_render_rocket_ascii_basic(sample_components):
    """Test that the renderer returns a non-empty string with expected markers."""
    output = render_rocket_ascii(sample_components, width=100, cg_x=0.5, cp_x=0.7)

    assert isinstance(output, str)
    assert len(output) > 0
    assert "mm" in output
    assert "1000mm" in output
    assert "100mm" in output
    # Stability markers
    assert "(G)" in output
    assert "(P)" in output
    assert "Stability:" in output


def test_render_rocket_ascii_technical_callouts(sample_components):
    """Test that internal technical callouts (OD/ID) are present in the art."""
    output = render_rocket_ascii(sample_components, width=100)

    # Check for technical callout labels in the summary
    assert "OD: 100mm" in output
    assert "ID: 90mm" in output
    # Check for Coupler callout in the summary
    assert "OD: 90mm" in output
    assert "ID: 80mm" in output

    # Check for art callout characters
    assert "│" in output
    assert "^" in output
    assert "v" in output


def test_render_rocket_ascii_segment_ruler(sample_components):
    """Test that the segment ruler below the art correctly identifies components."""
    output = render_rocket_ascii(sample_components, width=100)

    # Check for segment names in the ruler area
    assert "Nose" in output
    assert "Body" in output
    # Coupler is depth 2, it might be in ruler depending on filtering
    # Our current logic picks c["depth"] == airframe_depth or (c["depth"] == airframe_depth + 1 and c["type"] == "TubeCoupler")
    assert "Coupler" in output


def test_render_rocket_ascii_aspect_ratio(sample_components):
    """Test that changing width affects the drawing but maintains readability."""
    narrow = render_rocket_ascii(sample_components, width=60)
    wide = render_rocket_ascii(sample_components, width=120)

    assert len(wide.splitlines()[0]) > len(narrow.splitlines()[0])
    assert "1000mm" in narrow
    assert "1000mm" in wide


def test_render_rocket_ascii_empty():
    """Test handling of empty component list."""
    assert render_rocket_ascii([]) == "(no renderable components)"


def test_render_rocket_ascii_no_body():
    """Test handling of components without a body."""
    components = [{"type": "Parachute", "name": "Chute", "position_x_m": 0.1}]
    assert render_rocket_ascii(components) == "(no renderable components)"
