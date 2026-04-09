import configparser
import sys

from pathlib import Path


# Key fields surfaced per config type in database results.
_TYPE_FIELDS: dict[str, set[str]] = {
    "printer": {
        "bed_shape",
        "gcode_flavor",
        "max_print_height",
        "nozzle_diameter",
        "printer_model",
        "printer_technology",
        "retract_length",
        "retract_speed",
        "use_relative_e_distances",
    },
    "filament": {
        "bed_temperature",
        "compatible_printers_condition",
        "filament_density",
        "filament_type",
        "filament_vendor",
        "first_layer_bed_temperature",
        "first_layer_temperature",
        "temperature",
    },
    "print": {
        "bottom_solid_layers",
        "fill_angle",
        "infill_density",
        "infill_pattern",
        "layer_height",
        "perimeters",
        "support_material",
        "top_solid_layers",
    },
}


def get_profiles_path(prusaslicer_path: Path | None = None) -> Path:
    """
    Locate the PrusaSlicer bundled vendor profiles directory.

    Args:
        prusaslicer_path: Optional explicit path to the PrusaSlicer executable.

    Returns:
        Path to the profiles directory.

    Raises:
        FileNotFoundError: If the profiles directory cannot be located.
    """
    from rocketsmith.prusaslicer.utils import get_prusaslicer_path

    exe = get_prusaslicer_path(prusaslicer_path)
    platform = sys.platform

    candidates: list[Path] = []

    if platform == "darwin":
        # exe: *.app/Contents/MacOS/PrusaSlicer
        # profiles: *.app/Contents/Resources/profiles/
        candidates.append(exe.parent.parent / "Resources" / "profiles")
    elif platform == "win32":
        # exe: <install>/prusa-slicer-console.exe
        # profiles: <install>/resources/profiles/
        candidates.append(exe.parent / "resources" / "profiles")
    else:
        # Linux: exe may be an AppImage or installed binary
        candidates += [
            exe.parent / "resources" / "profiles",
            Path("/usr/share/PrusaSlicer/profiles"),
            Path("/usr/share/prusa-slicer/profiles"),
            Path("/usr/local/share/PrusaSlicer/profiles"),
        ]

    for path in candidates:
        if path.is_dir():
            return path

    raise FileNotFoundError(
        f"PrusaSlicer profiles directory not found (checked: {candidates}). "
        "Ensure PrusaSlicer is installed."
    )


def _parse_vendor_ini(
    path: Path,
) -> tuple[str, dict[str, dict[str, dict[str, str]]]]:
    """
    Parse a PrusaSlicer vendor .ini bundle.

    Returns:
        (vendor_name, sections_by_type) where sections_by_type maps
        config type → preset name → settings dict.
    """
    parser = configparser.RawConfigParser(
        strict=False,
        delimiters=("=",),
    )
    try:
        parser.read(str(path), encoding="utf-8")
    except configparser.Error:
        return path.stem, {}

    vendor_name = path.stem
    sections_by_type: dict[str, dict[str, dict[str, str]]] = {
        "printer": {},
        "filament": {},
        "print": {},
    }

    for section in parser.sections():
        if ":" not in section:
            if section == "vendor":
                vendor_name = parser.get(section, "name", fallback=path.stem)
            continue

        section_type, _, section_name = section.partition(":")
        section_type = section_type.strip().lower()
        section_name = section_name.strip()

        if section_type not in sections_by_type:
            continue

        try:
            settings = dict(parser.items(section))
        except configparser.Error:
            continue

        sections_by_type[section_type][section_name] = settings

    return vendor_name, sections_by_type


def _resolve_preset(
    name: str,
    sections: dict[str, dict[str, str]],
    _visited: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """
    Recursively resolve a preset's settings by following its inherits chain.

    Parents are merged left-to-right; the concrete preset's own keys win last.
    Cycles are broken via the visited set.
    """
    if name in _visited or name not in sections:
        return {}

    _visited = _visited | {name}
    own = sections[name].copy()
    inherits_str = own.pop("inherits", None)

    if not inherits_str:
        return own

    merged: dict[str, str] = {}
    for parent in (p.strip() for p in inherits_str.split(";") if p.strip()):
        merged.update(_resolve_preset(parent, sections, _visited))

    merged.update(own)
    return merged


def list_database(
    profiles_path: Path,
    config_type: str,
    *,
    vendor: str | None = None,
    name: str | None = None,
) -> list[dict]:
    """
    Search the PrusaSlicer vendor preset database.

    Args:
        profiles_path: Path to the PrusaSlicer profiles directory.
        config_type: One of 'printer', 'filament', 'print'.
        vendor: Optional vendor name substring filter (case-insensitive).
        name: Optional preset name substring filter (case-insensitive).

    Returns:
        List of preset dicts with vendor, name, and resolved key fields.
    """
    if config_type not in _TYPE_FIELDS:
        raise ValueError(
            f"Unknown config_type '{config_type}'. Valid: {', '.join(_TYPE_FIELDS)}"
        )

    fields = _TYPE_FIELDS[config_type]
    results: list[dict] = []

    for ini_file in sorted(profiles_path.glob("*.ini")):
        try:
            vendor_name, sections_by_type = _parse_vendor_ini(ini_file)
        except Exception:
            continue

        if vendor and vendor.lower() not in vendor_name.lower():
            continue

        sections = sections_by_type.get(config_type, {})

        for preset_name in sections:
            # Skip abstract/template presets (names wrapped in *)
            if preset_name.startswith("*"):
                continue

            if name and name.lower() not in preset_name.lower():
                continue

            resolved = _resolve_preset(preset_name, sections)

            entry: dict = {"vendor": vendor_name, "name": preset_name}
            for field in sorted(fields):
                if field in resolved:
                    entry[field] = resolved[field]

            results.append(entry)

    return results
