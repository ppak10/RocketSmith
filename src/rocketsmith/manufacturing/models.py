"""Pydantic models for the component tree.

The component tree is a living document that evolves through three phases:

1. **OpenRocket agent** populates it from the .ork simulation file —
   component hierarchy, reference dimensions, and human notes.
2. **Manufacturing agent** annotates it with DFAM decisions — fate
   assignments, fusion directives, dimension adjustments.
3. **Cadsmith agent** reads it to generate CAD — STEP files for
   printed parts, bounding boxes for purchased items.

The component hierarchy mirrors the OpenRocket component tree.
Components are never removed — fusion is an annotation, not a deletion.
Manufacturing decisions are persisted in each component's OpenRocket
comment field under the ``== agents ==`` delimiter, so the .ork file
remains the single source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field
from pintdantic import QuantityModel, QuantityField

from rocketsmith.openrocket.models import Dimensions


# ── Enums ──────────────────────────────────────────────────────────────────────


class Fate(str, Enum):
    """Per-component manufacturing decision."""

    PRINT = "print"
    FUSE = "fuse"
    PURCHASE = "purchase"
    SKIP = "skip"


class ComponentCategory(str, Enum):
    """High-level classification of a component's role."""

    STRUCTURAL = "structural"
    RECOVERY = "recovery"
    HARDWARE = "hardware"
    ELECTRONICS = "electronics"
    PROPULSION = "propulsion"


# ── Category defaults by OpenRocket component type ─────────────────────────────

_TYPE_TO_CATEGORY: dict[str, ComponentCategory] = {
    "NoseCone": ComponentCategory.STRUCTURAL,
    "BodyTube": ComponentCategory.STRUCTURAL,
    "TrapezoidFinSet": ComponentCategory.STRUCTURAL,
    "EllipticalFinSet": ComponentCategory.STRUCTURAL,
    "FreeformFinSet": ComponentCategory.STRUCTURAL,
    "InnerTube": ComponentCategory.STRUCTURAL,
    "TubeCoupler": ComponentCategory.STRUCTURAL,
    "CenteringRing": ComponentCategory.STRUCTURAL,
    "BulkHead": ComponentCategory.STRUCTURAL,
    "Transition": ComponentCategory.STRUCTURAL,
    "LaunchLug": ComponentCategory.HARDWARE,
    "RailButton": ComponentCategory.HARDWARE,
    "Parachute": ComponentCategory.RECOVERY,
    "Streamer": ComponentCategory.RECOVERY,
    "ShockCord": ComponentCategory.RECOVERY,
    "MassComponent": ComponentCategory.HARDWARE,
    "EngineBlock": ComponentCategory.PROPULSION,
}


def default_category(component_type: str) -> ComponentCategory:
    """Return the default category for an OpenRocket component type."""
    return _TYPE_TO_CATEGORY.get(component_type, ComponentCategory.HARDWARE)


# ── Agent annotations ──────────────────────────────────────────────────────────


class AgentAnnotation(BaseModel):
    """Structured data written below ``== agents ==`` in an OR comment field.

    These annotations are the manufacturing agent's decisions, persisted
    in the .ork file so the BOM can be regenerated without losing them.
    """

    fate: Fate | None = None
    fused_into: str | None = None
    reason: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None

    model_config = {"extra": "allow"}


def parse_comment(comment: str | None) -> tuple[str | None, AgentAnnotation | None]:
    """Split an OpenRocket comment into human notes and agent annotations.

    Returns:
        (human_notes, agent_annotation) — either may be None.
    """
    if not comment or not comment.strip():
        return None, None

    delimiter = "== agents =="
    if delimiter not in comment:
        return comment.strip() or None, None

    above, below = comment.split(delimiter, maxsplit=1)
    human_notes = above.strip() or None

    # Parse key: value pairs from the agent section.
    data: dict[str, str] = {}
    for line in below.strip().splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()

    annotation = AgentAnnotation.model_validate(data) if data else None
    return human_notes, annotation


def serialize_comment(
    human_notes: str | None,
    annotation: AgentAnnotation | None,
) -> str:
    """Rebuild an OpenRocket comment from human notes and agent annotations."""
    parts: list[str] = []
    if human_notes:
        parts.append(human_notes)

    if annotation:
        parts.append("== agents ==")
        for key, value in annotation.model_dump(exclude_none=True).items():
            parts.append(f"{key}: {value}")

    return "\n".join(parts)


# ── Component ──────────────────────────────────────────────────────────────────


class Component(QuantityModel):
    """A single item in the rocket's component hierarchy.

    Mirrors one node in the OpenRocket component tree. The hierarchy is
    preserved via ``children`` — components are never removed, even when
    fused into a parent for manufacturing.
    """

    type: str
    name: str
    category: ComponentCategory
    dimensions: Dimensions
    mass: QuantityField | None = None
    override_mass: QuantityField | None = None
    override_mass_enabled: bool = False
    material: str | None = None
    material_density: QuantityField | None = None
    human_notes: str | None = None
    agent: AgentAnnotation | None = None
    cost: float | None = None
    step_path: str | None = None
    children: list[Component] = Field(default_factory=list)


# ── Component tree ─────────────────────────────────────────────────────────────


class Stage(QuantityModel):
    """One stage of the rocket (e.g., Sustainer, Booster)."""

    name: str
    components: list[Component] = Field(default_factory=list)
    cg: QuantityField | None = None
    cp: QuantityField | None = None
    stability_cal: float | None = None
    max_diameter: QuantityField | None = None


class ComponentTree(BaseModel):
    """Hierarchical component tree for a rocket project.

    Generated from an OpenRocket .ork file, annotated by the manufacturing
    agent, and consumed by the cadsmith agent to produce CAD.
    Written to ``<project_root>/gui/component_tree.json``.
    """

    schema_version: int = 1
    source_ork: str
    project_root: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    rocket_name: str
    stages: list[Stage] = Field(default_factory=list)
