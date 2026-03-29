from mcp.server.fastmcp import FastMCP

from rocketsmith.workspace.mcp import register_workspace_create

app = FastMCP(name="rocketsmith")

_ = register_workspace_create(app)


def main():
    """Entry point for the direct execution server."""
    app.run()


if __name__ == "__main__":
    main()
