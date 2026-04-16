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
    register_cadsmith_generate_assets,
    register_cadsmith_run_script,
)
from rocketsmith.gui.mcp import register_gui_navigate, register_gui_server
from rocketsmith.gui.mcp.logging import LoggingApp
from rocketsmith.manufacturing.mcp import register_manufacturing_annotate_tree
from rocketsmith.rag.mcp import register_rag_reference

app = FastMCP(name="rocketsmith")
logged = LoggingApp(app)

_ = register_setup(logged)
_ = register_openrocket_new(logged)
_ = register_openrocket_component(logged)
_ = register_openrocket_database(logged)
_ = register_openrocket_flight(logged)
_ = register_prusaslicer_slice(logged)
_ = register_prusaslicer_config(logged)
_ = register_prusaslicer_database(logged)
_ = register_cadsmith_assembly(logged)
_ = register_cadsmith_bd_warehouse_info(logged)
_ = register_cadsmith_extract_part(logged)
_ = register_cadsmith_generate_assets(logged)
_ = register_cadsmith_run_script(logged)
_ = register_gui_server(logged)
_ = register_gui_navigate(logged)
_ = register_manufacturing_annotate_tree(logged)
_ = register_rag_reference(logged)


def main():
    """Entry point for the direct execution server."""
    try:
        app.run()
    except (BrokenPipeError, EOFError):
        # stdio transport closed by the client (normal shutdown or tool rejection).
        # Exit cleanly so the process does not appear to have crashed.
        sys.exit(0)
    except Exception as e:
        print(
            f"rocketsmith MCP server error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
