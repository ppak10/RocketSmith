import re
import shutil
import subprocess
import sys
import urllib.request

from pathlib import Path
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, DownloadColumn, TransferSpeedColumn, BarColumn, TextColumn

from rocketsmith.openrocket.utils import get_openrocket_jvm, get_openrocket_path


# orhelper 0.1.x is compatible with OpenRocket 23.09 only (net.sf.openrocket package).
# OpenRocket 24+ reorganized Java packages to info.openrocket and is not supported.
OPENROCKET_VERSION = "23.09"
_JAR_URL = (
    f"https://github.com/openrocket/openrocket/releases/download/"
    f"release-{OPENROCKET_VERSION}/OpenRocket-{OPENROCKET_VERSION}.jar"
)


def _get_install_dir() -> Path:
    """Return the platform-appropriate directory for the downloaded JAR."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "OpenRocket"
    return Path.home() / ".local" / "share" / "openrocket"


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
    """Install OpenRocket 23.09 JAR and a Java runtime for the current platform."""
    # Ensure a JRE is available — use a dummy path so get_openrocket_jvm falls
    # through to the system JVM search without needing the JAR to exist yet.
    if get_openrocket_jvm(Path("/nonexistent")) is None:
        _install_java()

    try:
        jar = get_openrocket_path()
        match = re.search(r"OpenRocket-?([\d.]+)\.jar", jar.name, re.IGNORECASE)
        version = match.group(1) if match else "unknown"
        rprint(f"✅ OpenRocket [bold]{version}[/bold] is already installed at: [cyan]{jar}[/cyan]")
        return
    except FileNotFoundError:
        pass

    _install_jar()


def _install_jar() -> None:
    dest = _get_install_dir() / f"OpenRocket-{OPENROCKET_VERSION}.jar"
    rprint(f"[blue]Downloading OpenRocket {OPENROCKET_VERSION}...[/blue]")
    _download_jar(_JAR_URL, dest)
    rprint(f"✅ OpenRocket [bold]{OPENROCKET_VERSION}[/bold] installed at: [cyan]{dest}[/cyan]")


def _install_java() -> None:
    """Install a Java runtime using the appropriate method for the current platform."""
    match sys.platform:
        case "darwin":
            if shutil.which("brew") is None:
                raise RuntimeError(
                    "Homebrew not found. Install it from https://brew.sh then retry, "
                    "or install a Java runtime manually."
                )
            rprint("[blue]Installing Java runtime via Homebrew (openjdk)...[/blue]")
            subprocess.run(["brew", "install", "openjdk"], check=True)
            rprint("✅ Java runtime installed.")
        case "linux":
            rprint("[blue]Installing Java runtime via apt...[/blue]")
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "default-jre-headless"],
                check=True,
            )
            rprint("✅ Java runtime installed.")
        case "win32":
            if shutil.which("winget") is None:
                raise RuntimeError(
                    "winget not found. Install a Java runtime manually from https://adoptium.net"
                )
            rprint("[blue]Installing Java runtime via winget (Temurin)...[/blue]")
            subprocess.run(
                [
                    "winget", "install",
                    "--exact", "--id", "EclipseAdoptium.Temurin.21.JRE",
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ],
                check=True,
            )
            rprint("✅ Java runtime installed.")
        case _:
            raise NotImplementedError(
                f"Unsupported platform: {sys.platform}. "
                "Install a Java runtime manually then retry."
            )
