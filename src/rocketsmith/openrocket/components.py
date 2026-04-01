import contextlib

from pathlib import Path

# Maps CLI type names to OpenRocket Java class names
COMPONENT_TYPES = {
    "nose-cone": "NoseCone",
    "body-tube": "BodyTube",
    "inner-tube": "InnerTube",
    "transition": "Transition",
    "fin-set": "TrapezoidFinSet",
    "parachute": "Parachute",
    "mass": "MassComponent",
}

# Maps component type key (CLI name or Java class name) to preset type key
_COMPONENT_TO_PRESET_TYPE = {
    "body-tube": "body-tube",
    "nose-cone": "nose-cone",
    "transition": "transition",
    "parachute": "parachute",
    "BodyTube": "body-tube",
    "NoseCone": "nose-cone",
    "Transition": "transition",
    "Parachute": "parachute",
}


def _setup_jvm(jar_path: Path) -> None:
    from rocketsmith.openrocket.utils import get_openrocket_jvm
    import os

    jvm = get_openrocket_jvm(jar_path)
    if jvm:
        os.environ["JAVA_HOME"] = str(jvm.parent.parent.parent)


class _StubInstance:
    """Minimal OpenRocketInstance substitute for a JVM that is already running.

    JPype can only be started once per process. When the JVM is already live
    (e.g. in a test session that suppresses shutdown), we create this stub so
    that orhelper.Helper can be constructed without restarting the JVM.
    """

    def __init__(self):
        import jpype

        self.started = True
        self.openrocket = jpype.JPackage("net").sf.openrocket


@contextlib.contextmanager
def _or_context(jar_path: Path):
    """Open an OpenRocket context, reusing an already-running JVM if present.

    The JVM can only be started once per Python process. We deliberately never
    call shutdownJVM() so that subsequent calls within the same process can
    reuse the running JVM via _StubInstance.
    """
    import jpype
    import orhelper

    if jpype.isJVMStarted():
        yield _StubInstance()
    else:
        _setup_jvm(jar_path)
        instance = orhelper.OpenRocketInstance(str(jar_path), log_level="ERROR")
        instance.__enter__()
        # Do not call instance.__exit__() — shutdownJVM() would prevent any
        # subsequent tool call in this process from restarting the JVM.
        yield instance


def _resolve_preset(type_key: str, part_no: str, manufacturer: str | None):
    """Look up a ComponentPreset by type key (CLI name or Java class name) and part number.

    Must be called inside an active _or_context so the JVM and Application are live.
    Raises ValueError if the preset cannot be found.
    """
    import jpype
    from rocketsmith.openrocket.database import PRESET_TYPES

    preset_type = _COMPONENT_TO_PRESET_TYPE.get(type_key)
    if preset_type is None:
        raise ValueError(
            f"Component type '{type_key}' does not support presets. "
            f"Supported: {', '.join(_COMPONENT_TO_PRESET_TYPE)}"
        )

    java_type_name = PRESET_TYPES[preset_type]
    Application = jpype.JPackage("net").sf.openrocket.startup.Application
    CP = jpype.JPackage("net").sf.openrocket.preset.ComponentPreset
    java_type = getattr(CP.Type, java_type_name)
    presets = Application.getComponentPresetDao().listForType(java_type)

    for i in range(presets.size()):
        p = presets.get(i)
        if str(p.getPartNo()).lower() == part_no.lower():
            if (
                manufacturer is None
                or manufacturer.lower() in str(p.getManufacturer()).lower()
            ):
                return p

    suffix = f" for manufacturer '{manufacturer}'" if manufacturer else ""
    raise ValueError(f"Preset '{part_no}' not found{suffix}.")


def _resolve_material(material_name: str, material_type: str | None):
    """Look up a Material object by name, optionally restricted to a type.

    Must be called inside an active _or_context so the JVM is live.
    Raises ValueError if the material cannot be found.
    """
    import jpype
    from rocketsmith.openrocket.database import MATERIAL_TYPES

    Databases = jpype.JPackage("net").sf.openrocket.database.Databases

    if material_type is not None:
        if material_type not in MATERIAL_TYPES:
            raise ValueError(
                f"Unknown material type '{material_type}'. "
                f"Valid: {', '.join(sorted(MATERIAL_TYPES))}"
            )
        dbs = [
            {
                "bulk": Databases.BULK_MATERIAL,
                "surface": Databases.SURFACE_MATERIAL,
                "line": Databases.LINE_MATERIAL,
            }[material_type]
        ]
    else:
        dbs = [
            Databases.BULK_MATERIAL,
            Databases.SURFACE_MATERIAL,
            Databases.LINE_MATERIAL,
        ]

    for db in dbs:
        for mat in db:
            if str(mat.getName()).lower() == material_name.lower():
                return mat

    raise ValueError(f"Material '{material_name}' not found.")


