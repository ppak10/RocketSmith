from mcp.server.fastmcp import FastMCP


def register_openrocket_new(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        title="New OpenRocket File",
        description="Create a new empty OpenRocket .ork file with a single stage.",
        structured_output=True,
    )
    async def openrocket_new(
        name: str,
        output_path: Path,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Create a new OpenRocket design file with an empty rocket and one stage.

        Args:
            name: Display name for the rocket (stored inside the .ork file).
            output_path: Where to write the new .ork file.
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
        """
        from rocketsmith.openrocket.components import new_ork
        from rocketsmith.openrocket.utils import get_openrocket_path

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            result_path = new_ork(name=name, output_path=output_path, jar_path=openrocket_path)
            return tool_success({"path": str(result_path), "name": name})

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to create OpenRocket file",
                "CREATE_FAILED",
                output_path=str(output_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_new
