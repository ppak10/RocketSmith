import logging
import sys

# MCP communicates over stdio. Redirect all logging to stderr so nothing
# from this process or its dependencies can corrupt the JSON-RPC stream on stdout.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

from mcp.server.fastmcp import FastMCP

from rocketsmith.mcp.setup import register_setup
from rocketsmith.openrocket.mcp import (
    register_openrocket_simulate,
    register_openrocket_new,
    register_openrocket_inspect,
    register_openrocket_component,
    register_openrocket_database,
    register_openrocket_flight,
    register_openrocket_cad_handoff,
    register_openrocket_report,
)
from rocketsmith.prusaslicer.mcp import (
    register_prusaslicer_slice,
    register_prusaslicer_config,
    register_prusaslicer_database,
)
from rocketsmith.cadsmith.mcp import (
    register_cadsmith_extract,
    register_cadsmith_render,
    register_cadsmith_script,
)
from rocketsmith.gui.mcp import register_gui_start
from rocketsmith.manufacturing.mcp import register_manufacturing_manifest
from rocketsmith.rag.mcp import register_rag_reference

app = FastMCP(name="rocketsmith")

_ = register_setup(app)
_ = register_openrocket_simulate(app)
_ = register_openrocket_new(app)
_ = register_openrocket_inspect(app)
_ = register_openrocket_component(app)
_ = register_openrocket_database(app)
_ = register_openrocket_flight(app)
_ = register_openrocket_cad_handoff(app)
_ = register_openrocket_report(app)
_ = register_prusaslicer_slice(app)
_ = register_prusaslicer_config(app)
_ = register_prusaslicer_database(app)
_ = register_cadsmith_extract(app)
_ = register_cadsmith_render(app)
_ = register_cadsmith_script(app)
_ = register_gui_start(app)
_ = register_manufacturing_manifest(app)
_ = register_rag_reference(app)


def main():
    """Entry point for the direct execution server."""
    app.run()


if __name__ == "__main__":
    main()
