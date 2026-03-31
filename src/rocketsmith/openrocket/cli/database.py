import typer
import questionary

from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from typing_extensions import Annotated

from rocketsmith.openrocket.utils import get_openrocket_path


# ── Category / type definitions ───────────────────────────────────────────────

_CATEGORIES = [
    ("Motors", "motors"),
    ("Recovery  (Parachutes · Streamers · Shock Cords)", "recovery"),
    ("Airframe  (Body Tubes · Nose Cones · Transitions · Tube Couplers)", "airframe"),
    ("Hardware  (Centering Rings · Bulk Heads · Engine Blocks · Launch Lugs · Rail Buttons)", "hardware"),
    ("Materials  (Bulk · Surface · Line)", "materials"),
]

_RECOVERY_TYPES = [
    ("Parachutes", "parachute"),
    ("Streamers", "streamer"),
    ("Shock Cords (line materials)", "shock-cords"),
]

_AIRFRAME_TYPES = [
    ("Body Tubes", "body-tube"),
    ("Nose Cones", "nose-cone"),
    ("Transitions", "transition"),
    ("Tube Couplers", "tube-coupler"),
]

_HARDWARE_TYPES = [
    ("Centering Rings", "centering-ring"),
    ("Bulk Heads", "bulk-head"),
    ("Engine Blocks", "engine-block"),
    ("Launch Lugs", "launch-lug"),
    ("Rail Buttons", "rail-button"),
]

_MATERIAL_TYPES = [
    ("Bulk  (tubes, fins, nose cones — density in kg/m³)", "bulk"),
    ("Surface  (fin sheets, streamers — area density in kg/m²)", "surface"),
    ("Line  (shock cords — linear density in kg/m)", "line"),
]

_MOTOR_DIAMETERS = [
    "Any", "13", "18", "24", "29", "38", "54", "75", "98",
]

_IMPULSE_CLASSES = [
    "Any", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
]


# ── Display helpers ───────────────────────────────────────────────────────────

def _motor_label(m: dict) -> str:
    return (
        f"{m['manufacturer']}  {m['common_name']}  "
        f"({m['type']}, {m['diameter_mm']}mm, {m['total_impulse_ns']} Ns)"
    )


def _preset_label(p: dict) -> str:
    dims = []
    for key in ("outer_diameter_m", "diameter_m", "length_m"):
        if key in p:
            dims.append(f"{key.replace('_m','').replace('_',' ')}={p[key]:.4f}m")
    dim_str = "  ".join(dims)
    return f"{p['manufacturer']}  {p['part_no']}  {dim_str}"


def _material_label(m: dict) -> str:
    return f"{m['name']}  ({m['density']} kg)"


def _show_motor(motor: dict) -> None:
    table = Table(title=f"{motor['manufacturer']} {motor['common_name']}", show_header=False)
    table.add_column("Property", style="dim")
    table.add_column("Value", style="cyan")
    for k, v in motor.items():
        table.add_row(k.replace("_", " "), str(v))
    Console().print(table)


def _show_preset(preset: dict) -> None:
    table = Table(
        title=f"{preset['manufacturer']} — {preset['part_no']}",
        show_header=False,
    )
    table.add_column("Property", style="dim")
    table.add_column("Value", style="cyan")
    for k, v in preset.items():
        if k == "type":
            continue
        table.add_row(k.replace("_", " "), str(v))
    Console().print(table)


def _show_material(material: dict) -> None:
    unit = {"bulk": "kg/m³", "surface": "kg/m²", "line": "kg/m"}.get(material["type"], "")
    Console().print(
        Panel(
            f"[cyan]{material['name']}[/cyan]\n"
            f"[dim]Density:[/dim] {material['density']} {unit}",
            title="Material",
        )
    )


def _ask_manufacturer_filter() -> str | None:
    value = questionary.text(
        "Filter by manufacturer (leave blank for all):",
        instruction="(type to filter, Enter to skip)",
    ).ask()
    return value.strip() or None


# ── Flow handlers ─────────────────────────────────────────────────────────────

def _flow_motors(jar) -> None:
    from rocketsmith.openrocket.database import list_motors

    # Impulse class
    cls_choice = questionary.select(
        "Impulse class:",
        choices=_IMPULSE_CLASSES,
    ).ask()
    impulse_class = None if cls_choice == "Any" else cls_choice

    # Diameter
    dia_choice = questionary.select(
        "Motor diameter (mm):",
        choices=_MOTOR_DIAMETERS,
    ).ask()
    diameter_mm = None if dia_choice == "Any" else float(dia_choice)

    # Manufacturer
    manufacturer = _ask_manufacturer_filter()

    rprint("[dim]Loading motors…[/dim]")
    motors = list_motors(
        jar,
        manufacturer=manufacturer,
        impulse_class=impulse_class,
        diameter_mm=diameter_mm,
    )

    if not motors:
        rprint("[yellow]No motors found matching those filters.[/yellow]")
        return

    choices = [questionary.Choice(title=_motor_label(m), value=m) for m in motors]
    choices.append(questionary.Choice(title="← Cancel", value=None))

    selected = questionary.select(
        f"Select a motor ({len(motors)} found):",
        choices=choices,
    ).ask()

    if selected:
        _show_motor(selected)


