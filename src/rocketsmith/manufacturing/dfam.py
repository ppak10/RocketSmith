"""Design-for-additive-manufacturing translation.

Takes an OpenRocket component tree (mm-scaled via cad_handoff) and
produces a parts manifest tailored for 3D printing. Implements the
fusion decision rules documented in
``skills/design-for-additive-manufacturing/SKILL.md``.

Key rules (mirrored from the skill — keep in sync):

- ``NoseCone``               → always a standalone printed part
- ``BodyTube``               → always a standalone printed part, with children fused
- ``TrapezoidFinSet``        → always fused into its parent body tube (no standalone)
- ``InnerTube`` (motor mount) → fused into parent body tube by default; caller may
                                override to ``separate`` via fusion_overrides
- ``CenteringRing``          → absorbed into the parent body tube as wall thickening
                                when motor mount is fused; standalone part when not
- ``TubeCoupler``            → fused into parent body tube (as integral aft shoulder)
                                by default; caller may override to ``separate``
- ``Parachute``              → skipped (non-structural assembly item)
- ``MassComponent``          → skipped (ballast, added at assembly time)
- ``LaunchLug`` / ``RailButton`` → skipped (adhesive-mounted at assembly time)

The caller passes fusion decisions that require user input via
``fusion_overrides``. Everything else uses deterministic defaults.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rocketsmith.manufacturing.models import (
    Assembly,
    Decision,
    Directories,
    Fate,
    ManufacturingMethod,
    Modification,
    Part,
    PartsManifest,
    PurchasedItem,
    SkippedComponent,
)
from rocketsmith.openrocket.cad_handoff import cad_handoff

# Structural / non-physical component types that should never become their
# own printed parts and have no fusion behaviour.
_STRUCTURAL_WRAPPERS = {"Rocket", "AxialStage"}
_NON_PHYSICAL_TYPES = {"Parachute", "MassComponent", "LaunchLug", "RailButton"}


def _sanitize_name(name: str) -> str:
    """Convert a free-text component name to a snake_case identifier.

    "Nose Cone"            → "nose_cone"
    "Upper Airframe"       → "upper_airframe"
    "Trapezoidal Fin Set"  → "trapezoidal_fin_set"
    """
    slug = re.sub(r"[^\w\s-]", "", name.strip())
    slug = re.sub(r"[\s\-]+", "_", slug)
    return slug.lower() or "unnamed"


def _component_id(comp: dict[str, Any]) -> str:
    """Return the canonical ``Type:Name`` identifier for an OR component."""
    return f"{comp['type']}:{comp['name']}"


def _build_children_map(
    components: list[dict[str, Any]],
) -> dict[int, list[int]]:
    """Build a parent-index → child-indices map from the flat depth-walked list.

    The component list is a pre-order traversal with ``depth`` annotated
    per entry. A component is the parent of the next ``depth+1`` component,
    and that parent-child relationship holds for every subsequent
    ``depth+1`` until depth drops back to the parent's level.
    """
    children: dict[int, list[int]] = {i: [] for i in range(len(components))}
    # Stack of (index, depth) for ancestors at each depth level
    ancestors: list[tuple[int, int]] = []
    for i, comp in enumerate(components):
        d = comp.get("depth", 0)
        # Pop ancestors until we find one at depth < current
        while ancestors and ancestors[-1][1] >= d:
            ancestors.pop()
        if ancestors:
            parent_idx = ancestors[-1][0]
            children[parent_idx].append(i)
        ancestors.append((i, d))
    return children


def _direct_children(
    components: list[dict[str, Any]],
    children_map: dict[int, list[int]],
    parent_idx: int,
    child_type: str | None = None,
) -> list[int]:
    """Return direct-child indices of a component, optionally filtered by type."""
    out = []
    for i in children_map[parent_idx]:
        if child_type is None or components[i]["type"] == child_type:
            out.append(i)
    return out


def _make_part_entry(
    name: str,
    directories: Directories,
    derived_from: list[str],
    features: dict[str, Any],
    modifications: list[Modification] | None = None,
) -> Part:
    """Build a Part entry with directory-prefixed paths."""
    return Part(
        name=name,
        script_path=f"{directories.scripts}/{name}.py",
        step_path=f"{directories.step}/{name}.step",
        gcode_path=f"{directories.gcode}/{name}.gcode",
        derived_from=derived_from,
        fate=Fate.PRINT,
        features=features,
        modifications=modifications or [],
    )


def _nose_cone_features(comp: dict[str, Any]) -> dict[str, Any]:
    """Extract feature block for a nose cone.

    The shoulder retention decision is made at the manifest level
    (retention mechanism), not per-part, so it's propagated from the
    caller rather than computed here.
    """
    return {
        "shape": comp.get("shape", "ogive"),
        "length_mm": comp.get("length_mm"),
        "base_od_mm": comp.get("aft_diameter_mm"),
        "fore_d_mm": comp.get("fore_diameter_mm", 0.0),
        "wall_mm": comp.get("thickness_mm", 3.0),
    }


def _body_tube_base_features(comp: dict[str, Any]) -> dict[str, Any]:
    """Base feature block for a body tube (before fused children are added)."""
    return {
        "length_mm": comp.get("length_mm"),
        "od_mm": comp.get("outer_diameter_mm"),
        "id_mm": comp.get("inner_diameter_mm"),
        "base_wall_mm": comp.get("thickness_mm", 3.0),
        "fused": [],
    }


def _fin_feature_block(comp: dict[str, Any]) -> dict[str, Any]:
    """Feature block describing a fin set fused into a parent body tube."""
    return {
        "from": _component_id(comp),
        "as": "integrated_fins",
        "count": comp.get("fin_count"),
        "root_chord_mm": comp.get("root_chord_mm"),
        "tip_chord_mm": comp.get("tip_chord_mm"),
        "span_mm": comp.get("span_mm"),
        "sweep_mm": comp.get("sweep_mm", 0.0),
        "thickness_mm": comp.get("thickness_mm", 3.0),
        "fillet_mm": 1.5,
    }


def _motor_mount_feature_block(
    comp: dict[str, Any], parent_length_mm: float
) -> dict[str, Any]:
    """Feature block for a motor mount fused as local wall thickening."""
    length = comp.get("length_mm", 0.0)
    return {
        "from": _component_id(comp),
        "as": "local_wall_thickening",
        "bore_mm": comp.get("inner_diameter_mm"),
        "region_start_mm": max(0.0, parent_length_mm - length),
        "region_end_mm": parent_length_mm,
    }


def _coupler_feature_block(
    comp: dict[str, Any], parent_body_tube: dict[str, Any]
) -> dict[str, Any]:
    """Feature block for a coupler fused as integral aft shoulder.

    The shoulder OD is computed from the **parent body tube's inner
    diameter**, not from the coupler component's OR-side outer
    diameter. In traditional rocketry the coupler OD is sized to the
    body-tube ID minus a small clearance (so the coupler can slide in
    and be epoxied). When we fuse the coupler into the forward section
    as an integral shoulder for AM, we want the shoulder to match the
    mating section's ID with **zero clearance** (or a very small one
    for assembly tolerance) — otherwise the print comes out with a
    visible gap at the section joint.

    Assumes the mating (aft) section has the same inner diameter as
    the parent. For multi-section designs with varying diameters the
    user can override via ``fusion_overrides``.
    """
    # AM assembly clearance: 0.0 mm by default (interference fit or
    # just-touching). Traditional machining would use 0.2–0.5 mm here.
    assembly_clearance_mm = 0.0
    parent_id_mm = parent_body_tube.get("inner_diameter_mm", 0.0) or 0.0
    shoulder_od_mm = max(0.0, parent_id_mm - assembly_clearance_mm)
    return {
        "from": _component_id(comp),
        "as": "integral_aft_shoulder",
        "od_mm": shoulder_od_mm,
        "length_mm": comp.get("length_mm"),
        "assembly_clearance_mm": assembly_clearance_mm,
    }


def _retention_modifications_for_shoulder(
    target_z_mm: float,
    shoulder_od_mm: float,
    retention: str,
) -> list[Modification]:
    """Build the modifications list for one side of a retained joint.

    Only generates modifications when retention is explicitly set to
    something other than ``none`` or ``friction_fit``. For heat-set
    retention this emits radial insert holes on the shoulder-emitting
    side; the caller must separately add clearance through-holes on
    the mating side.
    """
    if retention == "m4_heat_set":
        return [
            Modification(
                kind="radial_holes",
                purpose="m4_heat_set_insert",
                count=4,
                angular_positions_deg=[45, 135, 225, 315],
                z_mm=target_z_mm,
                radius_mm=shoulder_od_mm / 2,
                hole_diameter_mm=5.7,
                hole_depth_mm=7.0,
            )
        ]
    # friction_fit and none have no modifications
    return []


def _retention_clearance_modifications(
    target_z_mm: float,
    tube_od_mm: float,
    retention: str,
) -> list[Modification]:
    """Modifications for the mating (receive) side of a retained joint.

    When the shoulder-emitting side has heat-set inserts, the mating
    tube wall needs through-holes so screws can pass through the tube
    and thread into the inserts.
    """
    if retention == "m4_heat_set":
        return [
            Modification(
                kind="radial_through_holes",
                purpose="m4_clearance",
                count=4,
                angular_positions_deg=[45, 135, 225, 315],
                z_mm=target_z_mm,
                radius_mm=tube_od_mm / 2,
                hole_diameter_mm=4.5,
            )
        ]
    return []


def _default_retention(max_diameter_mm: float | None) -> str:
    """Retention default is "none" — no assembly hardware is generated
    until the user explicitly asks for it.

    In earlier iterations this returned ``m4_heat_set`` for larger body
    diameters and ``friction_fit`` for LPR, but baking hardware into
    every design by default turned out to be wrong: users want the
    option, not the imposition. Retention modifications are now opt-in
    via ``fusion_overrides={"retention": "m4_heat_set"}``.

    The ``max_diameter_mm`` parameter is kept for forward compatibility
    with diameter-dependent defaults if we ever want them back.
    """
    return "none"


def generate_dfam_manifest(
    rocket_file_path: Path,
    project_root: Path,
    fusion_overrides: dict[str, str] | None = None,
    jar_path: Path | None = None,
) -> PartsManifest:
    """Generate a DFAM parts manifest from an OpenRocket design file.

    Args:
        rocket_file_path: Path to the .ork file.
        project_root: Project directory where the manifest and CAD outputs live.
        fusion_overrides: Optional dict of fusion decision overrides. Keys:
            - ``motor_mount_fate``: ``"fuse"`` (default) | ``"separate"``
            - ``coupler_fate``: ``"fuse"`` (default) | ``"separate"``
            - ``retention``: ``"m4_heat_set"`` | ``"friction_fit"`` (default
              is derived from body diameter if not specified)
        jar_path: Optional OpenRocket JAR path (autodetected if omitted).

    Returns:
        A validated ``PartsManifest`` instance. Caller is responsible for
        writing it to ``<project_root>/parts_manifest.json``.
    """
    overrides = fusion_overrides or {}

    handoff = cad_handoff(rocket_file_path, jar_path=jar_path)
    components = handoff["components"]
    derived = handoff.get("derived", {})

    directories = Directories()
    children_map = _build_children_map(components)

    # Fusion decisions with defaults
    motor_mount_fate = overrides.get("motor_mount_fate", "fuse")
    coupler_fate = overrides.get("coupler_fate", "fuse")
    retention = overrides.get(
        "retention", _default_retention(derived.get("max_diameter_mm"))
    )

    parts: list[Part] = []
    skipped: list[SkippedComponent] = []
    decisions: list[Decision] = []
    component_to_part_map: dict[str, str] = {}

    # Pass 1: handle nose cones
    for i, comp in enumerate(components):
        if comp["type"] != "NoseCone":
            continue
        cid = _component_id(comp)
        name = _sanitize_name(comp["name"])
        features = _nose_cone_features(comp)
        features["retention"] = retention
        part = _make_part_entry(name, directories, [cid], features)
        parts.append(part)
        component_to_part_map[cid] = name

    # Pass 2: handle body tubes, absorbing their children
    body_tube_names_used: set[str] = set()
    for i, comp in enumerate(components):
        if comp["type"] != "BodyTube":
            continue

        base_name = _sanitize_name(comp["name"])
        # Disambiguate duplicates by appending index
        name = base_name
        disambiguator = 2
        while name in body_tube_names_used:
            name = f"{base_name}_{disambiguator}"
            disambiguator += 1
        body_tube_names_used.add(name)

        cid = _component_id(comp)
        features = _body_tube_base_features(comp)
        derived_from = [cid]
        fused_blocks: list[dict[str, Any]] = []

        # Walk direct children and decide fate of each
        for child_idx in children_map[i]:
            child = components[child_idx]
            child_id = _component_id(child)
            child_type = child["type"]

            if child_type == "TrapezoidFinSet":
                fused_blocks.append(_fin_feature_block(child))
                derived_from.append(child_id)
                component_to_part_map[child_id] = name

            elif child_type == "InnerTube":
                if motor_mount_fate == "fuse":
                    fused_blocks.append(
                        _motor_mount_feature_block(child, features["length_mm"] or 0.0)
                    )
                    derived_from.append(child_id)
                    component_to_part_map[child_id] = name
                # "separate" case handled in pass 3 below

            elif child_type == "CenteringRing":
                if motor_mount_fate == "fuse":
                    skipped.append(
                        SkippedComponent(
                            name=child_id,
                            reason=f"absorbed into {name} via local wall thickening",
                        )
                    )
                    component_to_part_map[child_id] = "skipped"
                # "separate" case handled in pass 3 below

            elif child_type == "TubeCoupler":
                if coupler_fate == "fuse":
                    fused_blocks.append(_coupler_feature_block(child, comp))
                    derived_from.append(child_id)
                    component_to_part_map[child_id] = name
                # "separate" case handled in pass 3 below

            elif child_type in _NON_PHYSICAL_TYPES:
                skipped.append(
                    SkippedComponent(
                        name=child_id,
                        reason=_skip_reason_for(child_type),
                    )
                )
                component_to_part_map[child_id] = "skipped"

        features["fused"] = fused_blocks
        # Retention is recorded on the features for human inspection, but
        # the actual modification objects are populated in pass 5 below,
        # after every part exists so we can cross-reference shoulder
        # positions with mating tubes.
        features["retention"] = retention

        part = _make_part_entry(name, directories, derived_from, features)
        parts.append(part)
        component_to_part_map[cid] = name

    # Pass 3: handle standalone components when fusion overrides said "separate"
    if motor_mount_fate == "separate":
        for comp in components:
            if comp["type"] != "InnerTube":
                continue
            cid = _component_id(comp)
            if cid in component_to_part_map:
                continue  # already handled
            name = _sanitize_name(comp["name"])
            features = {
                "length_mm": comp.get("length_mm"),
                "outer_diameter_mm": comp.get("outer_diameter_mm"),
                "inner_diameter_mm": comp.get("inner_diameter_mm"),
                "wall_mm": comp.get("thickness_mm", 1.5),
            }
            parts.append(_make_part_entry(name, directories, [cid], features))
            component_to_part_map[cid] = name

    if motor_mount_fate == "separate":
        # Centering rings need to become standalone parts when the motor
        # mount is separate.
        for comp in components:
            if comp["type"] != "CenteringRing":
                continue
            cid = _component_id(comp)
            if cid in component_to_part_map:
                continue
            name = _sanitize_name(comp["name"])
            features = {
                "outer_diameter_mm": comp.get("outer_diameter_mm"),
                "inner_diameter_mm": comp.get("inner_diameter_mm"),
                "thickness_mm": comp.get("thickness_mm", 5.0),
            }
            parts.append(_make_part_entry(name, directories, [cid], features))
            component_to_part_map[cid] = name

    if coupler_fate == "separate":
        for comp in components:
            if comp["type"] != "TubeCoupler":
                continue
            cid = _component_id(comp)
            if cid in component_to_part_map:
                continue
            name = _sanitize_name(comp["name"])
            features = {
                "length_mm": comp.get("length_mm"),
                "outer_diameter_mm": comp.get("outer_diameter_mm"),
                "inner_diameter_mm": comp.get("inner_diameter_mm"),
                "retention": retention,
            }
            parts.append(_make_part_entry(name, directories, [cid], features))
            component_to_part_map[cid] = name

    # Pass 4: anything we haven't touched (wrappers, orphans)
    for comp in components:
        cid = _component_id(comp)
        if cid in component_to_part_map:
            continue
        if comp["type"] in _STRUCTURAL_WRAPPERS:
            component_to_part_map[cid] = "skipped"
            continue
        if comp["type"] in _NON_PHYSICAL_TYPES:
            skipped.append(
                SkippedComponent(name=cid, reason=_skip_reason_for(comp["type"]))
            )
            component_to_part_map[cid] = "skipped"
            continue
        # Unknown orphan — skip with a note
        skipped.append(
            SkippedComponent(
                name=cid,
                reason=f"orphaned {comp['type']} with no parent body tube",
            )
        )
        component_to_part_map[cid] = "skipped"

    # Pass 5: populate retention modifications on shoulder-bearing parts
    # and their mating sections. This is a no-op when retention == "none",
    # which is the default.
    if retention not in ("none", "friction_fit"):
        for part in parts:
            # Find any fused integral_aft_shoulder on this part
            for fused in part.features.get("fused", []):
                if fused.get("as") != "integral_aft_shoulder":
                    continue
                shoulder_length = fused.get("length_mm") or 0.0
                shoulder_od = fused.get("od_mm") or 0.0
                part_length = part.features.get("length_mm") or 0.0
                # Shoulder mid-length in the part's Z frame. The shoulder
                # extrudes past the aft face by shoulder_length, so its
                # mid-length is at part_length + shoulder_length/2.
                shoulder_mid_z = part_length + shoulder_length / 2
                part.modifications.extend(
                    _retention_modifications_for_shoulder(
                        target_z_mm=shoulder_mid_z,
                        shoulder_od_mm=shoulder_od,
                        retention=retention,
                    )
                )
                # The mating (aft) part needs clearance holes at its
                # fore-end shoulder receive zone. For simplicity we look
                # up the next body-tube-derived part in the list.
                mating_idx = parts.index(part) + 1
                if mating_idx < len(parts):
                    mating = parts[mating_idx]
                    mating_od = mating.features.get("od_mm") or 0.0
                    # Clearance holes sit at the same shoulder mid-length
                    # inside the mating tube's frame (Z ≈ shoulder_length/2).
                    mating.modifications.extend(
                        _retention_clearance_modifications(
                            target_z_mm=shoulder_length / 2,
                            tube_od_mm=mating_od,
                            retention=retention,
                        )
                    )

    # Build a default full_assembly entry if we have printable parts
    assemblies: list[Assembly] = []
    printable_names = [p.name for p in parts if p.fate == Fate.PRINT]
    if printable_names:
        assemblies.append(
            Assembly(
                name="full_assembly",
                step_path=f"{directories.step}/full_assembly.step",
                parts_fore_to_aft=printable_names,
            )
        )

    # Record decisions for auditability
    decisions.append(
        Decision(
            decision="motor_mount_fate",
            policy_default="fuse",
            chosen=motor_mount_fate,
            reason=(
                "override provided"
                if "motor_mount_fate" in overrides
                else "default for additive policy"
            ),
        )
    )
    decisions.append(
        Decision(
            decision="coupler_fate",
            policy_default="fuse",
            chosen=coupler_fate,
            reason=(
                "override provided"
                if "coupler_fate" in overrides
                else "default for additive policy"
            ),
        )
    )
    decisions.append(
        Decision(
            decision="retention",
            policy_default="none",
            chosen=retention,
            reason=(
                "override provided"
                if "retention" in overrides
                else "default — no assembly hardware until user opts in"
            ),
        )
    )

    return PartsManifest(
        source_ork=str(rocket_file_path),
        project_root=str(project_root),
        default_policy=ManufacturingMethod.ADDITIVE,
        assemblies=assemblies,
        directories=directories,
        parts=parts,
        skipped_components=skipped,
        decisions=decisions,
        component_to_part_map=component_to_part_map,
    )


def _skip_reason_for(type_name: str) -> str:
    return {
        "Parachute": "non-structural assembly item",
        "MassComponent": "ballast, added at assembly time",
        "LaunchLug": "adhesive-mounted at assembly time",
        "RailButton": "adhesive-mounted at assembly time",
    }.get(type_name, f"{type_name} is not translated by DFAM")