def _save_doc(doc, output_path: Path) -> None:
    from java.io import File
    from net.sf.openrocket.file import GeneralRocketSaver
    from net.sf.openrocket.document import StorageOptions

    opts = StorageOptions()
    opts.setFileType(StorageOptions.FileType.OPENROCKET)
    opts.setSaveSimulationData(True)

    GeneralRocketSaver().save(File(str(output_path)), doc, opts)


def _extract_properties(comp) -> dict:
    """Extract readable properties from a Java RocketComponent."""
    type_name = str(comp.getClass().getSimpleName())
    props = {}

    try:
        props["length_m"] = round(float(comp.getLength()), 4)
    except Exception:
        pass

    if type_name in ("NoseCone", "Transition"):
        try:
            props["fore_diameter_m"] = round(float(comp.getForeRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["aft_diameter_m"] = round(float(comp.getAftRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["shape"] = str(comp.getShapeType().name()).lower()
        except Exception:
            pass
        try:
            props["thickness_m"] = round(float(comp.getThickness()), 4)
        except Exception:
            pass

    elif type_name in ("BodyTube", "InnerTube"):
        try:
            props["outer_diameter_m"] = round(float(comp.getOuterRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["inner_diameter_m"] = round(float(comp.getInnerRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["thickness_m"] = round(float(comp.getThickness()), 4)
        except Exception:
            pass
        try:
            props["motor_mount"] = bool(comp.isMotorMount())
        except Exception:
            pass

    elif type_name == "TrapezoidFinSet":
        try:
            props["fin_count"] = int(comp.getFinCount())
        except Exception:
            pass
        try:
            props["root_chord_m"] = round(float(comp.getRootChord()), 4)
        except Exception:
            pass
        try:
            props["tip_chord_m"] = round(float(comp.getTipChord()), 4)
        except Exception:
            pass
        try:
            props["span_m"] = round(float(comp.getSpan()), 4)
        except Exception:
            pass
        try:
            props["sweep_m"] = round(float(comp.getSweep()), 4)
        except Exception:
            pass
        try:
            props["thickness_m"] = round(float(comp.getThickness()), 4)
        except Exception:
            pass

    elif type_name == "Parachute":
        try:
            props["diameter_m"] = round(float(comp.getDiameter()), 4)
        except Exception:
            pass
        try:
            props["cd"] = round(float(comp.getCD()), 3)
        except Exception:
            pass

    elif type_name == "MassComponent":
        try:
            props["mass_kg"] = round(float(comp.getMass()), 6)
        except Exception:
            pass

    try:
        preset = comp.getPresetComponent()
        if preset is not None:
            props["preset_manufacturer"] = str(preset.getManufacturer())
            props["preset_part_no"] = str(preset.getPartNo())
    except Exception:
        pass

    try:
        mat = comp.getMaterial()
        if mat is not None:
            props["material"] = str(mat.getName())
            props["material_density_kg_m3"] = round(float(mat.getDensity()), 4)
    except Exception:
        pass

    try:
        props["axial_offset_m"] = round(float(comp.getAxialOffset()), 4)
    except Exception:
        pass

    try:
        props["axial_offset_method"] = str(comp.getAxialMethod().name()).lower()
    except Exception:
        pass

    return props


def _walk_tree(comp, depth: int = 0) -> list[dict]:
    """Recursively collect component info into a flat list."""
    entry = {
        "depth": depth,
        "type": str(comp.getClass().getSimpleName()),
        "name": str(comp.getName()),
        **_extract_properties(comp),
    }
    results = [entry]
    for i in range(comp.getChildCount()):
        results.extend(_walk_tree(comp.getChild(i), depth + 1))
    return results


def _find_by_name(helper, rocket, name: str):
    try:
        return helper.get_component_named(rocket, name)
    except ValueError:
        raise ValueError(f"Component '{name}' not found.")


def _find_default_parent(rocket, java_type_name: str):
    """Return the appropriate default parent for a new component."""
    INTERNAL_TYPES = {
        "TrapezoidFinSet",
        "EllipticalFinSet",
        "Parachute",
        "MassComponent",
        "ShockCord",
        "Streamer",
        "InnerTube",
    }

    first_stage = None
    last_body_tube = None

    for i in range(rocket.getChildCount()):
        child = rocket.getChild(i)
        if (
            str(child.getClass().getSimpleName()) == "AxialStage"
            and first_stage is None
        ):
            first_stage = child
            for j in range(child.getChildCount()):
                gc = child.getChild(j)
                if str(gc.getClass().getSimpleName()) == "BodyTube":
                    last_body_tube = gc

    if java_type_name in INTERNAL_TYPES:
        if last_body_tube is None:
            raise ValueError(
                "No BodyTube found in first stage — add a body tube first."
            )
        return last_body_tube
    else:
        if first_stage is None:
            raise ValueError("No AxialStage found in rocket.")
        return first_stage


def _apply_properties(comp, java_type_name: str, **kwargs) -> None:
    """Apply non-None keyword properties to a Java RocketComponent."""
    if kwargs.get("name") is not None:
        comp.setName(kwargs["name"])

    if kwargs.get("length") is not None:
        comp.setLength(float(kwargs["length"]))

    if java_type_name in ("NoseCone", "Transition"):
        if kwargs.get("diameter") is not None:
            comp.setAftRadius(float(kwargs["diameter"]) / 2)
        if kwargs.get("fore_diameter") is not None:
            comp.setForeRadius(float(kwargs["fore_diameter"]) / 2)
        if kwargs.get("aft_diameter") is not None:
            comp.setAftRadius(float(kwargs["aft_diameter"]) / 2)
        if kwargs.get("shape") is not None:
            from net.sf.openrocket.rocketcomponent import Transition as JTransition

            shape = JTransition.Shape.valueOf(kwargs["shape"].upper())
            comp.setShapeType(shape)
        if kwargs.get("thickness") is not None:
            comp.setThickness(float(kwargs["thickness"]))

    elif java_type_name in ("BodyTube", "InnerTube"):
        if kwargs.get("diameter") is not None:
            comp.setOuterRadius(float(kwargs["diameter"]) / 2)
        if kwargs.get("thickness") is not None:
            comp.setThickness(float(kwargs["thickness"]))

    elif java_type_name == "TrapezoidFinSet":
        if kwargs.get("count") is not None:
            comp.setFinCount(int(kwargs["count"]))
        if kwargs.get("root_chord") is not None:
            comp.setRootChord(float(kwargs["root_chord"]))
        if kwargs.get("tip_chord") is not None:
            comp.setTipChord(float(kwargs["tip_chord"]))
        if kwargs.get("span") is not None:
            comp.setHeight(float(kwargs["span"]))
        if kwargs.get("sweep") is not None:
            comp.setSweep(float(kwargs["sweep"]))
        if kwargs.get("thickness") is not None:
            comp.setThickness(float(kwargs["thickness"]))

    elif java_type_name == "Parachute":
        if kwargs.get("diameter") is not None:
            comp.setDiameter(float(kwargs["diameter"]))
        if kwargs.get("cd") is not None:
            comp.setCD(float(kwargs["cd"]))

    elif java_type_name == "MassComponent":
        if kwargs.get("mass") is not None:
            comp.setMass(float(kwargs["mass"]))

    # Axial positioning — applies to all component types.
    # Always set the method before the offset so the new method interprets the value correctly.
    if kwargs.get("axial_offset_method") is not None:
        import jpype

        AxialMethod = jpype.JPackage("net").sf.openrocket.rocketcomponent.AxialMethod
        comp.setAxialMethod(AxialMethod.valueOf(kwargs["axial_offset_method"].upper()))
    if kwargs.get("axial_offset_m") is not None:
        comp.setAxialOffset(float(kwargs["axial_offset_m"]))


# ── Public API ────────────────────────────────────────────────────────────────


def inspect_ork(ork_path: Path, jar_path: Path) -> list[dict]:
    """Return the full component tree of an .ork file as a flat list."""
    import orhelper

    with _or_context(jar_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))
        return _walk_tree(doc.getRocket())


def read_component(ork_path: Path, component_name: str, jar_path: Path) -> dict:
    """Return properties of a single named component."""
    import orhelper

    with _or_context(jar_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))
        comp = _find_by_name(helper, doc.getRocket(), component_name)
        return {
            "type": str(comp.getClass().getSimpleName()),
            "name": str(comp.getName()),
            **_extract_properties(comp),
        }


def new_ork(name: str, output_path: Path, jar_path: Path) -> Path:
    """Create a new .ork file with an empty Rocket and one AxialStage."""
    with _or_context(jar_path):
        from net.sf.openrocket.document import OpenRocketDocumentFactory
        from net.sf.openrocket.rocketcomponent import AxialStage

        doc = OpenRocketDocumentFactory.createEmptyRocket()
        rocket = doc.getRocket()
        rocket.setName(name)

        stage = AxialStage()
        stage.setName("Stage 1")
        rocket.addChild(stage)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        _save_doc(doc, output_path)

    return output_path


def create_component(
    ork_path: Path,
    component_type: str,
    jar_path: Path,
    parent_name: str | None = None,
    preset_part_no: str | None = None,
    preset_manufacturer: str | None = None,
    material_name: str | None = None,
    material_type: str | None = None,
    **kwargs,
) -> dict:
    """Add a new component to an .ork file and save in-place."""
    import jpype
    import orhelper

    java_type_name = COMPONENT_TYPES.get(component_type)
    if java_type_name is None:
        raise ValueError(
            f"Unknown component type '{component_type}'. "
            f"Valid types: {', '.join(COMPONENT_TYPES)}"
        )

    with _or_context(jar_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))
        rocket = doc.getRocket()

        parent = (
            _find_by_name(helper, rocket, parent_name)
            if parent_name
            else _find_default_parent(rocket, java_type_name)
        )

        comp_cls = getattr(
            jpype.JPackage("net").sf.openrocket.rocketcomponent, java_type_name
        )
        comp = comp_cls()

        # Load preset first — establishes baseline geometry and material
        if preset_part_no is not None:
            preset = _resolve_preset(
                component_type, preset_part_no, preset_manufacturer
            )
            comp.loadPreset(preset)

        # Apply explicit dimension overrides on top of preset (or standalone)
        _apply_properties(comp, java_type_name, **kwargs)

        # Apply explicit material override last — takes precedence over preset's material
        if material_name is not None:
            mat = _resolve_material(material_name, material_type)
            comp.setMaterial(mat)

        parent.addChild(comp)

        result = {
            "type": java_type_name,
            "name": str(comp.getName()),
            **_extract_properties(comp),
        }
        _save_doc(doc, ork_path)

    return result


def update_component(
    ork_path: Path,
    component_name: str,
    jar_path: Path,
    preset_part_no: str | None = None,
    preset_manufacturer: str | None = None,
    material_name: str | None = None,
    material_type: str | None = None,
    **kwargs,
) -> dict:
    """Update properties of a named component and save in-place."""
    import orhelper

    with _or_context(jar_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))
        comp = _find_by_name(helper, doc.getRocket(), component_name)
        java_type_name = str(comp.getClass().getSimpleName())

        # Load preset first — resets geometry and material to preset baseline
        if preset_part_no is not None:
            preset = _resolve_preset(
                java_type_name, preset_part_no, preset_manufacturer
            )
            comp.loadPreset(preset)

        # Apply explicit dimension overrides
        _apply_properties(comp, java_type_name, **kwargs)

        # Apply explicit material override last
        if material_name is not None:
            mat = _resolve_material(material_name, material_type)
            comp.setMaterial(mat)

        result = {
            "type": java_type_name,
            "name": str(comp.getName()),
            **_extract_properties(comp),
        }
        _save_doc(doc, ork_path)

    return result


def delete_component(ork_path: Path, component_name: str, jar_path: Path) -> str:
    """Remove a named component from an .ork file and save in-place."""
    import orhelper

    with _or_context(jar_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))
        comp = _find_by_name(helper, doc.getRocket(), component_name)
        parent = comp.getParent()

        if parent is None:
            raise ValueError(
                f"Cannot delete '{component_name}': it is the rocket root."
            )

        name = str(comp.getName())
        parent.removeChild(comp)
        _save_doc(doc, ork_path)

    return name
