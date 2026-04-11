from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float


class CenterOfMass(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float


class CADSmithModelInfo(BaseModel):
    volume_mm3: float
    volume_cm3: float
    surface_area_mm2: float
    bounding_box_mm: BoundingBox
    center_of_mass_mm: CenterOfMass
    mass_g: float | None = None


# ── Assembly models ─────────────────────────────────────────────────────────


class Part(BaseModel):
    """A single part — printed or purchased."""

    name: str
    stl_path: str | None = None
    step_path: str | None = None
    bounding_box_mm: tuple[float, float, float] | None = None
    color: str = "#cccccc"
    cost: float | None = None
    description: str | None = None
    id: str | None = None


class AssemblyPart(Part):
    """A part placed in the assembly with position and rotation."""

    position_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0)


class Assembly(BaseModel):
    """Spatial layout of parts for the 3D viewer."""

    schema_version: int = 1
    project_root: str | None = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    parts: list[AssemblyPart] = Field(default_factory=list)
    total_length_mm: float = 0.0
