"""Stability calculations for OpenRocket rockets.

Computes center of gravity (CG), center of pressure (CP), maximum
diameter, and static stability margin from a loaded OpenRocket rocket
and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StabilityResult:
    """Result of a static stability calculation."""

    cg_m: float
    cp_m: float
    max_diameter_m: float
    stability_cal: float | None

    @property
    def stability_pct(self) -> float | None:
        """Stability margin as a percentage (stability_cal * 100 / length equivalent)."""
        return None  # reserved for future use


def compute_cg(rocket) -> tuple[float, float]:
    """Walk the component tree and compute center of gravity.

    Args:
        rocket: An OpenRocket Rocket Java object.

    Returns:
        (cg_x_m, max_diameter_m) — CG position in metres from the nose
        tip, and the maximum outer diameter in metres.
    """
    import orhelper

    total_mass = 0.0
    total_moment = 0.0
    max_d = 0.0

    for c in orhelper.JIterator(rocket):
        try:
            m = float(c.getMass())
        except Exception:
            m = 0.0
        if m > 0:
            total_mass += m
            abs_x = 0.0
            curr = c
            while curr is not None:
                try:
                    p = curr.getPosition()
                    try:
                        abs_x += float(p.x)
                    except Exception:
                        abs_x += float(p)
                except Exception:
                    pass
                curr = curr.getParent()

            try:
                cg_local = c.getCG()
                if cg_local is not None:
                    total_moment += m * (abs_x + float(cg_local.x))
                else:
                    total_moment += m * abs_x
            except Exception:
                total_moment += m * abs_x

        try:
            d = float(c.getOuterRadius()) * 2
            if d > max_d:
                max_d = d
        except Exception:
            pass

    cg_x = total_moment / total_mass if total_mass > 0 else 0.0
    return cg_x, max_d


def compute_cp(config) -> float:
    """Compute center of pressure using the Barrowman method.

    Args:
        config: An OpenRocket FlightConfiguration Java object.

    Returns:
        CP position in metres from the nose tip, or 0.0 if the
        calculation fails.
    """
    import jpype

    try:
        BC = jpype.JClass("net.sf.openrocket.aerodynamics.BarrowmanCalculator")
        FC = jpype.JClass("net.sf.openrocket.aerodynamics.FlightConditions")
        WS = jpype.JClass("net.sf.openrocket.logging.WarningSet")
        calc = BC()
        conds = FC(config)
        warnings = WS()
        return float(calc.getCP(config, conds, warnings).x)
    except Exception:
        return 0.0


def barrowman_stability(rocket, config) -> StabilityResult:
    """Compute full static stability using the Barrowman method.

    Args:
        rocket: An OpenRocket Rocket Java object.
        config: An OpenRocket FlightConfiguration Java object.

    Returns:
        A StabilityResult with CG, CP, max diameter, and stability
        margin in calibers.
    """
    cg_x, max_d = compute_cg(rocket)
    cp_x = compute_cp(config)

    stability_cal = None
    if max_d > 0:
        stability_cal = round((cp_x - cg_x) / max_d, 2)

    return StabilityResult(
        cg_m=round(cg_x, 4),
        cp_m=round(cp_x, 4),
        max_diameter_m=round(max_d, 4),
        stability_cal=stability_cal,
    )
