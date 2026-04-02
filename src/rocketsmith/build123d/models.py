from pydantic import BaseModel


class BoundingBox(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float


class CenterOfMass(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float


class Build123dGeometry(BaseModel):
    volume_mm3: float
    volume_cm3: float
    surface_area_mm2: float
    bounding_box_mm: BoundingBox
    center_of_mass_mm: CenterOfMass
    mass_g: float | None = None
