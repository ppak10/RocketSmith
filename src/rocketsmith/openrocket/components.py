import contextlib
import os
import sys
from pathlib import Path

# Maps CLI type names to OpenRocket Java class names
COMPONENT_TYPES = {
    "nose-cone": "NoseCone",
    "body-tube": "BodyTube",
    "inner-tube": "InnerTube",
    "transition": "Transition",
    "tube-coupler": "TubeCoupler",
    "fin-set": "TrapezoidFinSet",
    "parachute": "Parachute",
    "mass": "MassComponent",
}


@contextlib.contextmanager
def _silence_fds():
    """Temporarily redirect stdout/stderr FDs to /dev/null."""
    null_fd = os.open(os.devnull, os.O_RDWR)
    try:
        old_stdout = os.dup(1)
        old_stderr = os.dup(2)
        try:
            os.dup2(null_fd, 1)
            os.dup2(null_fd, 2)
            yield
        finally:
            os.dup2(old_stdout, 1)
            os.dup2(old_stderr, 2)
            os.close(old_stdout)
            os.close(old_stderr)
    finally:
        os.close(null_fd)


def _setup_jvm(jar_path: Path) -> None:
    from rocketsmith.openrocket.utils import get_openrocket_jvm

    jvm = get_openrocket_jvm(jar_path)
    if jvm:
        os.environ["JAVA_HOME"] = str(jvm.parent.parent.parent)


def _silence_jvm() -> None:
    """Redirect Java-side stdout/stderr to null and silence SLF4J/Logback."""
    import jpype

    try:
        System = jpype.JClass("java.lang.System")
        JFile = jpype.JClass("java.io.File")
        FileOutputStream = jpype.JClass("java.io.FileOutputStream")
        PrintStream = jpype.JClass("java.io.PrintStream")

        dev_null = "NUL" if sys.platform == "win32" else "/dev/null"
        null_ps = PrintStream(FileOutputStream(JFile(dev_null)))

        System.setOut(null_ps)
        System.setErr(null_ps)

        try:
            LoggerFactory = jpype.JClass("org.slf4j.LoggerFactory")
            context = LoggerFactory.getILoggerFactory()
            if "logback" in context.getClass().getName().lower():
                Level = jpype.JClass("ch.qos.logback.classic.Level")
                context.getLogger("ROOT").setLevel(Level.ERROR)
        except Exception:
            System.setProperty("org.slf4j.simpleLogger.defaultLogLevel", "error")
    except Exception:
        pass


class _StubInstance:
    """Minimal OpenRocketInstance substitute for a JVM that is already running."""

    def __init__(self):
        import jpype

        self.started = True
        self.openrocket = jpype.JPackage("net").sf.openrocket


@contextlib.contextmanager
def _or_context(jar_path: Path):
    """Open an OpenRocket context, reusing an already-running JVM if present."""
    import jpype
    import orhelper

    if jpype.isJVMStarted():
        _silence_jvm()
        yield _StubInstance()
    else:
        _setup_jvm(jar_path)
        with _silence_fds():
            instance = orhelper.OpenRocketInstance(str(jar_path), log_level="ERROR")
            instance.__enter__()
            _silence_jvm()
        yield instance


def _save_doc(doc, ork_path: Path) -> None:
    import jpype

    JFile = jpype.JClass("java.io.File")
    JGeneralRocketSaver = jpype.JClass("net.sf.openrocket.file.GeneralRocketSaver")
    JStorageOptions = jpype.JClass("net.sf.openrocket.document.StorageOptions")

    opts = JStorageOptions()
    saver = JGeneralRocketSaver(JFile(os.path.abspath(str(ork_path))))
    saver.save(doc, opts)


