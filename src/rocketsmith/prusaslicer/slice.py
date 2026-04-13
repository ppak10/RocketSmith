import re
import subprocess

from pathlib import Path

from rocketsmith.prusaslicer.models import MATERIAL_DENSITY, Material, PrusaSlicerResult
from rocketsmith.prusaslicer.utils import get_prusaslicer_path


class PrusaSlicerSliceError(Exception):
    """Raised when PrusaSlicer fails to produce a usable gcode file.

    Carries the captured stdout, stderr, return code, and command line so
    the MCP wrapper can pass them through to the agent verbatim. This is
    the diagnostic info that ``CalledProcessError.__str__`` discards.
    """

    def __init__(
        self,
        summary: str,
        returncode: int,
        stdout: str,
        stderr: str,
        command: list[str],
        model_path: str,
        output_path: str,
        detail: str,
    ):
        self.summary = summary
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.command = command
        self.model_path = model_path
        self.output_path = output_path
        self.detail = detail
        super().__init__(f"{summary}\n\n{detail}")


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
    model_path = Path(model_path).expanduser()
    if not model_path.is_absolute():
        model_path = (Path.cwd() / model_path).resolve()

    if output_path is None:
        output_path = model_path.with_suffix(".gcode")
    else:
        output_path = Path(output_path).expanduser()
        if not output_path.is_absolute():
            output_path = (Path.cwd() / output_path).resolve()

    exe = get_prusaslicer_path(prusaslicer_path)

    cmd = [str(exe), "--export-gcode", "--output", str(output_path)]
    if config_path is not None:
        cmd += ["--load", str(config_path)]
    cmd.append(str(model_path))

    # Note: ``check=False`` deliberately. PrusaSlicer's stderr is the most
    # important diagnostic when slicing fails, and ``CalledProcessError``'s
    # default ``__str__`` only contains the command line and return code —
    # not the captured stderr. Inspecting the return code manually lets us
    # surface PrusaSlicer's actual error message (e.g. "no extrusions in
    # the first layer", "Object out of print volume") in the raised
    # exception, so the agent can react without dropping to a shell.
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)

    if proc.returncode != 0 or not output_path.exists():
        # Build a single informative error message that the MCP wrapper
        # will pass through to the agent. Both failure modes (non-zero
        # exit, and zero exit with no output file) take this branch.
        detail_lines = []
        if proc.stderr and proc.stderr.strip():
            detail_lines.append(f"stderr:\n{proc.stderr.strip()}")
        if proc.stdout and proc.stdout.strip():
            detail_lines.append(f"stdout:\n{proc.stdout.strip()}")
        detail = "\n\n".join(detail_lines) if detail_lines else "(no output)"

        if proc.returncode != 0:
            summary = (
                f"PrusaSlicer exited with code {proc.returncode} while "
                f"slicing {model_path.name}. This usually means the "
                "model orientation is wrong (e.g. tip-down nose cone "
                "with no extrusions in the first layer), the mesh is "
                "invalid, the model is outside the print volume, or "
                "the supplied config_path is missing required profiles."
            )
        else:
            summary = (
                f"PrusaSlicer exited 0 but produced no G-code at "
                f"{output_path}. This usually means the model is outside "
                "the print volume, the mesh is invalid, or no print "
                "profile was supplied via config_path."
            )

        raise PrusaSlicerSliceError(
            summary=summary,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            command=list(cmd),
            model_path=str(model_path),
            output_path=str(output_path),
            detail=detail,
        )

    metadata = _parse_gcode_metadata(output_path)

    # Calculate grams from volume when PrusaSlicer reports 0 (no filament profile)
    if (
        metadata.get("filament_used_g") is None
        and metadata.get("filament_used_cm3") is not None
    ):
        metadata["filament_used_g"] = (
            metadata["filament_used_cm3"] * MATERIAL_DENSITY[material]
        )

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

            elif m := re.match(
                r"; estimated printing time \(normal mode\) = (.+)", line
            ):
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
