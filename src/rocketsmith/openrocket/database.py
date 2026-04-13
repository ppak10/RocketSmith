from pathlib import Path

# Maps CLI type names to ComponentPreset.Type Java enum names
PRESET_TYPES = {
    "body-tube": "BODY_TUBE",
    "nose-cone": "NOSE_CONE",
    "transition": "TRANSITION",
    "tube-coupler": "TUBE_COUPLER",
    "bulk-head": "BULK_HEAD",
    "centering-ring": "CENTERING_RING",
    "engine-block": "ENGINE_BLOCK",
    "launch-lug": "LAUNCH_LUG",
    "rail-button": "RAIL_BUTTON",
    "streamer": "STREAMER",
    "parachute": "PARACHUTE",
}

MATERIAL_TYPES = {"bulk", "surface", "line"}

# TypedKey field names on ComponentPreset and their Python output names
_PRESET_DIM_KEYS = [
    ("OUTER_DIAMETER", "outer_diameter_m"),
    ("INNER_DIAMETER", "inner_diameter_m"),
    ("LENGTH", "length_m"),
    ("THICKNESS", "thickness_m"),
    ("AFT_OUTER_DIAMETER", "aft_outer_diameter_m"),
    ("AFT_INNER_DIAMETER", "aft_inner_diameter_m"),
    ("FORE_OUTER_DIAMETER", "fore_outer_diameter_m"),
    ("FORE_INNER_DIAMETER", "fore_inner_diameter_m"),
    ("SHOULDER_OUTER_DIAMETER", "shoulder_outer_diameter_m"),
    ("SHOULDER_INNER_DIAMETER", "shoulder_inner_diameter_m"),
    ("SHOULDER_LENGTH", "shoulder_length_m"),
    ("DIAMETER", "diameter_m"),
    ("CD", "cd"),
    ("MASS", "mass_kg"),
]


def _extract_preset_props(p, CP) -> dict:
    """Extract available dimensional properties from a ComponentPreset."""
    props = {}
    for java_key, py_key in _PRESET_DIM_KEYS:
        try:
            key = getattr(CP, java_key)
            if p.has(key):
                val = p.get(key)
                try:
                    props[py_key] = round(float(val), 6)
                except Exception:
                    props[py_key] = str(val)
        except Exception:
            pass
    try:
        if p.has(CP.DESCRIPTION):
            props["description"] = str(p.get(CP.DESCRIPTION))
    except Exception:
        pass
    return props


def list_motors(
    jar_path: Path,
    *,
    manufacturer: str | None = None,
    impulse_class: str | None = None,
    diameter_mm: float | None = None,
    motor_type: str | None = None,
    name: str | None = None,
) -> list[dict]:
    """
    List available motors from the OpenRocket database.

    Args:
        jar_path: Path to the OpenRocket JAR.
        manufacturer: Filter by manufacturer name substring.
        impulse_class: Filter by impulse class letter (e.g. 'D', 'F', 'H').
        diameter_mm: Filter by motor diameter in mm (tolerance ±0.5 mm).
        motor_type: Filter by type substring: 'single-use', 'reloadable', 'hybrid'.
        name: Filter by motor common name or designation substring (case-insensitive).
    """
    import jpype
    from rocketsmith.openrocket.components import _or_context

    with _or_context(jar_path) as _:
        Application = jpype.JPackage("net").sf.openrocket.startup.Application
        motor_sets = Application.getThrustCurveMotorSetDatabase().getMotorSets()

        results = []
        for i in range(motor_sets.size()):
            ms = motor_sets.get(i)

            mfr = str(ms.getManufacturer())
            common_name = str(ms.getCommonName())
            designation = str(ms.getDesignation())
            mtype = str(ms.getType())
            dia_mm = round(float(ms.getDiameter()) * 1000, 1)

            if manufacturer and manufacturer.lower() not in mfr.lower():
                continue
            if impulse_class and not common_name.upper().startswith(
                impulse_class.upper()
            ):
                continue
            if diameter_mm is not None and abs(dia_mm - diameter_mm) > 0.5:
                continue
            if motor_type and motor_type.lower().replace(
                "-", ""
            ) not in mtype.lower().replace("-", ""):
                continue
            if name:
                needle = name.lower().replace("-", "").replace(" ", "")
                haystack_name = common_name.lower().replace("-", "").replace(" ", "")
                haystack_desig = designation.lower().replace("-", "").replace(" ", "")
                if needle not in haystack_name and needle not in haystack_desig:
                    continue

            m0 = ms.getMotors().get(0)
            entry = {
                "manufacturer": mfr,
                "designation": designation,
                "common_name": common_name,
                "type": mtype,
                "diameter_mm": dia_mm,
                "length_mm": round(float(ms.getLength()) * 1000, 1),
                "total_impulse_ns": round(float(m0.getTotalImpulseEstimate()), 2),
                "avg_thrust_n": round(float(m0.getAverageThrustEstimate()), 2),
                "burn_time_s": round(float(m0.getBurnTimeEstimate()), 3),
                "variant_count": int(ms.getMotorCount()),
            }
            try:
                entry["digest"] = str(m0.getDigest())
            except Exception:
                pass
            results.append(entry)

        return results


def list_presets(
    jar_path: Path,
    preset_type: str,
    *,
    manufacturer: str | None = None,
) -> list[dict]:
    """
    List manufacturer component presets for a given type.

    Args:
        jar_path: Path to the OpenRocket JAR.
        preset_type: One of the keys in PRESET_TYPES (e.g. 'body-tube', 'parachute').
        manufacturer: Filter by manufacturer name substring.
    """
    import jpype
    from rocketsmith.openrocket.components import _or_context

    java_type_name = PRESET_TYPES.get(preset_type)
    if java_type_name is None:
        raise ValueError(
            f"Unknown preset type '{preset_type}'. "
            f"Valid types: {', '.join(PRESET_TYPES)}"
        )

    with _or_context(jar_path) as _:
        Application = jpype.JPackage("net").sf.openrocket.startup.Application
        CP = jpype.JPackage("net").sf.openrocket.preset.ComponentPreset

        java_type = getattr(CP.Type, java_type_name)
        presets = Application.getComponentPresetDao().listForType(java_type)

        results = []
        for i in range(presets.size()):
            p = presets.get(i)
            mfr = str(p.getManufacturer())
            if manufacturer and manufacturer.lower() not in mfr.lower():
                continue
            results.append(
                {
                    "manufacturer": mfr,
                    "part_no": str(p.getPartNo()),
                    "type": preset_type,
                    **_extract_preset_props(p, CP),
                }
            )

        return results


def list_materials(jar_path: Path, material_type: str) -> list[dict]:
    """
    List materials of the given type.

    Args:
        jar_path: Path to the OpenRocket JAR.
        material_type: One of 'bulk', 'surface', 'line'.
    """
    import jpype
    from rocketsmith.openrocket.components import _or_context

    if material_type not in MATERIAL_TYPES:
        raise ValueError(
            f"Unknown material type '{material_type}'. "
            f"Valid types: {', '.join(sorted(MATERIAL_TYPES))}"
        )

    with _or_context(jar_path) as _:
        Databases = jpype.JPackage("net").sf.openrocket.database.Databases
        db = {
            "bulk": Databases.BULK_MATERIAL,
            "surface": Databases.SURFACE_MATERIAL,
            "line": Databases.LINE_MATERIAL,
        }[material_type]

        results = [
            {
                "name": str(mat.getName()),
                "density": round(float(mat.getDensity()), 6),
                "type": material_type,
            }
            for mat in db
        ]

        return sorted(results, key=lambda x: x["name"])
