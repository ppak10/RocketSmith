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


def _save_doc(doc, output_path: Path) -> None:
    import jpype

    JFile = jpype.JClass("java.io.File")
    JGeneralRocketSaver = jpype.JClass("net.sf.openrocket.file.GeneralRocketSaver")
    JStorageOptions = jpype.JClass("net.sf.openrocket.document.StorageOptions")

    opts = JStorageOptions()
    saver = JGeneralRocketSaver()
    # OR 23.09: save(File, Document, Options)
    saver.save(JFile(os.path.abspath(str(output_path))), doc, opts)


def new_ork(name: str, output_path: Path, jar_path: Path | None = None) -> Path:
    """Create a new empty .ork file with a single stage."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()

    with _or_context(jar_path) as _:
        import jpype

        # Create basic document structure
        Rocket = jpype.JClass("net.sf.openrocket.rocketcomponent.Rocket")
        AxialStage = jpype.JClass("net.sf.openrocket.rocketcomponent.AxialStage")
        OpenRocketDocument = jpype.JClass(
            "net.sf.openrocket.document.OpenRocketDocument"
        )

        rocket = Rocket()
        rocket.setName(name)
        stage = AxialStage()
        stage.setName("Sustainer")
        rocket.addChild(stage)

        # Use reflection for non-public constructor in OR 23.09
        cons = OpenRocketDocument.class_.getDeclaredConstructors()
        doc = None
        for c in cons:
            if len(c.getParameterTypes()) == 1 and "Rocket" in str(
                c.getParameterTypes()[0]
            ):
                c.setAccessible(True)
                doc = c.newInstance(rocket)
                break
        if doc is None:
            raise RuntimeError("Failed to instantiate OpenRocketDocument.")

        _save_doc(doc, output_path)

    return output_path


def inspect_ork(ork_path: Path, jar_path: Path | None = None) -> dict:
    """Read component tree, CG, and CP from .ork file.

    Returns a dict with:
      - 'components': list of dicts
      - 'cg_x': center of gravity (m from tip)
      - 'cp_x': center of pressure (m from tip)
      - 'max_diameter_m': maximum outer diameter
    """
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper
        import jpype

        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        doc = helper.load_doc(path_str)
        rocket = doc.getRocket()
        config = doc.getSelectedConfiguration()

        # 1. Walk components
        results = []

        def _walk(comp, depth):
            props = _extract_properties(comp)
            props["depth"] = depth
            results.append(props)
            for i in range(comp.getChildCount()):
                _walk(comp.getChild(i), depth + 1)

        _walk(rocket, 0)

        # 2. Calculate CG (manual walk to be robust across OR versions)
        total_mass = 0.0
        total_moment = 0.0
        max_d = 0.0
        for c in orhelper.JIterator(rocket):
            m = float(c.getMass())
            if m > 0:
                total_mass += m
                # Absolute X
                abs_x = 0.0
                curr = c
                while curr is not None:
                    try:
                        p = curr.getPosition()
                        try:
                            abs_x += float(p.x)
                        except:
                            abs_x += float(p)
                    except:
                        pass
                    curr = curr.getParent()

                total_moment += m * (abs_x + float(c.getCG().x))

            try:
                # getOuterRadius returns radius
                d = float(c.getOuterRadius()) * 2
                if d > max_d:
                    max_d = d
            except:
                pass

        cg_x = total_moment / total_mass if total_mass > 0 else 0.0

        # 3. Calculate CP (using Barrowman)
        cp_x = 0.0
        try:
            BC = jpype.JClass("net.sf.openrocket.aerodynamics.BarrowmanCalculator")
            FC = jpype.JClass("net.sf.openrocket.aerodynamics.FlightConditions")
            WS = jpype.JClass("net.sf.openrocket.logging.WarningSet")
            calc = BC()
            conds = FC(config)
            warnings = WS()
            cp_x = float(calc.getCP(config, conds, warnings).x)
        except Exception:
            pass

        return {
            "components": results,
            "cg_x": round(cg_x, 4),
            "cp_x": round(cp_x, 4),
            "max_diameter_m": round(max_d, 4),
        }


def read_components(ork_path: Path) -> list[dict]:
    """Read component tree from .ork file."""
    return inspect_ork(ork_path)


def read_component(
    ork_path: Path, component_name: str, jar_path: Path | None = None
) -> dict:
    """Read properties of a single component by name."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper

        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        doc = helper.load_doc(path_str)
        rocket = doc.getRocket()

        comp = None

        def _find(c):
            nonlocal comp
            if str(c.getName()) == component_name:
                comp = c
                return True
            for i in range(c.getChildCount()):
                if _find(c.getChild(i)):
                    return True
            return False

        _find(rocket)
        if comp is None:
            raise ValueError(f"Component '{component_name}' not found.")

        return _extract_properties(comp)


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
        except:
            pass
        try:
            props["fore_diameter_m"] = round(float(comp.getForeRadius()) * 2, 4)
        except:
            pass
        try:
            props["aft_diameter_m"] = round(float(comp.getAftRadius()) * 2, 4)
        except:
            pass
        try:
            props["thickness_m"] = round(float(comp.getThickness()), 4)
        except:
            pass
        try:
            props["shape"] = str(comp.getShapeType().toString()).lower()
        except:
            pass

    elif type_name in ("BodyTube", "InnerTube", "TubeCoupler"):
        try:
            props["outer_diameter_m"] = round(float(comp.getOuterRadius()) * 2, 4)
        except:
            pass
        try:
            props["inner_diameter_m"] = round(float(comp.getInnerRadius()) * 2, 4)
        except:
            pass
        try:
            props["length_m"] = round(float(comp.getLength()), 4)
        except:
            pass
        try:
            props["thickness_m"] = round(float(comp.getThickness()), 4)
        except:
            pass
        try:
            props["motor_mount"] = bool(comp.isMotorMount())
        except:
            pass

    elif type_name == "TrapezoidFinSet":
        try:
            props["fin_count"] = int(comp.getFinCount())
        except:
            pass
        try:
            props["root_chord_m"] = round(float(comp.getRootChord()), 4)
        except:
            pass
        try:
            props["tip_chord_m"] = round(float(comp.getTipChord()), 4)
        except:
            pass
        try:
            props["span_m"] = round(float(comp.getSpan()), 4)
        except:
            pass
        try:
            props["sweep_m"] = round(float(comp.getSweep()), 4)
        except:
            pass
        try:
            props["thickness_m"] = round(float(comp.getThickness()), 4)
        except:
            pass

    elif type_name == "Parachute":
        try:
            props["diameter_m"] = round(float(comp.getDiameter()), 4)
        except:
            pass
        try:
            props["cd"] = round(float(comp.getCD()), 2)
        except:
            pass

    try:
        preset = comp.getComponentPreset()
        if preset is not None:
            props["preset_manufacturer"] = str(preset.getManufacturer())
            props["preset_part_no"] = str(preset.getPartNo())
    except:
        pass

    try:
        mat = comp.getMaterial()
        if mat is not None:
            props["material"] = str(mat.getName())
            props["material_density_kg_m3"] = round(float(mat.getDensity()), 4)
    except:
        pass

    try:
        props["axial_offset_m"] = round(float(comp.getAxialOffset()), 4)
        props["axial_offset_method"] = str(comp.getAxialOffsetMethod())
    except:
        pass

    try:
        props["position_x_m"] = round(float(comp.getPositionX()), 4)
    except:
        try:
            x = 0.0
            curr = comp
            while curr is not None:
                try:
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


