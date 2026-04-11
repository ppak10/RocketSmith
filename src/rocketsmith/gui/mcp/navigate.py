from mcp.server.fastmcp import FastMCP


def register_gui_navigate(app: FastMCP):
    from typing import Optional, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        name="gui_navigate",
        title="Navigate GUI",
        description=(
            "Send a navigation command to the RocketSmith GUI. "
            "Switches the dashboard to a specific panel and optionally "
            "opens a file within that panel. Requires the GUI server "
            "to be running."
        ),
        structured_output=True,
    )
    async def gui_navigate(
        panel: str,
        file: Optional[str] = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Navigate the GUI to a specific panel.

        Args:
            panel: Panel to navigate to. One of "live", "3d-viewer",
                   "flight-profile", or "flight".
            file: Optional relative path to a file to open in the panel
                  (e.g. "step/nose_cone.step"). Relative to project root.
        """
        import aiohttp

        valid_panels = {"live", "3d-viewer", "flight-profile", "flight", "assembly"}
        if panel not in valid_panels:
            return tool_error(
                f"Unknown panel: {panel!r}. Use one of: {', '.join(sorted(valid_panels))}.",
                "INVALID_PANEL",
                panel=panel,
                valid_panels=sorted(valid_panels),
            )

        from rocketsmith.gui.mcp.server import DEFAULT_HOST, DEFAULT_PORT, WS_PORT

        # Try the production port first, then the dev WS port.
        for port in [DEFAULT_PORT, WS_PORT]:
            url = f"http://{DEFAULT_HOST}:{port}/api/navigate"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={"panel": panel, "file": file},
                        timeout=aiohttp.ClientTimeout(total=2),
                    ) as resp:
                        if resp.status == 200:
                            return tool_success(
                                {
                                    "panel": panel,
                                    "file": file,
                                    "message": f"Navigated to {panel}"
                                    + (f" with {file}" if file else ""),
                                }
                            )
            except (aiohttp.ClientError, OSError):
                continue

        return tool_error(
            "GUI server is not running. Start it with gui_server(action='start').",
            "SERVER_NOT_RUNNING",
        )

    return gui_navigate
