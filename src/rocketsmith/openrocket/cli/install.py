import typer

from rich import print as rprint


def register_openrocket_install(app: typer.Typer):
    @app.command(name="install")
    def openrocket_install() -> None:
        """Install OpenRocket using the appropriate method for the current platform."""
        from rocketsmith.openrocket.install import install

        try:
            install()
        except NotImplementedError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)
        except RuntimeError as e:
            rprint(f"⚠️  [yellow]{e}[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            rprint(f"⚠️  [yellow]Installation failed: {e}[/yellow]")
            raise typer.Exit(1)

    return openrocket_install
