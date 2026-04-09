"""Convert an OpenRocket design into CAD-ready (millimetre) parameters.

This module is the "glue" between an OpenRocket .ork file and a build123d
CAD workflow. OpenRocket stores every dimension in metres; build123d and
most STEP consumers expect millimetres. Converting by hand is a common
source of off-by-1000 bugs, so this helper does it once, per-component,
and attaches the derived values and red-flag notes that the cad-handoff
skill documents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rocketsmith.openrocket.components import inspect_rocket_file

# Fields in the openrocket inspect output that are in metres and should
# be converted to millimetres. Field name ``foo_m`` becomes ``foo_mm``.
_METRE_FIELDS = {
    "length_m",
    "outer_diameter_m",
    "inner_diameter_m",
    "fore_diameter_m",
    "aft_diameter_m",
    "thickness_m",
    "root_chord_m",
    "tip_chord_m",
    "span_m",
    "sweep_m",
    "diameter_m",
    "axial_offset_m",
    "position_x_m",
}

# Fields that stay in their original units (ints, enums, strings, density).
_PASSTHROUGH_FIELDS = {
    "type",
    "name",
    "depth",
    "shape",
    "fin_count",
    "motor_mount",
    "cd",
    "axial_offset_method",
    "preset_manufacturer",
    "preset_part_no",
    "material",
    "material_density_kg_m3",
    "override_mass_kg",
    "override_mass_enabled",
}


def _convert_component(comp: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a component dict with every metre field rewritten to mm."""
    out: dict[str, Any] = {}
    for key, value in comp.items():
        if key in _METRE_FIELDS and isinstance(value, (int, float)):
            mm_key = key[:-2] + "_mm"  # strip "_m", append "_mm"
            out[mm_key] = round(float(value) * 1000.0, 4)
        elif key in _PASSTHROUGH_FIELDS:
            out[key] = value
        else:
            # Unknown field — pass through untouched so we never silently
            # drop data added by future OpenRocket versions.
            out[key] = value
    return out


def _find_motor_mount(components: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the best motor mount candidate from a converted components list.

    Prefers an InnerTube; falls back to the first BodyTube flagged as a
    motor mount; returns None if neither is found.
    """
    for c in components:
        if c.get("type") == "InnerTube":
            return c
    for c in components:
        if c.get("type") == "BodyTube" and c.get("motor_mount"):
            return c
    return None


def _build_handoff_notes(
    components: list[dict[str, Any]],
    motor_mount: dict[str, Any] | None,
    body_tube_id_mm: float | None,
) -> list[str]:
    """Generate a short list of human-readable handoff gotchas.

    These mirror the rules in skills/cad-handoff/SKILL.md so that an agent
    that only sees the cad_handoff tool output still gets the red flags.
    """
    notes: list[str] = [
        "All dimensions below are in millimetres (mm). OpenRocket stores metres; "
        "this tool has already multiplied every length by 1000.",
        "Fins must be integrated into the lower airframe STEP file. Never "
        "write a separate parts/fins.step — that produces weak prints.",
    ]

    if body_tube_id_mm is not None:
        notes.append(
            f"Coupler OD should match the body tube ID "
            f"({body_tube_id_mm:.2f} mm) with a 2–3 mm wall. A typical coupler "
            "length is 1.0–1.5× body diameter."
        )

    if motor_mount is not None:
        mm_od = motor_mount.get("outer_diameter_mm")
        if mm_od is not None:
            notes.append(
                f"Motor mount tube ID should be motor case OD + ~0.5 mm "
                f"clearance. Centering ring ID should be the motor tube OD "
                f"({mm_od:.2f} mm) + 0.2 mm."
            )
        if body_tube_id_mm is not None:
            notes.append(
                f"Centering ring OD should be body tube ID "
                f"({body_tube_id_mm:.2f} mm) − 0.2 mm."
            )
    else:
        notes.append(
            "No motor mount found in the rocket. Add an inner-tube "
            "component sized to the motor case before running CAD handoff."
        )

    has_any_fin = any(c.get("type") == "TrapezoidFinSet" for c in components)
    if not has_any_fin:
        notes.append(
            "No fin set found. The lower airframe still needs fins before "
            "the design is flight-ready."
        )

    return notes


def cad_handoff(path: Path, jar_path: Path | None = None) -> dict[str, Any]:
    """Convert an OpenRocket design into CAD-ready (mm) parameters.

    Reads the component tree from an .ork or .rkt file via
    :func:`inspect_rocket_file`, converts every length from metres to
    millimetres, identifies the motor mount, computes useful derived
    values (body tube ID, max diameter, CG/CP in mm), and attaches a
    list of handoff red-flag notes.

    Args:
        path: Path to the .ork or .rkt design file.
        jar_path: Optional path to the OpenRocket JAR. If omitted the
            installed JAR is located automatically.

    Returns:
        A dict with the shape::

            {
                "units": "mm",
                "source_path": "<abs path>",
                "components": [ ... per-component dicts in mm ... ],
                "derived": {
                    "cg_x_mm": float | None,
                    "cp_x_mm": float | None,
                    "max_diameter_mm": float | None,
                    "body_tube_id_mm": float | None,
                    "motor_mount": {name, outer_diameter_mm, ...} | None,
                },
                "handoff_notes": [str, ...],
            }
    """
    raw = inspect_rocket_file(path, jar_path=jar_path)

    components_mm = [_convert_component(c) for c in raw["components"]]

    # Find the primary airframe body tube (first BodyTube not acting as a
    # motor mount) — its ID is the reference for couplers and centering
    # rings.
    body_tube_id_mm: float | None = None
    for c in components_mm:
        if c.get("type") == "BodyTube" and not c.get("motor_mount"):
            id_val = c.get("inner_diameter_mm")
            if isinstance(id_val, (int, float)):
                body_tube_id_mm = float(id_val)
                break

    motor_mount = _find_motor_mount(components_mm)

    def _m_to_mm(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return round(float(value) * 1000.0, 4)
        return None

    derived = {
        "cg_x_mm": _m_to_mm(raw.get("cg_x")),
        "cp_x_mm": _m_to_mm(raw.get("cp_x")),
        "max_diameter_mm": _m_to_mm(raw.get("max_diameter_m")),
        "body_tube_id_mm": body_tube_id_mm,
        "motor_mount": motor_mount,
    }

    return {
        "units": "mm",
        "source_path": str(Path(path).resolve()),
        "components": components_mm,
        "derived": derived,
        "handoff_notes": _build_handoff_notes(
            components_mm, motor_mount, body_tube_id_mm
        ),
    }
