from mcp.server.fastmcp import FastMCP


def register_openrocket_cad_handoff(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error

    @app.tool(
        title="OpenRocket → CAD Handoff",
        description=(
            "Convert an OpenRocket .ork or RockSim .rkt design into CAD-ready "
            "parameters in millimetres. Reads every component, multiplies each "
            "length by 1000, identifies the motor mount, and returns a dict "
            "ready to feed into build123d scripts. Eliminates the m↔mm "
            "conversion as a source of hand-computed errors."
        ),
        structured_output=True,
    )
    async def openrocket_cad_handoff(
        rocket_file_path: Path,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Convert an OpenRocket design file into millimetre-scaled CAD parameters.

        Returns a dict with:
          - ``units``: always ``"mm"``.
          - ``source_path``: absolute path to the .ork/.rkt file.
          - ``components``: list of components with every ``_m`` field
            rewritten as ``_mm`` (e.g. ``length_m`` → ``length_mm``). String
            and int fields (shape, fin_count, motor_mount flag, etc.) are
            passed through unchanged.
          - ``derived``: convenience values in mm — ``cg_x_mm``, ``cp_x_mm``,
            ``max_diameter_mm``, ``body_tube_id_mm`` (the primary airframe
            body tube's inner diameter, useful for sizing couplers and
            centering rings), and ``motor_mount`` (the selected motor
            mount component, or ``None`` if no mount is present).
          - ``handoff_notes``: short list of red-flag notes mirroring the
            cad-handoff skill — unit reminder, fin integration rule,
            coupler wall sizing, centering ring clearances.

        Use this output as the single source of truth when writing
        build123d scripts. Never derive dimensions from the ASCII art in
        ``openrocket_inspect`` — that is a sanity check, not a CAD
        source.

        Args:
            rocket_file_path: Path to the .ork or .rkt design file.
            openrocket_path: Optional path to the OpenRocket JAR file. If
                not provided, the installed JAR is located automatically.
        """
        from rocketsmith.openrocket.cad_handoff import cad_handoff
        from rocketsmith.openrocket.utils import get_openrocket_path

        rocket_file_path = resolve_path(rocket_file_path)
        if not rocket_file_path.exists():
            return tool_error(
                f"Design file not found: {rocket_file_path}",
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
            )

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            result = cad_handoff(path=rocket_file_path, jar_path=openrocket_path)
            return tool_success(result)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to build CAD handoff",
                "HANDOFF_FAILED",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_cad_handoff
