from enum import Enum
from pathlib import Path
from typing import Literal

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


class ConfigType(str, Enum):
    PRINTER = "printer"
    FILAMENT = "filament"
    PRINT = "print"


ConfigAction = Literal["list", "show", "create", "set", "delete"]


class ConfigEntry(BaseModel):
    """Metadata for a single PrusaSlicer config file."""

    name: str
    config_type: ConfigType
    path: Path


class ConfigSettings(BaseModel):
    """A PrusaSlicer config file with its parsed key-value settings."""

    name: str
    config_type: ConfigType
    path: Path
    settings: dict[str, str]


class ConfigListResult(BaseModel):
    """Result of listing PrusaSlicer config files."""

    configs: list[ConfigEntry]
    count: int
