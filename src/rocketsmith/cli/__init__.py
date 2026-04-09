from .__main__ import app

from rocketsmith.mcp.cli import app as mcp_app
from rocketsmith.openrocket.cli import app as openrocket_app
from rocketsmith.prusaslicer.cli import app as prusaslicer_app
from rocketsmith.build123d.cli import app as build123d_app
from rocketsmith.cli.setup import app as setup_app
from rocketsmith.cli.update import register_update

__all__ = ["app"]

app.add_typer(mcp_app, name="mcp", rich_help_panel="Configuration Commands")
app.add_typer(setup_app, name="setup", rich_help_panel="Configuration Commands")
app.add_typer(openrocket_app, name="openrocket", rich_help_panel="Tools")
app.add_typer(prusaslicer_app, name="prusaslicer", rich_help_panel="Tools")
app.add_typer(build123d_app, name="build123d", rich_help_panel="Tools")

_ = register_update(app)

if __name__ == "__main__":
    app()
