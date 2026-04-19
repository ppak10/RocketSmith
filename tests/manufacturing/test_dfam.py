"""Tests for DFAM annotation logic.

Unit tests verify the translation rules against a ComponentTree,
skipping the OpenRocket JAR dependency. Integration tests round-trip
through a real .ork file using openrocket_component (action="read").
"""

import pytest
from pathlib import Path

from rocketsmith.manufacturing.dfam import (
    _sanitize_name,
    _dim,
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
    RingDimensions,
    RecoveryDimensions,
    GenericDimensions,
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


class TestCadsmithPath:
    """Verify cadsmith_path is set correctly after annotate_dfam."""

    def _make_tree(self, tmp_path, components, fusion_overrides=None):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=components,
                )
            ],
        )
        return annotate_dfam(tree, fusion_overrides=fusion_overrides)

    def test_nose_cone_gets_cadsmith_path(self, tmp_path):
        tree = self._make_tree(
            tmp_path,
            [
                Component(
                    type="NoseCone",
                    name="Nose Cone",
                    category="structural",
                    dimensions=NoseConeDimensions(
                        shape="ogive",
                        length=120.0,
                        base_od=64.0,
                    ),
                )
            ],
        )
        nc = tree.stages[0].components[0]
        assert nc.cadsmith_path == "nose_cone.py"

    def test_body_tube_gets_cadsmith_path(self, tmp_path):
        tree = self._make_tree(
            tmp_path,
            [
                Component(
                    type="BodyTube",
                    name="Body Tube",
                    category="structural",
                    dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                )
            ],
        )
        bt = tree.stages[0].components[0]
        assert bt.cadsmith_path == "body_tube.py"

    def test_fused_fin_set_has_no_cadsmith_path(self, tmp_path):
        tree = self._make_tree(
            tmp_path,
            [
                Component(
                    type="BodyTube",
                    name="Body Tube",
                    category="structural",
                    dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                    children=[
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
                    ],
                )
            ],
        )
        bt = tree.stages[0].components[0]
        fin = bt.children[0]
        assert fin.cadsmith_path is None

    def test_separate_motor_mount_gets_cadsmith_path(self, tmp_path):
        tree = self._make_tree(
            tmp_path,
            [
                Component(
                    type="BodyTube",
                    name="Body Tube",
                    category="structural",
                    dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                    children=[
                        Component(
                            type="InnerTube",
                            name="Motor Mount",
                            category="structural",
                            dimensions=TubeDimensions(
                                length=100.0,
                                od=29.0,
                                id=27.0,
                                motor_mount=True,
                            ),
                        )
                    ],
                )
            ],
            fusion_overrides={"motor_mount_fate": "separate"},
        )
        bt = tree.stages[0].components[0]
        mm = bt.children[0]
        assert mm.cadsmith_path == "motor_mount.py"

    def test_separate_coupler_gets_cadsmith_path(self, tmp_path):
        tree = self._make_tree(
            tmp_path,
            [
                Component(
                    type="BodyTube",
                    name="Body Tube",
                    category="structural",
                    dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                    children=[
                        Component(
                            type="TubeCoupler",
                            name="Tube Coupler",
                            category="structural",
                            dimensions=TubeDimensions(length=60.0, od=60.0, id=56.0),
                        )
                    ],
                )
            ],
            fusion_overrides={"coupler_fate": "separate"},
        )
        bt = tree.stages[0].components[0]
        coupler = bt.children[0]
        assert coupler.cadsmith_path == "tube_coupler.py"

    def test_separate_centering_ring_gets_cadsmith_path(self, tmp_path):
        tree = self._make_tree(
            tmp_path,
            [
                Component(
                    type="BodyTube",
                    name="Body Tube",
                    category="structural",
                    dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                    children=[
                        Component(
                            type="CenteringRing",
                            name="Centering Ring",
                            category="structural",
                            dimensions=RingDimensions(od=62.0, id=29.5, thickness=5.0),
                        )
                    ],
                )
            ],
            fusion_overrides={"motor_mount_fate": "separate"},
        )
        bt = tree.stages[0].components[0]
        cr = bt.children[0]
        assert cr.cadsmith_path == "centering_ring.py"

    def test_fused_motor_mount_has_none_cadsmith_path(self, tmp_path):
        """Motor mount with default fuse fate should have cadsmith_path=None."""
        tree = self._make_tree(
            tmp_path,
            [
                Component(
                    type="BodyTube",
                    name="Body Tube",
                    category="structural",
                    dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                    children=[
                        Component(
                            type="InnerTube",
                            name="Motor Mount",
                            category="structural",
                            dimensions=TubeDimensions(
                                length=100.0,
                                od=29.0,
                                id=27.0,
                                motor_mount=True,
                            ),
                        )
                    ],
                )
            ],
            # motor_mount_fate defaults to "fuse"
        )
        bt = tree.stages[0].components[0]
        mm = bt.children[0]
        assert mm.cadsmith_path is None


# ── _dim helper tests ─────────────────────────────────────────────────────────


