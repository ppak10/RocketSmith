"""Nose cone profile calculations."""


def get_nose_cone_radius_at(comp: dict, x_m: float) -> float | None:
    """Return the outer radius of a NoseCone at absolute position x_m."""
    if comp["type"] != "NoseCone":
        return None

    pos = comp.get("position_x_m")
    if pos is None:
        return None

    length = comp.get("length_m") or 0.0
    if length <= 0:
        return None

    if x_m < pos - 1e-9 or x_m > pos + length + 1e-9:
        return None

    # Normalized position: 0 = front, 1 = rear
    t = max(0.0, min(1.0, (x_m - pos) / length))

    fore_r = (comp.get("fore_diameter_m") or 0.0) / 2
    aft_r = (comp.get("aft_diameter_m") or 0.0) / 2

    # Simple linear profile for now — OpenRocket's getShapeType()
    # would need more complex interpolation for true curves.
    return fore_r + (aft_r - fore_r) * t
