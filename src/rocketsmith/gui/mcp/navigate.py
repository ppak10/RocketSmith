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
            "Routes: '#/' (Agent Feed), '#/flights', '#/component-tree', "
            "'#/assembly', '#/parts/<name>' (part detail). "
            "Part paths use '#/parts/<name>' not '/gui/parts/...'. "
            "Requires the GUI server to be running."
        ),
        structured_output=True,
    )
    async def gui_navigate(
        path: str,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Navigate the GUI to a route path.

        The GUI uses a HashRouter, so the URL looks like:
        http://127.0.0.1:5173/#/parts/nose_cone

        Args:
            path: Hash route path to navigate to. Examples:
                "#/" — Agent Feed (live dashboard with cards)
                "#/flights" — Flight viewer (charts from flight JSON)
                "#/component-tree" — Component tree (rocket profile + parts list)
                "#/assembly" — Assembly viewer (3D spatial layout)
                "#/parts/nose_cone" — Part detail page (3D model + source code)
                "#/parts/upper_body_tube" — Part detail page

            Note: part paths use "#/parts/<name>" (NOT "/gui/parts/...").
            The route strips the "gui/" prefix — the frontend adds it back
            when loading the file.
        """
        import json
        import urllib.request
        import urllib.error

        from rocketsmith.gui.mcp.server import DEFAULT_HOST, DEFAULT_PORT, WS_PORT

        # Normalize: strip leading '#' — React Router's navigate() expects a
        # plain path ("/component-tree"), not a hash fragment ("#/component-tree").
        normalized_path = path.lstrip("#") or "/"
        payload = json.dumps({"path": normalized_path}).encode("utf-8")

        reached = []
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
                        reached.append(port)
            except (urllib.error.URLError, OSError):
                continue

        if reached:
            return tool_success(
                {
                    "path": normalized_path,
                    "message": f"Navigated to {normalized_path}",
                }
            )

        return tool_error(
            "GUI server is not running. Start it with gui_server(action='start').",
            "SERVER_NOT_RUNNING",
        )

    return gui_navigate