class TestDimHelper:
    """Tests for the _dim() helper function."""

    def _make_component_with_dims(self, dims):
        return Component(
            type="NoseCone",
            name="Test",
            category="structural",
            dimensions=dims,
        )

    def test_dim_returns_zero_for_missing_field(self):
        """Line 61: _dim returns 0.0 when the field doesn't exist on dimensions."""
        comp = self._make_component_with_dims(
            NoseConeDimensions(shape="ogive", length=100.0, base_od=64.0)
        )
        result = _dim(comp, "nonexistent_field")
        assert result == 0.0

    def test_dim_returns_float_for_plain_number(self):
        """Line 64: _dim returns float(val) when val has no .magnitude attribute.

        TubeDimensions.motor_mount is a plain bool — no .magnitude.
        """
        comp = self._make_component_with_dims(
            TubeDimensions(length=400.0, od=64.0, id=60.0, motor_mount=True)
        )
        # motor_mount is a bool (no .magnitude), so _dim should call float(val)
        result = _dim(comp, "motor_mount")
        assert result == 1.0  # float(True) == 1.0


# ── Fin override tests ────────────────────────────────────────────────────────


class TestFinOverrides:
    """Tests for fin_thickness_mm and fin_fillet_mm overrides (lines 119, 129)."""

    def _make_tree_with_fins(self, tmp_path, fusion_overrides=None):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="BodyTube",
                            name="Body Tube",
                            category="structural",
                            dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                            children=[
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
                            ],
                        )
                    ],
                )
            ],
        )
        return annotate_dfam(tree, fusion_overrides=fusion_overrides)

    def test_fin_thickness_override(self, tmp_path):
        """Line 119: fusion_overrides fin_thickness_mm overrides default."""
        tree = self._make_tree_with_fins(
            tmp_path, fusion_overrides={"fin_thickness_mm": 15.0}
        )
        fin = tree.stages[0].components[0].children[0]
        assert fin.agent.dfam_thickness_mm == 15.0

    def test_fin_fillet_override(self, tmp_path):
        """Line 129: fusion_overrides fin_fillet_mm overrides default fillet."""
        tree = self._make_tree_with_fins(
            tmp_path, fusion_overrides={"fin_fillet_mm": 2.0}
        )
        fin = tree.stages[0].components[0].children[0]
        # fillet_ceiling = min(12.7/2, 3.0) = min(6.35, 3.0) = 3.0
        # fin_fillet_mm=2.0 < 3.0 ceiling, so fillet == 2.0
        assert fin.agent.dfam_fillet_mm == pytest.approx(2.0)


# ── Motor mount fused (line 164) ──────────────────────────────────────────────


class TestMotorMountFused:
    """Line 164: motor mount with default fate=fuse gets Fate.FUSE and no cadsmith_path."""

    def test_motor_mount_fuse_fate_and_no_cadsmith_path(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="BodyTube",
                            name="Body Tube",
                            category="structural",
                            dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                            children=[
                                Component(
                                    type="InnerTube",
                                    name="Motor Mount",
                                    category="structural",
                                    dimensions=TubeDimensions(
                                        length=100.0,
                                        od=29.0,
                                        id=27.0,
                                        motor_mount=True,
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)  # default motor_mount_fate="fuse"
        mm = annotated.stages[0].components[0].children[0]
        assert mm.agent.fate == Fate.FUSE
        assert mm.cadsmith_path is None


# ── Modifications override (line 253) ────────────────────────────────────────


class TestModificationsOverride:
    """Line 253: modifications in fusion_overrides ends up on body tube's dfam_modifications."""

    def test_modifications_set_on_body_tube(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="BodyTube",
                            name="Body Tube",
                            category="structural",
                            dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                        )
                    ],
                )
            ],
        )
        mods = [{"kind": "radial_through_holes"}]
        annotated = annotate_dfam(tree, fusion_overrides={"modifications": mods})
        bt = annotated.stages[0].components[0]
        assert bt.agent.dfam_modifications == mods


# ── Orphaned fin set (lines 277-280) ──────────────────────────────────────────


class TestOrphanedFinSet:
    """Lines 277-280: top-level TrapezoidFinSet (no parent) gets PRINT + cadsmith_path."""

    def test_orphaned_fin_set_gets_print(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="TrapezoidFinSet",
                            name="Orphan Fins",
                            category="structural",
                            dimensions=FinSetDimensions(
                                root_chord=80.0,
                                tip_chord=40.0,
                                span=60.0,
                                thickness=3.0,
                            ),
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)
        fin = annotated.stages[0].components[0]
        assert fin.agent.fate == Fate.PRINT
        assert fin.cadsmith_path == "orphan_fins.py"


# ── Non-motor-mount InnerTube (lines 299-302) ─────────────────────────────────


