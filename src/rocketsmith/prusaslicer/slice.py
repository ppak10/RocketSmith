import re
import subprocess

from pathlib import Path

from rocketsmith.prusaslicer.models import MATERIAL_DENSITY, Material, PrusaSlicerResult
from rocketsmith.prusaslicer.utils import get_prusaslicer_path


def slice(
    model_path: Path,
    output_path: Path | None = None,
    config_path: Path | None = None,
    prusaslicer_path: Path | None = None,
    material: Material = Material.PLA,
) -> PrusaSlicerResult:
    """
    Slice a model file using PrusaSlicer and return the result.

    Args:
        model_path: Path to the input model file (.stl, .step, .3mf, .obj).
        output_path: Path for the output .gcode file. Defaults to the model
                     path with a .gcode extension in the same directory.
        config_path: Optional path to a PrusaSlicer .ini config file to load.
        prusaslicer_path: Optional path to the PrusaSlicer executable.
        material: Filament material used to calculate weight from volume when
                  no filament profile is configured. Defaults to PLA.

    Returns:
        PrusaSlicerResult with the gcode path and parsed print metadata.
    """
    model_path = Path(model_path)

    if output_path is None:
        output_path = model_path.with_suffix(".gcode")

    exe = get_prusaslicer_path(prusaslicer_path)

    cmd = [str(exe), "--export-gcode", "--output", str(output_path)]
    if config_path is not None:
        cmd += ["--load", str(config_path)]
    cmd.append(str(model_path))

    subprocess.run(cmd, check=True, capture_output=True, text=True)

    metadata = _parse_gcode_metadata(output_path)

    # Calculate grams from volume when PrusaSlicer reports 0 (no filament profile)
    if metadata.get("filament_used_g") is None and metadata.get("filament_used_cm3") is not None:
        metadata["filament_used_g"] = metadata["filament_used_cm3"] * MATERIAL_DENSITY[material]

    return PrusaSlicerResult(
        gcode_path=output_path,
        material=material,
        **metadata,
    )


def _parse_gcode_metadata(gcode_path: Path) -> dict:
    """Parse print metadata from PrusaSlicer G-code comments."""
    metadata: dict = {}
    layer_count = 0

    with open(gcode_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()

            if line == ";LAYER_CHANGE":
                layer_count += 1
                continue

            if not line.startswith("; "):
                continue

            if m := re.match(r"; filament used \[mm\] = ([\d.]+)", line):
                metadata["filament_used_mm"] = float(m.group(1))

            elif m := re.match(r"; filament used \[cm3\] = ([\d.]+)", line):
                metadata["filament_used_cm3"] = float(m.group(1))

            elif m := re.match(r"; total filament used \[g\] = ([\d.]+)", line):
                value = float(m.group(1))
                if value > 0:
                    metadata["filament_used_g"] = value

            elif m := re.match(r"; estimated printing time \(normal mode\) = (.+)", line):
                metadata["print_time_seconds"] = _parse_time(m.group(1).strip())

    if layer_count:
        metadata["total_layers"] = layer_count

    return metadata


def _parse_time(time_str: str) -> float:
    """Convert a PrusaSlicer time string like '7h 3m 25s' to seconds."""
    seconds = 0.0
    for value, unit in re.findall(r"(\d+)\s*([hms])", time_str):
        match unit:
            case "h":
                seconds += int(value) * 3600
            case "m":
                seconds += int(value) * 60
            case "s":
                seconds += int(value)
    return seconds