def inspect_ork(ork_path: Path, jar_path: Path | None = None) -> list[dict]:
    """Read component tree from .ork file and return as list of dicts."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper
        import jpype

        JFile = jpype.JClass("java.io.File")
        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        try:
            doc = helper.load_doc(path_str)
        except Exception:
            doc = helper.load_doc(JFile(path_str))
        rocket = doc.getRocket()

        results = []

        def _walk(comp, depth):
            # Extract properties
            props = _extract_properties(comp)
            props["depth"] = depth
            results.append(props)

            # Recurse children
            children = []
            try:
                for i in range(comp.getChildCount()):
                    children.append(comp.getChildAt(i))
            except Exception:
                try:
                    for child in comp.getChildren():
                        children.append(child)
                except Exception:
                    pass

            for child in children:
                _walk(child, depth + 1)

        _walk(rocket, 0)
        return results


def read_components(ork_path: Path) -> list[dict]:
    """Read component tree from .ork file."""
    return inspect_ork(ork_path)


def _extract_properties(comp) -> dict:
    """Extract dict of serializable properties from an OpenRocket component."""
    props = {
        "type": str(comp.getClass().getSimpleName()),
        "name": str(comp.getName()),
    }

    type_name = props["type"]

    if type_name in ("NoseCone", "Transition"):
        try:
            props["length_m"] = round(float(comp.getLength()), 4)
        except Exception:
            pass
        try:
            props["fore_diameter_m"] = round(float(comp.getForeRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["aft_diameter_m"] = round(float(comp.getAftRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["thickness_m"] = round(float(comp.getThickness()), 4)
        except Exception:
            pass

    elif type_name in ("BodyTube", "InnerTube", "TubeCoupler"):
        try:
            props["outer_diameter_m"] = round(float(comp.getOuterRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["inner_diameter_m"] = round(float(comp.getInnerRadius()) * 2, 4)
        except Exception:
            pass
        try:
            props["length_m"] = round(float(comp.getLength()), 4)
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
            props["cd"] = round(float(comp.getCD()), 2)
        except Exception:
            pass

    try:
        preset = comp.getComponentPreset()
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
        props["axial_offset_method"] = str(comp.getAxialOffsetMethod())
    except Exception:
        pass

    # Position X (absolute)
    try:
        # getPositionX() is the standard for absolute position from nose tip
        props["position_x_m"] = round(float(comp.getPositionX()), 4)
    except Exception:
        # Fallback: walk parents and add getPosition().x
        try:
            x = 0.0
            curr = comp
            while curr is not None:
                try:
                    # In some OR versions, getPosition() returns a Coordinate
                    p = curr.getPosition()
                    try:
                        x += float(p.x)
                    except:
                        x += float(p)
                except:
                    pass
                curr = curr.getParent()
            props["position_x_m"] = round(x, 4)
        except:
            props["position_x_m"] = 0.0

    return props


def update_component(ork_path: Path, component_name: str, **kwargs) -> dict | None:
    """Update properties of an existing component by name."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper
        import jpype

        JFile = jpype.JClass("java.io.File")
        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        try:
            doc = helper.load_doc(path_str)
        except Exception:
            doc = helper.load_doc(JFile(path_str))
        rocket = doc.getRocket()

        comp = None

        def _find(c):
            nonlocal comp
            if str(c.getName()) == component_name:
                comp = c
                return True
            for i in range(c.getChildCount()):
                if _find(c.getChildAt(i)):
                    return True
            return False

        _find(rocket)

        if comp is None:
            return None

        _apply_properties(comp, **kwargs)
        _save_doc(doc, ork_path)

        return _extract_properties(comp)


def _apply_properties(comp, **kwargs):
    """Apply dict of properties to an OpenRocket component."""
    import jpype

    java_type_name = str(comp.getClass().getSimpleName())

    if kwargs.get("name") is not None:
        comp.setName(str(kwargs["name"]))

    if java_type_name in ("NoseCone", "Transition"):
        if kwargs.get("length") is not None:
            comp.setLength(float(kwargs["length"]))
        if kwargs.get("fore_diameter") is not None:
            comp.setForeRadius(float(kwargs["fore_diameter"]) / 2)
        if kwargs.get("aft_diameter") is not None:
            comp.setAftRadius(float(kwargs["aft_diameter"]) / 2)
        if java_type_name == "NoseCone":
            if kwargs.get("shape") is not None:
                JNoseCone = jpype.JClass("net.sf.openrocket.rocketcomponent.NoseCone")
                shape = JNoseCone.Shape.valueOf(kwargs["shape"].upper())
                comp.setShapeType(shape)
        if java_type_name == "Transition":
            if kwargs.get("shape") is not None:
                JTransition = jpype.JClass(
                    "net.sf.openrocket.rocketcomponent.Transition"
                )
                shape = JTransition.Shape.valueOf(kwargs["shape"].upper())
                comp.setShapeType(shape)
        if kwargs.get("thickness") is not None:
            comp.setThickness(float(kwargs["thickness"]))

    elif java_type_name in ("BodyTube", "InnerTube", "TubeCoupler"):
        if kwargs.get("diameter") is not None:
            comp.setOuterRadius(float(kwargs["diameter"]) / 2)
        if kwargs.get("thickness") is not None:
            comp.setThickness(float(kwargs["thickness"]))
        if kwargs.get("length") is not None:
            comp.setLength(float(kwargs["length"]))
        if (
            java_type_name in ("BodyTube", "InnerTube")
            and kwargs.get("motor_mount") is not None
        ):
            comp.setMotorMount(bool(kwargs["motor_mount"]))

    elif java_type_name == "TrapezoidFinSet":
        if kwargs.get("fin_count") is not None:
            comp.setFinCount(int(kwargs["fin_count"]))
        if kwargs.get("root_chord") is not None:
            comp.setRootChord(float(kwargs["root_chord"]))
        if kwargs.get("tip_chord") is not None:
            comp.setTipChord(float(kwargs["tip_chord"]))
        if kwargs.get("span") is not None:
            comp.setSpan(float(kwargs["span"]))
        if kwargs.get("sweep") is not None:
            comp.setSweep(float(kwargs["sweep"]))
        if kwargs.get("thickness") is not None:
            comp.setThickness(float(kwargs["thickness"]))

    elif java_type_name == "Parachute":
        if kwargs.get("diameter") is not None:
            comp.setDiameter(float(kwargs["diameter"]))
        if kwargs.get("cd") is not None:
            comp.setCD(float(kwargs["cd"]))

    if kwargs.get("material") is not None:
        mat = lookup_material(kwargs["material"])
        if mat:
            comp.setMaterial(mat)

    if kwargs.get("axial_offset") is not None:
        comp.setAxialOffset(float(kwargs["axial_offset"]))
    if kwargs.get("axial_offset_method") is not None:
        JComponent = jpype.JClass("net.sf.openrocket.rocketcomponent.RocketComponent")
        method = JComponent.Position.valueOf(kwargs["axial_offset_method"].upper())
        comp.setAxialOffsetMethod(method)


