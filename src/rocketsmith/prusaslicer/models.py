from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class Material(str, Enum):
    PLA = "pla"
    PETG = "petg"
    ABS = "abs"


# Density in g/cm³ for each material
MATERIAL_DENSITY: dict[Material, float] = {
    Material.PLA: 1.24,
    Material.PETG: 1.27,
    Material.ABS: 1.04,
}


class PrusaSlicerResult(BaseModel):
    """Output from a PrusaSlicer slicing operation."""

    gcode_path: Path
    material: Material = Material.PLA
    print_time_seconds: float | None = None
    filament_used_mm: float | None = None
    filament_used_cm3: float | None = None
    filament_used_g: float | None = None
    total_layers: int | None = None
