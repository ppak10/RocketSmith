"""Pydantic models for the parts manifest.

The parts manifest is the contract between a design-for-X skill and the
downstream ``cadsmith`` subagent, ``generate-cad`` skill, and
``mass-calibration`` skill. It records per-component fate decisions
(print, fuse, purchase, skip), feature blocks for each printable part,
and the inverse lookup from OpenRocket components back to the part that
absorbed them.

The schema here mirrors the "parts_manifest.json Schema" section in
``skills/design-for-additive-manufacturing/SKILL.md``. If one changes,
the other must too. Unit tests lock down the mapping to catch drift.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Fate(str, Enum):
    """Per-component decision made by a design-for-X skill.

    ``print``     — generate CAD for this component as its own printed part
    ``purchase``  — source this component as COTS (not printed, not fused)
    ``skip``      — non-physical assembly item (parachute, ballast) or
                    a component that has been fused into another printed part
    """

    PRINT = "print"
    PURCHASE = "purchase"
    SKIP = "skip"


class ManufacturingMethod(str, Enum):
    """Manufacturing method the manifest was generated for.

    Only ``additive`` is fully implemented today. ``hybrid`` and
    ``traditional`` are placeholder values for forthcoming skills.
    """

    ADDITIVE = "additive"
    HYBRID = "hybrid"
    TRADITIONAL = "traditional"


class Directories(BaseModel):
    """Project-root-relative directory names for each artefact type."""

    scripts: str = "cadsmith"
    step: str = "CAD"
    gcode: str = "gcode"
    visualizations: str = "visualizations"


class Modification(BaseModel):
    """A detail feature applied to an existing base STEP during Pass 2.

    Modifications are additive or subtractive operations on the base
    geometry produced by the ``generate-structures`` skill. Typical
    examples: radial heat-set holes, clearance through-holes, rail
    button pockets, camera mounts, vent holes, weight-relief pockets.

    The ``kind`` field identifies the modification type; recipe-specific
    fields vary and are passed through via ``extra="allow"``. The
    ``modify-structures`` skill documents the supported kinds and their
    per-kind field shapes.
    """

    kind: str
    purpose: str | None = None

    model_config = {"extra": "allow"}


class Part(BaseModel):
    """One printable part.

    ``derived_from`` lists the OpenRocket component identifiers (formatted
    as ``Type:Name``) that contribute to this part. A simple part derives
    from one component; a fused part derives from several. The downstream
    ``mass-calibration`` skill uses this list to distribute the measured
    filament weight back across the constituent OR components.

    ``features`` is the base-geometry recipe consumed by the
    ``generate-structures`` skill in Pass 1. ``modifications`` is the
    detail-feature list consumed by ``modify-structures`` in Pass 2 —
    it starts empty and is populated only when DFAM (or the user via
    fusion_overrides) requests specific modifications like retention
    holes, accessory mounts, or vent holes.
    """

    name: str
    script_path: str
    step_path: str
    gcode_path: str
    derived_from: list[str]
    fate: Fate = Fate.PRINT
    features: dict[str, Any] = Field(default_factory=dict)
    modifications: list[Modification] = Field(default_factory=list)


class PurchasedItem(BaseModel):
    """An OR component sourced as COTS rather than printed."""

    derived_from: str
    description: str
    suggested_source: str | None = None


class SkippedComponent(BaseModel):
    """An OR component that becomes neither a printed part nor a COTS item.

    Includes non-physical assembly items (parachutes, ballast) and
    components that have been fused into another printed part (in which
    case ``reason`` names the target part).
    """

    name: str
    reason: str


class Assembly(BaseModel):
    """Optional multi-part STEP assembly composing several parts."""

    name: str
    step_path: str
    parts_fore_to_aft: list[str]


class Decision(BaseModel):
    """Auditable record of one fusion / fate decision.

    Every non-default choice should produce one of these so the user (and
    the agent in a future session) can understand *why* the manifest looks
    the way it does.
    """

    decision: str
    policy_default: str
    chosen: str
    reason: str


class PartsManifest(BaseModel):
    """Authoritative parts manifest produced by a design-for-X skill.

    Written to ``<project_root>/parts_manifest.json``. Consumed by:

    - ``generate-cad`` skill / ``cadsmith`` subagent — iterates ``parts``
      to produce STEP files
    - ``prusaslicer`` subagent — slices each ``step_path`` to ``gcode_path``
    - ``mass-calibration`` skill — uses ``component_to_part_map`` to
      attribute filament weights back to OR components
    """

    schema_version: int = 1
    source_ork: str
    project_root: str
    default_policy: ManufacturingMethod
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    directories: Directories = Field(default_factory=Directories)
    parts: list[Part] = Field(default_factory=list)
    purchased_items: list[PurchasedItem] = Field(default_factory=list)
    skipped_components: list[SkippedComponent] = Field(default_factory=list)
    assemblies: list[Assembly] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    component_to_part_map: dict[str, str] = Field(default_factory=dict)