def update_component(
    ork_path: Path, component_name: str, jar_path: Path | None = None, **kwargs
) -> dict | None:
    """Update properties of an existing component by name."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper

        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        doc = helper.load_doc(path_str)
        rocket = doc.getRocket()

        comp = None

        def _find(c):
            nonlocal comp
            if str(c.getName()) == component_name:
                comp = c
                return True
            for i in range(c.getChildCount()):
                if _find(c.getChild(i)):
                    return True
            return False

        _find(rocket)
        if comp is None:
            raise ValueError(f"Component '{component_name}' not found.")

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

        # Handle both 'diameter' and 'aft_diameter' for NoseCone/Transition
        aft_d = kwargs.get("aft_diameter") or kwargs.get("diameter")
        if aft_d is not None:
            comp.setAftRadius(float(aft_d) / 2)

        if kwargs.get("fore_diameter") is not None:
            comp.setForeRadius(float(kwargs["fore_diameter"]) / 2)

        if java_type_name == "NoseCone" and kwargs.get("shape") is not None:
            JNoseCone = jpype.JClass("net.sf.openrocket.rocketcomponent.NoseCone")
            shape = JNoseCone.Shape.valueOf(kwargs["shape"].upper())
            comp.setShapeType(shape)
        if java_type_name == "Transition" and kwargs.get("shape") is not None:
            JTransition = jpype.JClass("net.sf.openrocket.rocketcomponent.Transition")
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
        count = kwargs.get("fin_count") or kwargs.get("count")
        if count is not None:
            comp.setFinCount(int(count))
        if kwargs.get("root_chord") is not None:
            comp.setRootChord(float(kwargs["root_chord"]))
        if kwargs.get("tip_chord") is not None:
            comp.setTipChord(float(kwargs["tip_chord"]))
        # In OR 23.09, TrapezoidFinSet uses setHeight instead of setSpan
        span = kwargs.get("span")
        if span is not None:
            if hasattr(comp, "setHeight"):
                comp.setHeight(float(span))
            else:
                comp.setSpan(float(span))
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

    if (
        kwargs.get("axial_offset") is not None
        or kwargs.get("axial_offset_m") is not None
    ):
        offset = (
            kwargs.get("axial_offset_m")
            if kwargs.get("axial_offset_m") is not None
            else kwargs.get("axial_offset")
        )
        comp.setAxialOffset(float(offset))
    if kwargs.get("axial_offset_method") is not None:
        JComponent = jpype.JClass("net.sf.openrocket.rocketcomponent.RocketComponent")
        method = JComponent.Position.valueOf(kwargs["axial_offset_method"].upper())
        comp.setAxialOffsetMethod(method)


def create_component(
    ork_path: Path,
    component_type: str,
    jar_path: Path | None = None,
    parent_name: str | None = None,
    **kwargs,
) -> dict:
    """Create a new component and add it to a parent."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()

    java_class_name = COMPONENT_TYPES.get(component_type)
    if not java_class_name:
        raise ValueError(f"Unknown component type: {component_type}")

    with _or_context(jar_path) as instance:
        import orhelper
        import jpype

        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        doc = helper.load_doc(path_str)
        rocket = doc.getRocket()

        # Find suitable parent if not specified
        parent_comp = None
        target = parent_name or kwargs.get("parent")

        def _find_suitable(c):
            nonlocal parent_comp
            if target:
                if str(c.getName()) == target:
                    parent_comp = c
                    return True
            else:
                # Default selection based on component compatibility
                cname = str(c.getClass().getSimpleName())
                if component_type in ("nose-cone", "body-tube", "transition"):
                    if "Stage" in cname:
                        parent_comp = c
                        return True
                elif component_type in (
                    "inner-tube",
                    "fin-set",
                    "parachute",
                    "tube-coupler",
                ):
                    # These MUST be in a BodyTube or similar
                    if cname in ("BodyTube", "Transition", "InnerTube"):
                        parent_comp = c
                        return True
                elif component_type == "mass":
                    if cname in ("BodyTube", "Transition", "InnerTube", "NoseCone"):
                        parent_comp = c
                        return True

            for i in range(c.getChildCount()):
                if _find_suitable(c.getChild(i)):
                    return True
            return False

        _find_suitable(rocket)

        if parent_comp is None:
            if target:
                raise ValueError(f"Parent '{target}' not found.")
            else:
                msg = f"No suitable parent found for {component_type}."
                if component_type in (
                    "fin-set",
                    "parachute",
                    "inner-tube",
                    "tube-coupler",
                ):
                    msg += " (expected BodyTube, Transition, or InnerTube)"
                raise ValueError(msg)

        JClass = jpype.JClass(f"net.sf.openrocket.rocketcomponent.{java_class_name}")
        comp = JClass()
        _apply_properties(comp, **kwargs)
        parent_comp.addChild(comp)
        _save_doc(doc, ork_path)
        return _extract_properties(comp)


