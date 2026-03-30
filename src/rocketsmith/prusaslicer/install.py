import shutil
import subprocess
import sys

from rich import print as rprint

from rocketsmith.prusaslicer.utils import get_prusaslicer_path


def install() -> None:
    """Install PrusaSlicer using the appropriate method for the current platform."""
    try:
        exe = get_prusaslicer_path()
        rprint(f"✅ PrusaSlicer is already installed at: [cyan]{exe}[/cyan]")
        return
    except FileNotFoundError:
        pass

    match sys.platform:
        case "darwin":
            _install_macos()
        case "linux":
            _install_linux()
        case "win32":
            _install_windows()
        case _:
            raise NotImplementedError(f"Unsupported platform: {sys.platform}")


def _install_macos() -> None:
    if shutil.which("brew") is None:
        raise RuntimeError(
            "Homebrew not found. Install it from https://brew.sh then retry."
        )
    rprint("[blue]Installing PrusaSlicer via Homebrew...[/blue]")
    subprocess.run(["brew", "install", "--cask", "prusaslicer"], check=True)
    rprint("✅ PrusaSlicer installed.")


def _install_linux() -> None:
    if shutil.which("brew") is not None:
        rprint("[blue]Installing PrusaSlicer via Homebrew...[/blue]")
        subprocess.run(["brew", "install", "prusaslicer"], check=True)
        rprint("✅ PrusaSlicer installed.")
    elif shutil.which("snap") is not None:
        rprint("[blue]Installing PrusaSlicer via snap...[/blue]")
        subprocess.run(["sudo", "snap", "install", "prusaslicer"], check=True)
        rprint("✅ PrusaSlicer installed.")
    else:
        raise RuntimeError(
            "No supported package manager found (brew or snap). "
            "Install PrusaSlicer manually from https://www.prusa3d.com/prusaslicer/"
        )


def _install_windows() -> None:
    if shutil.which("winget") is None:
        raise RuntimeError(
            "winget not found. Update Windows or install App Installer from the Microsoft Store."
        )
    rprint("[blue]Installing PrusaSlicer via winget...[/blue]")
    subprocess.run(
        [
            "winget", "install",
            "--exact", "--id", "Prusa3D.PrusaSlicer",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ],
        check=True,
    )
    rprint("✅ PrusaSlicer installed.")
