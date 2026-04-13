"""Tests for DFAM annotation logic.

Unit tests verify the translation rules against a ComponentTree,
skipping the OpenRocket JAR dependency. Integration tests round-trip
through a real .ork file using openrocket_generate_tree.
"""

import pytest
from pathlib import Path

from rocketsmith.manufacturing.dfam import (
    _sanitize_name,
    annotate_dfam,
)
from rocketsmith.manufacturing.models import (
    Component,
    ComponentTree,
    Fate,
    Stage,
)
from rocketsmith.openrocket.models import (
    TubeDimensions,
    NoseConeDimensions,
    FinSetDimensions,
)


# ── Unit tests (no JVM required) ──────────────────────────────────────────────


class TestSanitizeName:
    def test_snake_case_simple(self):
        assert _sanitize_name("Nose Cone") == "nose_cone"

    def test_snake_case_multi_word(self):
        assert _sanitize_name("Upper Airframe Section") == "upper_airframe_section"

    def test_converts_hyphens_to_underscores(self):
        assert _sanitize_name("BT-20 Body") == "bt_20_body"

    def test_collapses_whitespace(self):
        assert _sanitize_name("Nose   Cone") == "nose_cone"

    def test_empty_string_returns_placeholder(self):
        assert _sanitize_name("") == "unnamed"

    def test_strips_leading_trailing_whitespace(self):
        assert _sanitize_name("  Upper  ") == "upper"


@pytest.fixture
def minimal_tree(tmp_path):
    """Build a minimal ComponentTree with nose cone and body tube."""
    return ComponentTree(
        source_ork="test.ork",
        project_root=str(tmp_path),
        rocket_name="TestRocket",
        stages=[
            Stage(
                name="Sustainer",
                components=[
                    Component(
                        type="NoseCone",
                        name="Nose Cone",
                        category="structural",
                        dimensions=NoseConeDimensions(
                            shape="ogive",
                            length=120.0,
                            base_od=64.0,
                        ),
                    ),
                    Component(
                        type="BodyTube",
                        name="Upper Airframe",
                        category="structural",
                        dimensions=TubeDimensions(
                            length=400.0,
                            od=64.0,
                            id=60.0,
                        ),
                    ),
                ],
            )
        ],
    )


class TestAnnotationLogic:
    def test_nose_cone_always_print(self, minimal_tree):
        annotated = annotate_dfam(minimal_tree)
        nc = annotated.stages[0].components[0]
        assert nc.type == "NoseCone"
        assert nc.agent.fate == Fate.PRINT
        assert nc.agent.dfam_shoulder_length_mm == 30.0
        assert nc.agent.dfam_shoulder_od_mm == 60.0

    def test_body_tube_always_print(self, minimal_tree):
        annotated = annotate_dfam(minimal_tree)
        bt = annotated.stages[0].components[1]
        assert bt.type == "BodyTube"
        assert bt.agent.fate == Fate.PRINT

    def test_fins_are_fused(self, minimal_tree):
        # Add a fin set as a child of the body tube
        minimal_tree.stages[0].components[1].children.append(
            Component(
                type="TrapezoidFinSet",
                name="Fins",
                category="structural",
                dimensions=FinSetDimensions(
                    root_chord=80.0,
                    tip_chord=40.0,
                    span=60.0,
                    thickness=3.0,
                ),
            )
        )
        annotated = annotate_dfam(minimal_tree)
        bt = annotated.stages[0].components[1]
        fin = bt.children[0]
        assert fin.type == "TrapezoidFinSet"
        assert fin.agent.fate == Fate.FUSE
        assert fin.agent.fused_into == "upper_airframe"
        # Thickness should be bumped to minimum 12.7 mm
        assert fin.agent.dfam_thickness_mm == 12.7


# ── Integration tests (require OpenRocket JAR) ────────────────────────────────


@pytest.fixture
def minimal_rocket(tmp_path, openrocket_jar):
    """Build a minimal rocket with nose cone, body tube, motor mount, fins."""
    from rocketsmith.openrocket.components import new_ork, create_component

    p = tmp_path / "test.ork"
    new_ork("TestRocket", p, openrocket_jar)
    create_component(
        p,
        "nose-cone",
        openrocket_jar,
        diameter=0.064,
        length=0.12,
        shape="ogive",
    )
    create_component(
        p,
        "body-tube",
        openrocket_jar,
        diameter=0.064,
        length=0.4,
        name="Upper Airframe",
    )
    # Inner tube (motor mount) as child of BodyTube
    create_component(
        p, "inner-tube", openrocket_jar, diameter=0.029, length=0.1, motor_mount=True
    )
    # Fin set as child of BodyTube
    create_component(
        p,
        "fin-set",
        openrocket_jar,
        count=3,
        root_chord=0.08,
        tip_chord=0.04,
        span=0.06,
    )
    return p


class TestIntegration:
    def test_round_trip_through_openrocket(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        from rocketsmith.openrocket.generate_tree import generate_tree

        # 1. Generate tree
        tree, _ = generate_tree(minimal_rocket, tmp_path, jar_path=openrocket_jar)

        # 2. Annotate
        annotated = annotate_dfam(tree)

        # 3. Verify annotations
        # 1 stage, 2 top-level components (NC, BT)
        assert len(annotated.stages) == 1
        sustainer = annotated.stages[0]
        assert len(sustainer.components) == 2

        nc = next(c for c in sustainer.components if c.type == "NoseCone")
        bt = next(c for c in sustainer.components if c.type == "BodyTube")

        assert nc.agent.fate == Fate.PRINT
        assert bt.agent.fate == Fate.PRINT

        # BT should have 2 children: InnerTube and FinSet
        assert len(bt.children) == 2
        for child in bt.children:
            assert child.agent.fate == Fate.FUSE
            assert child.agent.fused_into == "upper_airframe"
