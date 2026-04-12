from pathlib import Path

from pint import Quantity

from rocketsmith.cadsmith.models import Part, UnitVector

SUPPORTED_SUFFIXES = {".step", ".stp", ".brep"}


def extract_part(
    path: Path,
    material_density_kg_m3: float | None = None,
    display_name: str | None = None,
) -> Part:
    """Extract geometric properties from a STEP or BREP file.

    Args:
        path: Path to the STEP (.step/.stp) or BREP (.brep) file.
        material_density_kg_m3: Optional material density. When provided,
            mass is calculated from volume x density.
        display_name: Optional human-readable name for the part.
            Falls back to the filename stem if not provided.

    Returns:
        Part with volume, surface area, bounding box, centre of mass,
        and file path populated. mass is set only when density is given.
    """
    suffix = path.suffix.lower()
    if suffix in {".step", ".stp"}:
        from build123d import import_step

        shape = import_step(str(path))
    elif suffix == ".brep":
        from build123d import import_brep

        shape = import_brep(str(path))
    else:
        raise ValueError(
            f"Unsupported file format '{suffix}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    bbox = shape.bounding_box()
    com = shape.center()

    mass = None
    if material_density_kg_m3 is not None:
        volume_m3 = shape.volume * 1e-9  # mm³ → m³
        mass = Quantity(round(volume_m3 * material_density_kg_m3 * 1000, 2), "g")

    path_kwargs: dict[str, str] = {}
    if suffix in {".step", ".stp"}:
        path_kwargs["step_path"] = str(path)
    elif suffix == ".brep":
        path_kwargs["brep_path"] = str(path)

    return Part(
        name=path.stem,
        display_name=display_name,
        **path_kwargs,
        volume=Quantity(round(shape.volume, 2), "mm**3"),
        surface_area=Quantity(round(shape.area, 2), "mm**2"),
        bounding_box=UnitVector.from_vector(bbox.size, precision=2),
        center_of_mass=UnitVector.from_vector(com),
        mass=mass,
    )
