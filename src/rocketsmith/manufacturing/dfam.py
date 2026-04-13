"""Design-for-additive-manufacturing annotation.

Walks a ``ComponentTree`` (already generated from an .ork file by
``openrocket_generate_tree``) and annotates each component's ``agent``
field with DFAM decisions: fate assignments, fusion directives, and
AM-specific dimension adjustments.

Key rules:

- ``NoseCone``               → print (standalone, integral shoulder added)
- ``BodyTube``               → print (standalone, children fused in)
- ``TrapezoidFinSet``        → fuse into parent body tube (thickness bumped to min 12.7 mm)
- ``InnerTube`` (motor mount) → fuse by default; separable via overrides
- ``CenteringRing``          → skip when motor mount is fused; separate when not
- ``TubeCoupler``            → fuse as integral aft shoulder by default; separable
- ``Parachute`` etc.         → purchase/skip (non-structural)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from rocketsmith.manufacturing.models import (
    AgentAnnotation,
    Component,
    ComponentTree,
    Fate,
)


# ── DFAM constants ─────────────────────────────────────────────────────────────

_DFAM_MIN_FIN_THICKNESS_MM = 12.7
_DFAM_FIN_FILLET_THICKNESS_FRACTION = 0.25
_DFAM_MAX_FIN_FILLET_MM = 3.0
_DFAM_DEFAULT_NOSE_SHOULDER_LENGTH_MM = 30.0

_NON_PHYSICAL_TYPES = {"Parachute", "MassComponent", "LaunchLug", "RailButton"}
_STRUCTURAL_WRAPPERS = {"Rocket", "AxialStage"}

_AGENT_NAME = "manufacturing"


def _sanitize_name(name: str) -> str:
    """Convert a free-text component name to a snake_case identifier."""
    slug = re.sub(r"[^\w\s-]", "", name.strip())
    slug = re.sub(r"[\s\-]+", "_", slug)
    return slug.lower() or "unnamed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dim(component: Component, field: str) -> float:
    """Extract a dimension magnitude from a component, returning 0.0 if missing."""
    dims = component.dimensions
    val = getattr(dims, field, None)
    if val is None:
        return 0.0
    if hasattr(val, "magnitude"):
        return float(val.magnitude)
    return float(val)


# ── Annotation helpers ─────────────────────────────────────────────────────────


def _annotate(
    component: Component,
    fate: Fate,
    reason: str,
    fused_into: str | None = None,
    **extra: object,
) -> None:
    """Set the agent annotation on a component."""
    component.agent = AgentAnnotation(
        fate=fate,
        fused_into=fused_into,
        reason=reason,
        updated_by=_AGENT_NAME,
        updated_at=_now(),
        **extra,
    )


def _annotate_nose_cone(
    comp: Component,
    body_tube_id_mm: float | None,
    overrides: dict,
) -> None:
    """Annotate a nose cone as a standalone printed part."""
    shoulder_length = float(
        overrides.get(
            "nose_cone_shoulder_length_mm",
            _DFAM_DEFAULT_NOSE_SHOULDER_LENGTH_MM,
        )
    )
    shoulder_od = body_tube_id_mm if body_tube_id_mm and body_tube_id_mm > 0 else None
    hollow = bool(overrides.get("nose_cone_hollow", False))
    wall = float(overrides.get("nose_cone_wall_mm", 3.0))

    _annotate(
        comp,
        fate=Fate.PRINT,
        reason="Nose cone is always a standalone printed part for AM",
        dfam_shoulder_length_mm=shoulder_length,
        dfam_shoulder_od_mm=shoulder_od,
        dfam_hollow=hollow,
        dfam_wall_mm=wall if hollow else None,
    )


def _annotate_fin_set(comp: Component, parent_name: str, overrides: dict) -> None:
    """Annotate a fin set as fused into its parent body tube."""
    or_thickness = _dim(comp, "thickness")
    if "fin_thickness_mm" in overrides:
        thickness = float(overrides["fin_thickness_mm"])
    else:
        thickness = max(or_thickness, _DFAM_MIN_FIN_THICKNESS_MM)

    fillet_ceiling = min(thickness / 2.0, _DFAM_MAX_FIN_FILLET_MM)
    default_fillet = min(
        thickness * _DFAM_FIN_FILLET_THICKNESS_FRACTION,
        _DFAM_MAX_FIN_FILLET_MM,
    )
    if "fin_fillet_mm" in overrides:
        fillet = min(float(overrides["fin_fillet_mm"]), fillet_ceiling)
    else:
        fillet = default_fillet

    _annotate(
        comp,
        fate=Fate.FUSE,
        fused_into=parent_name,
        reason="Fins always integrated into parent body tube for AM",
        dfam_thickness_mm=thickness,
        dfam_or_thickness_mm=or_thickness,
        dfam_fillet_mm=fillet,
    )


def _annotate_motor_mount_fused(
    comp: Component, parent_name: str, parent_length_mm: float
) -> None:
    """Annotate a motor mount as fused (local wall thickening)."""
    mount_length = _dim(comp, "length")
    _annotate(
        comp,
        fate=Fate.FUSE,
        fused_into=parent_name,
        reason="Motor mount fused as local wall thickening (default AM policy)",
        dfam_bore_mm=_dim(comp, "id"),
        dfam_region_start_mm=max(0.0, parent_length_mm - mount_length),
        dfam_region_end_mm=parent_length_mm,
    )


def _annotate_coupler_fused(
    comp: Component, parent_name: str, parent_id_mm: float
) -> None:
    """Annotate a coupler as fused (integral aft shoulder)."""
    _annotate(
        comp,
        fate=Fate.FUSE,
        fused_into=parent_name,
        reason="Coupler fused as integral aft shoulder (default AM policy)",
        dfam_shoulder_od_mm=parent_id_mm,
        dfam_shoulder_length_mm=_dim(comp, "length"),
    )


# ── Main annotation function ──────────────────────────────────────────────────


def annotate_dfam(
    tree: ComponentTree,
    fusion_overrides: dict[str, str] | None = None,
) -> ComponentTree:
    """Annotate a ComponentTree with DFAM decisions.

    Walks the component hierarchy and populates each component's
    ``agent`` field with fate, fusion, and AM-specific adjustments.

    Args:
        tree: A ComponentTree generated by ``openrocket_generate_tree``.
        fusion_overrides: Optional dict of fusion decision overrides:
            - ``motor_mount_fate``: ``"fuse"`` (default) | ``"separate"``
            - ``coupler_fate``: ``"fuse"`` (default) | ``"separate"``
            - ``nose_cone_hollow``: ``True`` | ``False`` (default)
            - ``nose_cone_wall_mm``: wall thickness if hollow
            - ``nose_cone_shoulder_length_mm``: shoulder length override
            - ``fin_thickness_mm``: override minimum fin thickness
            - ``fin_fillet_mm``: override fillet radius

    Returns:
        The same ComponentTree with agent annotations populated.
    """
    overrides = fusion_overrides or {}
    motor_mount_fate = overrides.get("motor_mount_fate", "fuse")
    coupler_fate = overrides.get("coupler_fate", "fuse")

    # Find the primary body tube ID for nose cone shoulder sizing.
    body_tube_id_mm: float | None = None
    for stage in tree.stages:
        for comp in stage.components:
            if comp.type == "BodyTube":
                body_tube_id_mm = _dim(comp, "id")
                break
        if body_tube_id_mm:
            break

    for stage in tree.stages:
        for comp in stage.components:
            _annotate_component(
                comp,
                parent_name=None,
                body_tube_id_mm=body_tube_id_mm,
                motor_mount_fate=motor_mount_fate,
                coupler_fate=coupler_fate,
                overrides=overrides,
            )

    return tree


def _annotate_component(
    comp: Component,
    parent_name: str | None,
    body_tube_id_mm: float | None,
    motor_mount_fate: str,
    coupler_fate: str,
    overrides: dict,
) -> None:
    """Recursively annotate a component and its children."""
    name = _sanitize_name(comp.name)

    if comp.type == "NoseCone":
        _annotate_nose_cone(comp, body_tube_id_mm, overrides)

    elif comp.type == "BodyTube":
        _annotate(
            comp,
            fate=Fate.PRINT,
            reason="Body tube is always a standalone printed part for AM",
        )
        # Annotate children with this tube as parent
        for child in comp.children:
            _annotate_component(
                child,
                parent_name=name,
                body_tube_id_mm=body_tube_id_mm,
                motor_mount_fate=motor_mount_fate,
                coupler_fate=coupler_fate,
                overrides=overrides,
            )
        return  # children already handled

    elif comp.type in ("TrapezoidFinSet", "EllipticalFinSet", "FreeformFinSet"):
        if parent_name:
            _annotate_fin_set(comp, parent_name, overrides)
        else:
            _annotate(
                comp, fate=Fate.PRINT, reason="Orphaned fin set — no parent body tube"
            )

    elif comp.type == "InnerTube":
        if (
            comp.dimensions.motor_mount
            if hasattr(comp.dimensions, "motor_mount")
            else False
        ):
            if motor_mount_fate == "fuse" and parent_name:
                parent_length = 0.0
                _annotate_motor_mount_fused(comp, parent_name, parent_length)
            else:
                _annotate(
                    comp,
                    fate=Fate.PRINT,
                    reason="Motor mount as separate printed part (override)",
                )
        else:
            _annotate(
                comp, fate=Fate.PRINT, reason="Inner tube as standalone printed part"
            )

    elif comp.type == "TubeCoupler":
        if coupler_fate == "fuse" and parent_name:
            parent_id = body_tube_id_mm or 0.0
            _annotate_coupler_fused(comp, parent_name, parent_id)
        else:
            _annotate(
                comp,
                fate=Fate.PRINT,
                reason="Coupler as separate printed part (override)",
            )

    elif comp.type == "CenteringRing":
        if motor_mount_fate == "fuse" and parent_name:
            _annotate(
                comp,
                fate=Fate.SKIP,
                reason=f"Absorbed into {parent_name} via motor mount wall thickening",
            )
        else:
            _annotate(
                comp, fate=Fate.PRINT, reason="Centering ring as separate printed part"
            )

    elif comp.type in _NON_PHYSICAL_TYPES:
        _annotate(
            comp,
            fate=Fate.PURCHASE,
            reason=f"{comp.type} — purchased/non-structural item",
        )

    elif comp.type in _STRUCTURAL_WRAPPERS:
        _annotate(
            comp, fate=Fate.SKIP, reason="Structural wrapper — not a physical part"
        )

    else:
        _annotate(comp, fate=Fate.SKIP, reason=f"Unknown component type: {comp.type}")

    # Recurse into children (unless already handled by BodyTube above)
    for child in comp.children:
        _annotate_component(
            child,
            parent_name=name,
            body_tube_id_mm=body_tube_id_mm,
            motor_mount_fate=motor_mount_fate,
            coupler_fate=coupler_fate,
            overrides=overrides,
        )
