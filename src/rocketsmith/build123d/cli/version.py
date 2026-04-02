import typer

from rich import print as rprint


def register_build123d_version(app: typer.Typer):
    @app.command(name="version")
    def build123d_version() -> None:
        """Show the installed build123d version."""
        from rocketsmith.build123d.utils import get_build123d_version

        try:
            version = get_build123d_version()
            rprint(f"[bold green]build123d[/bold green] {version}")
        except Exception as e:
            rprint(f"⚠️  [yellow]Could not determine build123d version: {e}[/yellow]")
            raise typer.Exit(1)

    return build123d_version