def create_component(
    ork_path: Path, parent_name: str, type_name: str, name: str, **kwargs
) -> dict:
    """Create a new component and add it to a parent."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper
        import jpype

        JFile = jpype.JClass("java.io.File")
        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        try:
            doc = helper.load_doc(path_str)
        except Exception:
            doc = helper.load_doc(JFile(path_str))
        rocket = doc.getRocket()

        parent = None

        def _find(c):
            nonlocal parent
            if str(c.getName()) == parent_name:
                parent = c
                return True
            for i in range(c.getChildCount()):
                if _find(c.getChildAt(i)):
                    return True
            return False

        _find(rocket)

        if parent is None:
            raise ValueError(f"Parent '{parent_name}' not found.")

        java_class_name = COMPONENT_TYPES.get(type_name)
        if not java_class_name:
            raise ValueError(f"Unsupported component type: {type_name}")

        JClass = jpype.JClass(f"net.sf.openrocket.rocketcomponent.{java_class_name}")
        comp = JClass()
        comp.setName(str(name))

        _apply_properties(comp, **kwargs)
        parent.addChild(comp)
        _save_doc(doc, ork_path)

        return _extract_properties(comp)


def delete_component(ork_path: Path, component_name: str) -> str:
    """Delete a component by name."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper
        import jpype

        JFile = jpype.JClass("java.io.File")
        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        try:
            doc = helper.load_doc(path_str)
        except Exception:
            doc = helper.load_doc(JFile(path_str))
        rocket = doc.getRocket()

        comp = None
        parent = None

        def _find(c, p):
            nonlocal comp, parent
            if str(c.getName()) == component_name:
                comp = c
                parent = p
                return True
            for i in range(c.getChildCount()):
                if _find(c.getChildAt(i), c):
                    return True
            return False

        _find(rocket, None)

        if comp is None:
            raise ValueError(f"Component '{component_name}' not found.")

        if parent is None:
            raise ValueError(
                f"Cannot delete '{component_name}': it is the rocket root."
            )

        name = str(comp.getName())
        parent.removeChild(comp)
        _save_doc(doc, ork_path)

    return name


def lookup_material(name: str, material_type: str | None = None):
    """Look up a Material object by name."""
    import jpype

    Database = jpype.JClass("net.sf.openrocket.database.ComponentPresetDatabase")
    db = Database.getDefaultDatabase().getMaterialDatabase()

    for mat in db:
        if str(mat.getName()).lower() == name.lower():
            return mat

    return None


def list_materials(material_type: str | None = None) -> list[dict]:
    """List available materials from the OpenRocket database."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    jar_path = get_openrocket_path()

    with _or_context(jar_path):
        import jpype

        Database = jpype.JClass("net.sf.openrocket.database.ComponentPresetDatabase")
        db = Database.getDefaultDatabase().getMaterialDatabase()

        results = [
            {
                "name": str(mat.getName()),
                "density": round(float(mat.getDensity()), 6),
                "type": material_type,
            }
            for mat in db
        ]

        return sorted(results, key=lambda x: x["name"])
