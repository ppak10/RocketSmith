import logging
import sys

# MCP communicates over stdio. Redirect all logging to stderr so nothing
# from this process or its dependencies can corrupt the JSON-RPC stream on stdout.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

from mcp.server.fastmcp import FastMCP

from rocketsmith.mcp.setup import register_setup
from rocketsmith.openrocket.mcp import (
    register_openrocket_new,
    register_openrocket_component,
    register_openrocket_database,
    register_openrocket_flight,
    register_openrocket_generate_tree,
)
from rocketsmith.prusaslicer.mcp import (
    register_prusaslicer_slice,
    register_prusaslicer_config,
    register_prusaslicer_database,
)
from rocketsmith.cadsmith.mcp import (
    register_cadsmith_assembly,
    register_cadsmith_bd_warehouse_info,
    register_cadsmith_extract_part,
    register_cadsmith_generate_preview,
    register_cadsmith_run_script,
)
from rocketsmith.gui.mcp import register_gui_navigate, register_gui_server
from rocketsmith.manufacturing.mcp import register_manufacturing_annotate_tree
from rocketsmith.rag.mcp import register_rag_reference

app = FastMCP(name="rocketsmith")

_ = register_setup(app)
_ = register_openrocket_new(app)
_ = register_openrocket_component(app)
_ = register_openrocket_database(app)
_ = register_openrocket_flight(app)
_ = register_openrocket_generate_tree(app)
_ = register_prusaslicer_slice(app)
_ = register_prusaslicer_config(app)
_ = register_prusaslicer_database(app)
_ = register_cadsmith_assembly(app)
_ = register_cadsmith_bd_warehouse_info(app)
_ = register_cadsmith_extract_part(app)
_ = register_cadsmith_generate_preview(app)
_ = register_cadsmith_run_script(app)
_ = register_gui_server(app)
_ = register_gui_navigate(app)
_ = register_manufacturing_annotate_tree(app)
_ = register_rag_reference(app)


def main():
    """Entry point for the direct execution server."""
    app.run()


if __name__ == "__main__":
    main()
