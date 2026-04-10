"""Tests for DFAM translation logic.

The unit tests exercise the translation rules directly with hand-built
component lists, skipping the OpenRocket JAR dependency. The integration
tests round-trip through a real .ork file to catch any schema drift
between cad_handoff and the manifest generator.
"""

import pytest
from pathlib import Path

from rocketsmith.manufacturing.dfam import (
    _build_children_map,
    _sanitize_name,
    generate_dfam_manifest,
)
from rocketsmith.manufacturing.models import (
    Fate,
    ManufacturingMethod,
    PartsManifest,
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


class TestChildrenMap:
    def test_flat_list_no_children(self):
        components = [
            {"type": "Rocket", "name": "R", "depth": 0},
        ]
        assert _build_children_map(components) == {0: []}

    def test_single_parent_child(self):
        components = [
            {"type": "Rocket", "name": "R", "depth": 0},
            {"type": "AxialStage", "name": "Sustainer", "depth": 1},
        ]
        children = _build_children_map(components)
        assert children[0] == [1]
        assert children[1] == []

    def test_tree_walk_order(self):
        # Rocket → Stage → (NoseCone, BodyTube → FinSet)
        components = [
            {"type": "Rocket", "name": "R", "depth": 0},
            {"type": "AxialStage", "name": "S", "depth": 1},
            {"type": "NoseCone", "name": "NC", "depth": 2},
            {"type": "BodyTube", "name": "BT", "depth": 2},
            {"type": "TrapezoidFinSet", "name": "Fins", "depth": 3},
        ]
        children = _build_children_map(components)
        assert children[0] == [1]  # Rocket → Stage
        assert children[1] == [2, 3]  # Stage → NoseCone, BodyTube
        assert children[3] == [4]  # BodyTube → FinSet
        assert children[2] == []
        assert children[4] == []

    def test_multiple_siblings_at_same_depth(self):
        components = [
            {"type": "Rocket", "name": "R", "depth": 0},
            {"type": "AxialStage", "name": "S", "depth": 1},
            {"type": "BodyTube", "name": "Upper", "depth": 2},
            {"type": "TrapezoidFinSet", "name": "F", "depth": 3},
            {"type": "BodyTube", "name": "Lower", "depth": 2},
        ]
        children = _build_children_map(components)
        assert children[1] == [2, 4]
        assert children[2] == [3]  # FinSet is child of Upper
        assert children[4] == []  # Lower has no children


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
    create_component(p, "inner-tube", openrocket_jar, diameter=0.029, length=0.1)
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


class TestManifestGeneration:
    def test_manifest_is_valid_pydantic(self, minimal_rocket, tmp_path, openrocket_jar):
        manifest = generate_dfam_manifest(
            rocket_file_path=minimal_rocket,
            project_root=tmp_path,
            jar_path=openrocket_jar,
        )
        assert isinstance(manifest, PartsManifest)
        # Round-trip through model_dump should preserve everything
        dumped = manifest.model_dump(mode="json")
        restored = PartsManifest.model_validate(dumped)
        assert restored == manifest

    def test_manifest_has_correct_method(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        assert manifest.default_policy == ManufacturingMethod.ADDITIVE

    def test_manifest_produces_nose_cone_part(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        nose_cones = [p for p in manifest.parts if p.name == "nose_cone"]
        assert len(nose_cones) == 1
        nc = nose_cones[0]
        assert nc.fate == Fate.PRINT
        assert "NoseCone:Nose Cone" in nc.derived_from
        assert nc.features["shape"] == "ogive"
        assert nc.features["length_mm"] == pytest.approx(120.0, rel=1e-3)

    def test_fins_are_fused_not_standalone(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        """The single most important DFAM rule."""
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        # No standalone fin part
        fin_parts = [p for p in manifest.parts if "fin" in p.name.lower()]
        assert (
            len(fin_parts) == 0
        ), f"Found standalone fin parts: {[p.name for p in fin_parts]}"
        # Fins must be in the airframe's derived_from
        airframe = next(p for p in manifest.parts if "airframe" in p.name)
        assert "TrapezoidFinSet:Trapezoidal Fin Set" in airframe.derived_from
        # Fused feature block present
        fused_types = [f["as"] for f in airframe.features.get("fused", [])]
        assert "integrated_fins" in fused_types

    def test_motor_mount_fused_by_default(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        # No standalone motor_mount part
        mm_parts = [
            p
            for p in manifest.parts
            if p.name == "inner_tube" or p.name == "motor_mount"
        ]
        assert len(mm_parts) == 0
        # Fused into airframe
        airframe = next(p for p in manifest.parts if "airframe" in p.name)
        assert "InnerTube:Inner Tube" in airframe.derived_from
        fused_types = [f["as"] for f in airframe.features.get("fused", [])]
        assert "local_wall_thickening" in fused_types

    def test_motor_mount_separate_when_overridden(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket,
            tmp_path,
            fusion_overrides={"motor_mount_fate": "separate"},
            jar_path=openrocket_jar,
        )
        # Standalone motor mount exists
        mm_parts = [p for p in manifest.parts if p.name == "inner_tube"]
        assert len(mm_parts) == 1
        # And NOT in the airframe's derived_from
        airframe = next(p for p in manifest.parts if "airframe" in p.name)
        assert "InnerTube:Inner Tube" not in airframe.derived_from

    def test_component_to_part_map_covers_every_component(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        """Every OR component must be accounted for in component_to_part_map."""
        from rocketsmith.openrocket.cad_handoff import cad_handoff

        handoff = cad_handoff(minimal_rocket, jar_path=openrocket_jar)
        all_components = {f"{c['type']}:{c['name']}" for c in handoff["components"]}

        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        mapped = set(manifest.component_to_part_map.keys())

        assert all_components == mapped, (
            f"Missing from map: {all_components - mapped}, "
            f"Extra in map: {mapped - all_components}"
        )

    def test_decisions_are_recorded(self, minimal_rocket, tmp_path, openrocket_jar):
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        decision_keys = {d.decision for d in manifest.decisions}
        assert "motor_mount_fate" in decision_keys
        assert "coupler_fate" in decision_keys
        assert "retention" in decision_keys

    def test_override_is_reflected_in_decision_reason(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket,
            tmp_path,
            fusion_overrides={"motor_mount_fate": "separate"},
            jar_path=openrocket_jar,
        )
        mm_decision = next(
            d for d in manifest.decisions if d.decision == "motor_mount_fate"
        )
        assert mm_decision.chosen == "separate"
        assert "override" in mm_decision.reason.lower()

    def test_retention_default_is_none(self, minimal_rocket, tmp_path, openrocket_jar):
        """Retention is opt-in; default produces no assembly hardware."""
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        retention = next(d for d in manifest.decisions if d.decision == "retention")
        assert retention.chosen == "none"

    def test_no_modifications_by_default(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        """With retention=none, no part should have any modifications."""
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        for part in manifest.parts:
            assert (
                part.modifications == []
            ), f"Part {part.name} has unexpected modifications: {part.modifications}"

    def test_fin_thickness_bumped_to_minimum_by_default(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        """OR's default fin thickness (~3 mm) should be bumped to 12.7 mm for AM."""
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        airframe = next(
            p for p in manifest.parts if "airframe" in p.name or p.name == "upper"
        )
        fin_block = next(
            f
            for f in airframe.features.get("fused", [])
            if f.get("as") == "integrated_fins"
        )
        assert fin_block["thickness_mm"] == pytest.approx(12.7)
        # Original OR thickness preserved for auditability
        assert fin_block["or_thickness_mm"] < 12.7

    def test_fin_fillet_default_is_geometrically_feasible(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        """The fin-to-body fillet default must be buildable by OCC.

        An earlier iteration defaulted the fillet to the full fin
        thickness (12.7 mm), which OCC refuses to build because the
        fillets on the two broad faces of a 12.7 mm thick fin collide.
        The current default is ``thickness/4`` capped at 3 mm — small
        enough to always build, large enough to be visible and
        structurally meaningful.
        """
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        airframe = next(
            p for p in manifest.parts if "airframe" in p.name or p.name == "upper"
        )
        fin_block = next(
            f
            for f in airframe.features.get("fused", [])
            if f.get("as") == "integrated_fins"
        )
        thickness = fin_block["thickness_mm"]
        fillet = fin_block["fillet_mm"]
        # Must be strictly less than the fin half-thickness (OCC limit)
        assert fillet < thickness / 2
        # Must be > 0 (structural — fins without any root fillet are a
        # red flag per the DFAM skill)
        assert fillet > 0

    def test_fin_thickness_overridable(self, minimal_rocket, tmp_path, openrocket_jar):
        manifest = generate_dfam_manifest(
            minimal_rocket,
            tmp_path,
            fusion_overrides={"fin_thickness_mm": 5.0, "fin_fillet_mm": 2.0},
            jar_path=openrocket_jar,
        )
        airframe = next(
            p for p in manifest.parts if "airframe" in p.name or p.name == "upper"
        )
        fin_block = next(
            f
            for f in airframe.features.get("fused", [])
            if f.get("as") == "integrated_fins"
        )
        assert fin_block["thickness_mm"] == pytest.approx(5.0)
        # 2.0 is below the half-thickness ceiling (2.5) so it passes
        # through without clamping
        assert fin_block["fillet_mm"] == pytest.approx(2.0)

    def test_fin_fillet_override_clamped_to_half_thickness(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        """An override larger than the geometric ceiling is silently clamped.

        The ceiling is ``min(thickness/2, _DFAM_MAX_FIN_FILLET_MM)``.
        Passing 10 mm with a 5 mm thick fin should clamp to 2.5 mm.
        """
        manifest = generate_dfam_manifest(
            minimal_rocket,
            tmp_path,
            fusion_overrides={"fin_thickness_mm": 5.0, "fin_fillet_mm": 10.0},
            jar_path=openrocket_jar,
        )
        airframe = next(
            p for p in manifest.parts if "airframe" in p.name or p.name == "upper"
        )
        fin_block = next(
            f
            for f in airframe.features.get("fused", [])
            if f.get("as") == "integrated_fins"
        )
        assert fin_block["fillet_mm"] == pytest.approx(2.5)

    def test_nose_cone_has_integral_shoulder_by_default(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        nose_cone = next(p for p in manifest.parts if p.name == "nose_cone")
        shoulder = nose_cone.features.get("shoulder")
        assert shoulder is not None
        # Default shoulder OD = body tube ID (60 mm for the test rocket)
        assert shoulder["od_mm"] == pytest.approx(60.0)
        # Default shoulder length = 30 mm
        assert shoulder["length_mm"] == pytest.approx(30.0)

    def test_nose_cone_solid_by_default(self, minimal_rocket, tmp_path, openrocket_jar):
        """Nose cones should be solid (no hollowing pass) by default."""
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        nose_cone = next(p for p in manifest.parts if p.name == "nose_cone")
        assert nose_cone.features.get("hollow") is False
        assert nose_cone.features.get("wall_mm") is None

    def test_nose_cone_hollow_overridable(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket,
            tmp_path,
            fusion_overrides={"nose_cone_hollow": True, "nose_cone_wall_mm": 4.0},
            jar_path=openrocket_jar,
        )
        nose_cone = next(p for p in manifest.parts if p.name == "nose_cone")
        assert nose_cone.features["hollow"] is True
        assert nose_cone.features["wall_mm"] == pytest.approx(4.0)

    def test_nose_cone_shoulder_length_overridable(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket,
            tmp_path,
            fusion_overrides={"nose_cone_shoulder_length_mm": 50.0},
            jar_path=openrocket_jar,
        )
        nose_cone = next(p for p in manifest.parts if p.name == "nose_cone")
        assert nose_cone.features["shoulder"]["length_mm"] == pytest.approx(50.0)

    def test_full_assembly_is_always_populated(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        """A default manifest should include a full_assembly entry."""
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        assembly_names = [a.name for a in manifest.assemblies]
        assert "full_assembly" in assembly_names
        full = next(a for a in manifest.assemblies if a.name == "full_assembly")
        assert full.step_path.startswith("CAD/")
        assert full.step_path.endswith("full_assembly.step")
        # Every printable part should be in the fore-to-aft list
        printable = [p.name for p in manifest.parts if p.fate.value == "print"]
        assert full.parts_fore_to_aft == printable

    def test_part_paths_use_configured_directories(
        self, minimal_rocket, tmp_path, openrocket_jar
    ):
        manifest = generate_dfam_manifest(
            minimal_rocket, tmp_path, jar_path=openrocket_jar
        )
        for part in manifest.parts:
            assert part.script_path.startswith("cadsmith/")
            assert part.script_path.endswith(".py")
            assert part.step_path.startswith("CAD/")
            assert part.step_path.endswith(".step")
            assert part.gcode_path.startswith("gcode/")
            assert part.gcode_path.endswith(".gcode")
