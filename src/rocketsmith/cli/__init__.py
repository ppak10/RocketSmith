from .__main__ import app

# from .version import register_version

from rocketsmith.mcp.cli import app as mcp_app
from rocketsmith.workspace.cli import app as workspace_app

__all__ = ["app"]

app.add_typer(mcp_app, name="mcp", rich_help_panel="Configuration Commands")
app.add_typer(workspace_app, name="workspace", rich_help_panel="Configuration Commands")

# _ = register_version(app)

if __name__ == "__main__":
    app()