def delete_component(
    ork_path: Path, component_name: str, jar_path: Path | None = None
) -> str:
    """Delete a component by name."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()

    with _or_context(jar_path) as instance:
        import orhelper

        helper = orhelper.Helper(instance)
        path_str = os.path.abspath(str(ork_path))
        doc = helper.load_doc(path_str)
        rocket = doc.getRocket()

        comp = None
        p_comp = None

        def _find(c, p):
            nonlocal comp, p_comp
            if str(c.getName()) == component_name:
                comp = c
                p_comp = p
                return True
            for i in range(c.getChildCount()):
                if _find(c.getChild(i), c):
                    return True
            return False

        _find(rocket, None)
        if comp is None:
            raise ValueError(f"Component '{component_name}' not found.")
        if p_comp is None:
            raise ValueError(
                f"Cannot delete '{component_name}': it is the rocket root."
            )

        name = str(comp.getName())
        p_comp.removeChild(comp)
        _save_doc(doc, ork_path)
        return name


def lookup_material(name: str):
    """Look up a Material object by name."""
    import jpype

    Database = jpype.JClass("net.sf.openrocket.database.ComponentPresetDatabase")
    db = Database.getDefaultDatabase().getMaterialDatabase()
    for mat in db:
        if str(mat.getName()).lower() == name.lower():
            return mat
    return None


def list_materials(jar_path: Path | None = None) -> list[dict]:
    """List available materials from the OpenRocket database."""
    from rocketsmith.openrocket.utils import get_openrocket_path

    if jar_path is None:
        jar_path = get_openrocket_path()
    with _or_context(jar_path):
        import jpype

        Database = jpype.JClass("net.sf.openrocket.database.ComponentPresetDatabase")
        db = Database.getDefaultDatabase().getMaterialDatabase()
        results = [
            {"name": str(mat.getName()), "density": round(float(mat.getDensity()), 6)}
            for mat in db
        ]
        return sorted(results, key=lambda x: x["name"])
