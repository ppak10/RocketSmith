import shutil
import subprocess
import sys
import urllib.request
import json

from pathlib import Path
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, DownloadColumn, TransferSpeedColumn, BarColumn, TextColumn


_GITHUB_RELEASES_API = "https://api.github.com/repos/openrocket/openrocket/releases/latest"


def _get_latest_jar_asset() -> tuple[str, str]:
    """
    Fetch the latest OpenRocket release from GitHub and return (version, download_url)
    for the JAR asset.
    """
    rprint("[blue]Fetching latest OpenRocket release info from GitHub...[/blue]")

    req = urllib.request.Request(
        _GITHUB_RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "rocketsmith"},
    )

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())

    version = data["tag_name"].lstrip("release-").lstrip("v")

    jar_asset = next(
        (a for a in data["assets"] if a["name"].endswith(".jar")),
        None,
    )

    if jar_asset is None:
        raise RuntimeError(
            f"No JAR asset found in OpenRocket release {data['tag_name']}."
        )

    return version, jar_asset["browser_download_url"]


def _download_jar(url: str, dest: Path) -> None:
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


def install() -> None:
    """Install OpenRocket using the appropriate method for the current platform."""
    import re
    from rocketsmith.openrocket.utils import get_openrocket_path

    try:
        jar = get_openrocket_path()
        match = re.search(r"OpenRocket-?([\d.]+)\.jar", jar.name, re.IGNORECASE)
        version = match.group(1) if match else "unknown"
        rprint(f"✅ OpenRocket [bold]{version}[/bold] is already installed at: [cyan]{jar}[/cyan]")
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

    rprint("[blue]Installing OpenRocket via Homebrew...[/blue]")
    subprocess.run(["brew", "install", "--cask", "openrocket"], check=True)
    rprint("✅ OpenRocket installed via Homebrew.")


def _install_linux() -> None:
    version, url = _get_latest_jar_asset()

    dest = Path.home() / ".local" / "share" / "openrocket" / f"OpenRocket-{version}.jar"

    if dest.exists():
        rprint(f"✅ OpenRocket [bold]{version}[/bold] is already installed at: [cyan]{dest}[/cyan]")
        return

    rprint(f"[blue]Downloading OpenRocket {version}...[/blue]")
    _download_jar(url, dest)
    rprint(f"✅ OpenRocket [bold]{version}[/bold] installed at: [cyan]{dest}[/cyan]")


def _install_windows() -> None:
    if shutil.which("winget") is None:
        raise RuntimeError(
            "winget not found. Update Windows or install App Installer from the Microsoft Store."
        )

    rprint("[blue]Installing OpenRocket via winget...[/blue]")
    subprocess.run(
        ["winget", "install", "--exact", "--id", "OpenRocket.OpenRocket"],
        check=True,
    )
    rprint("✅ OpenRocket installed via winget.")
