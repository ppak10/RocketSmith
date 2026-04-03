"""Body tube and transition profile calculations."""


def get_body_radius_at(comp: dict, x_m: float) -> float | None:
    """Return the outer radius of a BodyTube or Transition at absolute position x_m."""
    ctype = comp["type"]
    if ctype not in ("BodyTube", "Transition", "InnerTube", "TubeCoupler"):
        return None

    pos = comp.get("position_x_m")
    if pos is None:
        return None

    length = comp.get("length_m") or 0.0
    if length <= 0:
        return None

    if x_m < pos - 1e-9 or x_m > pos + length + 1e-9:
        return None

    if ctype in ("BodyTube", "InnerTube", "TubeCoupler"):
        return (comp.get("outer_diameter_m") or 0.0) / 2

    if ctype == "Transition":
        t = max(0.0, min(1.0, (x_m - pos) / length))
        fore_r = (comp.get("fore_diameter_m") or 0.0) / 2
        aft_r = (comp.get("aft_diameter_m") or 0.0) / 2
        return fore_r + (aft_r - fore_r) * t

    return None
