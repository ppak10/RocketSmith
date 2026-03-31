import contextlib

from pathlib import Path

# Maps CLI type names to OpenRocket Java class names
COMPONENT_TYPES = {
    "nose-cone": "NoseCone",
    "body-tube": "BodyTube",
    "transition": "Transition",
    "fin-set": "TrapezoidFinSet",
    "parachute": "Parachute",
    "mass": "MassComponent",
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

    elif type_name == "BodyTube":
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
    INTERNAL_TYPES = {"TrapezoidFinSet", "EllipticalFinSet", "Parachute", "MassComponent", "ShockCord", "Streamer"}

    first_stage = None
    last_body_tube = None

    for i in range(rocket.getChildCount()):
        child = rocket.getChild(i)
        if str(child.getClass().getSimpleName()) == "AxialStage" and first_stage is None:
            first_stage = child
            for j in range(child.getChildCount()):
                gc = child.getChild(j)
                if str(gc.getClass().getSimpleName()) == "BodyTube":
                    last_body_tube = gc

    if java_type_name in INTERNAL_TYPES:
        if last_body_tube is None:
            raise ValueError("No BodyTube found in first stage — add a body tube first.")
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

    elif java_type_name == "BodyTube":
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

    elif java_type_name == "Parachute":
        if kwargs.get("diameter") is not None:
            comp.setDiameter(float(kwargs["diameter"]))
        if kwargs.get("cd") is not None:
            comp.setCD(float(kwargs["cd"]))

    elif java_type_name == "MassComponent":
        if kwargs.get("mass") is not None:
            comp.setMass(float(kwargs["mass"]))


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

        comp_cls = getattr(jpype.JPackage("net").sf.openrocket.rocketcomponent, java_type_name)
        comp = comp_cls()
        _apply_properties(comp, java_type_name, **kwargs)
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
    **kwargs,
) -> dict:
    """Update properties of a named component and save in-place."""
    import orhelper

    with _or_context(jar_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))
        comp = _find_by_name(helper, doc.getRocket(), component_name)
        java_type_name = str(comp.getClass().getSimpleName())

        _apply_properties(comp, java_type_name, **kwargs)

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
            raise ValueError(f"Cannot delete '{component_name}': it is the rocket root.")

        name = str(comp.getName())
        parent.removeChild(comp)
        _save_doc(doc, ork_path)

    return name
