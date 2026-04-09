from mcp.server.fastmcp import FastMCP


def register_openrocket_new(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import (
        get_project_dir,
        resolve_path,
        tool_success,
        tool_error,
    )

    @app.tool(
        title="New OpenRocket File",
        description="Create a new empty OpenRocket .ork file with a single stage.",
        structured_output=True,
    )
    async def openrocket_new(
        name: str,
        out_path: Path | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Create a new OpenRocket design file with an empty rocket and one stage.

        Args:
            name: Display name for the rocket (stored inside the .ork file). This
                  is the name OpenRocket shows in its UI — it is not a filename.
                  If it happens to end in ``.ork``, the suffix is stripped before
                  being used as the default filename (to avoid ``foo.ork.ork``).
            out_path: **Absolute** path where the .ork file should be saved.
                      If omitted, defaults to ``{name}.ork`` in the current
                      working directory — but note that when this tool runs
                      inside a Gemini CLI extension, the MCP subprocess cwd is
                      the extension directory, not the user's project. Always
                      pass an explicit absolute path derived from the user's
                      project directory. The ``.ork`` extension is normalised
                      automatically (``foo`` → ``foo.ork``, ``foo.ork.ork`` →
                      ``foo.ork``).
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
        """
        from rocketsmith.openrocket.components import new_ork
        from rocketsmith.openrocket.utils import get_openrocket_path

        # Strip ``.ork`` from the display name if the caller accidentally
        # passed a filename. The display name is stored inside the .ork file
        # as the rocket's label — it should not contain an extension.
        display_name = name[:-4] if name.endswith(".ork") else name

        if out_path is None:
            out_path = get_project_dir() / f"{display_name}.ork"

        out_path = resolve_path(out_path)

        # Normalise the ``.ork`` suffix: strip any number of trailing ``.ork``
        # components and append exactly one. Handles ``foo`` → ``foo.ork``,
        # ``foo.ork`` → ``foo.ork``, and ``foo.ork.ork`` → ``foo.ork``.
        path_str = str(out_path)
        while path_str.endswith(".ork"):
            path_str = path_str[:-4]
        out_path = Path(path_str + ".ork")

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            result_path = new_ork(
                name=display_name, output_path=out_path, jar_path=openrocket_path
            )
            return tool_success({"path": str(result_path), "name": display_name})

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
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_new
