from mcp.server.fastmcp import FastMCP


def register_gui_navigate(app: FastMCP):
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        name="gui_navigate",
        title="Navigate GUI",
        description=(
            "Navigate the RocketSmith GUI to a specific route path. "
            "Requires the GUI server to be running."
        ),
        structured_output=True,
    )
    async def gui_navigate(
        path: str,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Navigate the GUI to a route path.

        Args:
            path: Route path to navigate to. Examples:
                "/" — Live page
                "/flights" — Flight viewer
                "/component-tree" — Component tree
                "/assembly" — Assembly viewer
                "/parts/nose_cone.json" — Part detail page
        """
        import json
        import urllib.request
        import urllib.error

        from rocketsmith.gui.mcp.server import DEFAULT_HOST, DEFAULT_PORT, WS_PORT

        payload = json.dumps({"path": path}).encode("utf-8")

        for port in [DEFAULT_PORT, WS_PORT]:
            url = f"http://{DEFAULT_HOST}:{port}/api/navigate"
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        return tool_success(
                            {
                                "path": path,
                                "message": f"Navigated to {path}",
                            }
                        )
            except (urllib.error.URLError, OSError):
                continue

        return tool_error(
            "GUI server is not running. Start it with gui_server(action='start').",
            "SERVER_NOT_RUNNING",
        )

    return gui_navigate
