from mcp.server.fastmcp import FastMCP

from rocketsmith.mcp.setup import register_setup
from rocketsmith.openrocket.mcp import (
    register_openrocket_simulate,
    register_openrocket_new,
    register_openrocket_inspect,
    register_openrocket_component,
    register_openrocket_database,
    register_openrocket_flight,
)
from rocketsmith.prusaslicer.mcp import register_prusaslicer_slice
from rocketsmith.build123d.mcp import (
    register_build123d_extract,
    register_build123d_visualize,
    register_build123d_render,
)
from rocketsmith.rag.mcp import register_rag_reference

app = FastMCP(name="rocketsmith")

_ = register_setup(app)
_ = register_openrocket_simulate(app)
_ = register_openrocket_new(app)
_ = register_openrocket_inspect(app)
_ = register_openrocket_component(app)
_ = register_openrocket_database(app)
_ = register_openrocket_flight(app)
_ = register_prusaslicer_slice(app)
_ = register_build123d_extract(app)
_ = register_build123d_visualize(app)
_ = register_build123d_render(app)
_ = register_rag_reference(app)


def main():
    """Entry point for the direct execution server."""
    app.run()


if __name__ == "__main__":
    main()
