from mcp.server.fastmcp import FastMCP

from rocketsmith.mcp.setup import register_setup
from rocketsmith.workspace.mcp import register_workspace_create
from rocketsmith.openrocket.mcp import (
    register_openrocket_simulate,
    register_openrocket_new,
    register_openrocket_inspect,
    register_openrocket_component,
    register_openrocket_database,
    register_openrocket_flight,
)
from rocketsmith.prusaslicer.mcp import register_prusaslicer_slice

app = FastMCP(name="rocketsmith")

_ = register_setup(app)
_ = register_workspace_create(app)
_ = register_openrocket_simulate(app)
_ = register_openrocket_new(app)
_ = register_openrocket_inspect(app)
_ = register_openrocket_component(app)
_ = register_openrocket_database(app)
_ = register_openrocket_flight(app)
_ = register_prusaslicer_slice(app)


def main():
    """Entry point for the direct execution server."""
    app.run()


if __name__ == "__main__":
    main()