def _flow_presets(jar, preset_type: str, label: str) -> None:
    from rocketsmith.openrocket.database import list_presets

    manufacturer = _ask_manufacturer_filter()

    rprint(f"[dim]Loading {label}…[/dim]")
    presets = list_presets(jar, preset_type, manufacturer=manufacturer)

    if not presets:
        rprint(f"[yellow]No {label} found.[/yellow]")
        return

    choices = [questionary.Choice(title=_preset_label(p), value=p) for p in presets]
    choices.append(questionary.Choice(title="← Cancel", value=None))

    selected = questionary.select(
        f"Select a {label[:-1] if label.endswith('s') else label} ({len(presets)} found):",
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()

    if selected:
        _show_preset(selected)


def _flow_shock_cords(jar) -> None:
    from rocketsmith.openrocket.database import list_materials

    rprint("[dim]Loading shock cord materials…[/dim]")
    materials = list_materials(jar, "line")

    choices = [questionary.Choice(title=_material_label(m), value=m) for m in materials]
    choices.append(questionary.Choice(title="← Cancel", value=None))

    selected = questionary.select(
        f"Select a shock cord material ({len(materials)} found):",
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()

    if selected:
        _show_material(selected)


def _flow_recovery(jar) -> None:
    type_choice = questionary.select(
        "Recovery type:",
        choices=[questionary.Choice(title=label, value=val) for label, val in _RECOVERY_TYPES],
    ).ask()

    if type_choice == "shock-cords":
        _flow_shock_cords(jar)
    elif type_choice:
        _flow_presets(jar, type_choice, dict(_RECOVERY_TYPES)[
            next(label for label, val in _RECOVERY_TYPES if val == type_choice)
        ])


def _flow_airframe(jar) -> None:
    type_choice = questionary.select(
        "Airframe type:",
        choices=[questionary.Choice(title=label, value=val) for label, val in _AIRFRAME_TYPES],
    ).ask()
    if type_choice:
        label = next(label for label, val in _AIRFRAME_TYPES if val == type_choice)
        _flow_presets(jar, type_choice, label)


def _flow_hardware(jar) -> None:
    type_choice = questionary.select(
        "Hardware type:",
        choices=[questionary.Choice(title=label, value=val) for label, val in _HARDWARE_TYPES],
    ).ask()
    if type_choice:
        label = next(label for label, val in _HARDWARE_TYPES if val == type_choice)
        _flow_presets(jar, type_choice, label)


def _flow_materials(jar) -> None:
    from rocketsmith.openrocket.database import list_materials

    type_choice = questionary.select(
        "Material type:",
        choices=[questionary.Choice(title=label, value=val) for label, val in _MATERIAL_TYPES],
    ).ask()
    if not type_choice:
        return

    rprint("[dim]Loading materials…[/dim]")
    materials = list_materials(jar, type_choice)

    choices = [questionary.Choice(title=_material_label(m), value=m) for m in materials]
    choices.append(questionary.Choice(title="← Cancel", value=None))

    selected = questionary.select(
        f"Select a material ({len(materials)} found):",
        choices=choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()

    if selected:
        _show_material(selected)


# ── Command ───────────────────────────────────────────────────────────────────

def register_openrocket_database(app: typer.Typer):
    @app.command(name="database")
    def openrocket_database(
        openrocket_path: Annotated[
            str | None,
            typer.Option("--openrocket-path", help="Path to OpenRocket JAR or its parent directory."),
        ] = None,
    ) -> None:
        """Browse the OpenRocket component and motor database interactively."""
        try:
            jar = get_openrocket_path(openrocket_path)
        except FileNotFoundError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

        category = questionary.select(
            "What are you looking for?",
            choices=[questionary.Choice(title=label, value=val) for label, val in _CATEGORIES],
        ).ask()

        if category is None:
            return

        if category == "motors":
            _flow_motors(jar)
        elif category == "recovery":
            _flow_recovery(jar)
        elif category == "airframe":
            _flow_airframe(jar)
        elif category == "hardware":
            _flow_hardware(jar)
        elif category == "materials":
            _flow_materials(jar)

    return openrocket_database
