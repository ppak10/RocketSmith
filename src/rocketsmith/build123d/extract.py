from pathlib import Path

from rocketsmith.build123d.models import Build123dGeometry, BoundingBox, CenterOfMass


def extract_geometry(
    step_path: Path,
    material_density_kg_m3: float | None = None,
) -> Build123dGeometry:
    """Extract geometric properties from a STEP file.

    Args:
        step_path: Path to the STEP file.
        material_density_kg_m3: Optional material density. When provided,
            mass_g is calculated from volume × density.

    Returns:
        Build123dGeometry with volume, surface area, bounding box, and
        centre of mass. mass_g is populated only when density is given.
    """
    from build123d import import_step

    shape = import_step(str(step_path))

    bbox = shape.bounding_box()
    com = shape.center()

    mass_g = None
    if material_density_kg_m3 is not None:
        volume_m3 = shape.volume * 1e-9  # mm³ → m³
        mass_g = round(volume_m3 * material_density_kg_m3 * 1000, 2)

    return Build123dGeometry(
        volume_mm3=round(shape.volume, 2),
        volume_cm3=round(shape.volume * 1e-3, 3),
        surface_area_mm2=round(shape.area, 2),
        bounding_box_mm=BoundingBox(
            x_mm=round(bbox.size.X, 2),
            y_mm=round(bbox.size.Y, 2),
            z_mm=round(bbox.size.Z, 2),
        ),
        center_of_mass_mm=CenterOfMass(
            x_mm=round(com.X, 3),
            y_mm=round(com.Y, 3),
            z_mm=round(com.Z, 3),
        ),
        mass_g=mass_g,
    )
