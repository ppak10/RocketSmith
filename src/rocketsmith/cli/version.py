import importlib.metadata
import typer

from rich import print as rprint


def register_version(app: typer.Typer):
    @app.command()
    def version() -> None:
        """Show the installed version of `rocketsmith` package."""
        try:
            version = importlib.metadata.version("rocketsmith")
            rprint(f"✅ rocketsmith version {version}")
        except importlib.metadata.PackageNotFoundError:
            rprint(
                "⚠️  [yellow]rocketsmith version unknown (package not installed)[/yellow]"
            )
            raise typer.Exit()

    return version