class TestNonMotorMountInnerTube:
    """Lines 299-302: InnerTube with motor_mount=False gets PRINT + cadsmith_path."""

    def test_inner_tube_no_motor_mount_gets_print(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="BodyTube",
                            name="Body Tube",
                            category="structural",
                            dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                            children=[
                                Component(
                                    type="InnerTube",
                                    name="Payload Bay",
                                    category="structural",
                                    dimensions=TubeDimensions(
                                        length=150.0,
                                        od=50.0,
                                        id=48.0,
                                        motor_mount=False,
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)
        inner = annotated.stages[0].components[0].children[0]
        assert inner.agent.fate == Fate.PRINT
        assert inner.cadsmith_path == "payload_bay.py"


# ── TubeCoupler fused default (lines 306-307) ────────────────────────────────


class TestTubeCouplerFusedDefault:
    """Lines 306-307: TubeCoupler with default coupler_fate=fuse gets FUSE + no cadsmith_path."""

    def test_tube_coupler_fuse_fate(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="BodyTube",
                            name="Body Tube",
                            category="structural",
                            dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                            children=[
                                Component(
                                    type="TubeCoupler",
                                    name="Tube Coupler",
                                    category="structural",
                                    dimensions=TubeDimensions(
                                        length=60.0, od=60.0, id=56.0
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)  # default coupler_fate="fuse"
        coupler = annotated.stages[0].components[0].children[0]
        assert coupler.agent.fate == Fate.FUSE
        assert coupler.cadsmith_path is None


# ── CenteringRing skipped (line 318) ─────────────────────────────────────────


class TestCenteringRingSkipped:
    """Line 318: CenteringRing with default motor_mount_fate=fuse gets SKIP + no cadsmith_path."""

    def test_centering_ring_skip_when_motor_mount_fused(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="BodyTube",
                            name="Body Tube",
                            category="structural",
                            dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                            children=[
                                Component(
                                    type="CenteringRing",
                                    name="Centering Ring",
                                    category="structural",
                                    dimensions=RingDimensions(
                                        od=62.0, id=29.5, thickness=5.0
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)  # default motor_mount_fate="fuse"
        cr = annotated.stages[0].components[0].children[0]
        assert cr.agent.fate == Fate.SKIP
        assert cr.cadsmith_path is None


# ── Non-physical types (lines 329-334) ───────────────────────────────────────


class TestNonPhysicalTypes:
    """Lines 329-334: Parachute gets Fate.PURCHASE."""

    def test_parachute_gets_purchase(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="Parachute",
                            name="Main Chute",
                            category="recovery",
                            dimensions=RecoveryDimensions(diameter=300.0),
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)
        chute = annotated.stages[0].components[0]
        assert chute.agent.fate == Fate.PURCHASE


# ── Unknown type (lines 341-342) ─────────────────────────────────────────────


class TestUnknownType:
    """Lines 341-342: Unknown component type gets Fate.SKIP."""

    def test_unknown_widget_gets_skip(self, tmp_path):
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="UnknownWidget",
                            name="Mystery Part",
                            category="structural",
                            dimensions=RecoveryDimensions(),
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)
        widget = annotated.stages[0].components[0]
        assert widget.agent.fate == Fate.SKIP

    def test_axial_stage_gets_skip(self, tmp_path):
        """Line 337: AxialStage in _STRUCTURAL_WRAPPERS → Fate.SKIP."""
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="AxialStage",
                            name="Booster Stage",
                            category="structural",
                            dimensions=GenericDimensions(),
                        )
                    ],
                )
            ],
        )
        annotated = annotate_dfam(tree)
        stage_comp = annotated.stages[0].components[0]
        assert stage_comp.agent.fate == Fate.SKIP


# ── Children recursion (line 346) ────────────────────────────────────────────


class TestChildrenRecursion:
    """Line 346: children of non-BodyTube components are recursed into."""

    def test_tube_coupler_child_gets_annotated(self, tmp_path):
        """TubeCoupler (separate fate) with a child — the child gets annotated."""
        tree = ComponentTree(
            source_ork="test.ork",
            project_root=str(tmp_path),
            rocket_name="TestRocket",
            stages=[
                Stage(
                    name="Sustainer",
                    components=[
                        Component(
                            type="BodyTube",
                            name="Body Tube",
                            category="structural",
                            dimensions=TubeDimensions(length=400.0, od=64.0, id=60.0),
                            children=[
                                Component(
                                    type="TubeCoupler",
                                    name="Coupler",
                                    category="structural",
                                    dimensions=TubeDimensions(
                                        length=60.0, od=60.0, id=56.0
                                    ),
                                    children=[
                                        Component(
                                            type="Parachute",
                                            name="Drogue Chute",
                                            category="recovery",
                                            dimensions=RecoveryDimensions(
                                                diameter=200.0
                                            ),
                                        )
                                    ],
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        # Use separate coupler fate so coupler is annotated as non-fused
        annotated = annotate_dfam(tree, fusion_overrides={"coupler_fate": "separate"})
        coupler = annotated.stages[0].components[0].children[0]
        drogue = coupler.children[0]
        # The child parachute must have been recursed into and annotated
        assert drogue.agent is not None
        assert drogue.agent.fate == Fate.PURCHASE


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
