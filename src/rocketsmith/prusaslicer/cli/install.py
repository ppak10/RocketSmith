import typer

from rich import print as rprint

from rocketsmith.prusaslicer.install import install


def register_prusaslicer_install(app: typer.Typer):
    @app.command(name="install")
    def prusaslicer_install() -> None:
        """Install PrusaSlicer using the appropriate method for the current platform."""
        try:
            install()
        except (RuntimeError, NotImplementedError) as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)

    return prusaslicer_install
