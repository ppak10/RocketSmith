from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pint import Quantity
from pydantic import Field
from pintdantic import QuantityModel, QuantityField


class UnitVector(QuantityModel):
    """3D vector with unit-aware components (defaults to millimetres)."""

    x: QuantityField = (0.0, "mm")
    y: QuantityField = (0.0, "mm")
    z: QuantityField = (0.0, "mm")

    @classmethod
    def from_vector(cls, v, precision: int = 3) -> UnitVector:
        """Create from a build123d Vector or BoundBox.size."""
        return cls(
            x=round(v.X, precision), y=round(v.Y, precision), z=round(v.Z, precision)
        )

    @classmethod
    def deg(cls, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> UnitVector:
        """Create a vector in degrees."""
        return cls(x=Quantity(x, "deg"), y=Quantity(y, "deg"), z=Quantity(z, "deg"))


# ── Assembly models ─────────────────────────────────────────────────────────


class Part(QuantityModel):
    """A single part — printed or purchased."""

    name: str
    stl_path: str | None = None
    step_path: str | None = None
    brep_path: str | None = None
    bounding_box: UnitVector | None = None
    color: str = "#cccccc"
    cost: float | None = None
    description: str | None = None
    id: str | None = None
    volume: QuantityField | None = None
    surface_area: QuantityField | None = None
    center_of_mass: UnitVector | None = None
    mass: QuantityField | None = None


class AssemblyPart(Part):
    """A part placed in the assembly with position and rotation."""

    position: UnitVector = Field(default_factory=UnitVector)
    rotation: UnitVector = Field(default_factory=lambda: UnitVector.deg())


class Assembly(QuantityModel):
    """Spatial layout of parts for the 3D viewer."""

    schema_version: int = 1
    project_root: str | None = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    parts: list[AssemblyPart] = Field(default_factory=list)
    total_length: QuantityField = (0.0, "mm")
