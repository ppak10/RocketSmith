import json
import shutil
import subprocess
import sys
import urllib.request

from pathlib import Path
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, DownloadColumn, TransferSpeedColumn, BarColumn, TextColumn

from rocketsmith.prusaslicer.utils import get_prusaslicer_path


_GITHUB_RELEASES_API = "https://api.github.com/repos/prusa3d/PrusaSlicer/releases"
_APPIMAGE_INSTALL_DIR = Path.home() / ".local" / "share" / "prusaslicer"


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
    else:
        _install_appimage()


def _get_latest_appimage_url() -> tuple[str, str]:
    """
    Find the most recent PrusaSlicer release that ships a Linux x64 AppImage
    and return (filename, download_url). Newer releases (2.9+) dropped AppImages
    so this searches backwards until one is found.
    """
    req = urllib.request.Request(
        _GITHUB_RELEASES_API + "?per_page=30",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "rocketsmith"},
    )
    with urllib.request.urlopen(req) as response:
        releases = json.loads(response.read())

    for release in releases:
        asset = next(
            (
                a for a in release["assets"]
                if a["name"].endswith(".AppImage")
                and "linux" in a["name"].lower()
                and "x64" in a["name"].lower()
                and "GTK3" in a["name"]
            ),
            None,
        )
        if asset:
            return asset["name"], asset["browser_download_url"]

    raise RuntimeError("No Linux x64 AppImage found in the last 30 PrusaSlicer releases.")


def _download_file(url: str, dest: Path) -> None:
    """Download a file from url to dest with a progress bar."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading [cyan]{dest.name}[/cyan]...", total=None)

        def _reporthook(block_count, block_size, total_size):
            if total_size > 0:
                progress.update(task, total=total_size, completed=block_count * block_size)

        urllib.request.urlretrieve(url, dest, reporthook=_reporthook)


def _install_appimage() -> None:
    rprint("[blue]Fetching latest PrusaSlicer release from GitHub...[/blue]")
    filename, url = _get_latest_appimage_url()
    dest = _APPIMAGE_INSTALL_DIR / filename

    if dest.exists():
        rprint(f"✅ PrusaSlicer AppImage already at: [cyan]{dest}[/cyan]")
        return

    _download_file(url, dest)
    dest.chmod(dest.stat().st_mode | 0o111)  # make executable
    rprint(f"✅ PrusaSlicer installed at: [cyan]{dest}[/cyan]")


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
