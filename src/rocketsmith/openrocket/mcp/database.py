from mcp.server.fastmcp import FastMCP


def register_openrocket_database(app: FastMCP):
    from pathlib import Path
    from typing import Literal, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        title="OpenRocket Database",
        description=(
            "Query the OpenRocket built-in database for motors, component presets, or materials. "
            "Use 'action' to specify what to query. "
            "Valid preset types: body-tube, nose-cone, transition, tube-coupler, bulk-head, "
            "centering-ring, engine-block, launch-lug, rail-button, streamer, parachute. "
            "Valid material types: bulk, surface, line. "
            "Use 'limit' to cap the number of results returned (default 50, max unbounded)."
        ),
        structured_output=True,
    )
    async def openrocket_database(
        action: Literal["motors", "presets", "materials"],
        manufacturer: str | None = None,
        impulse_class: str | None = None,
        diameter_mm: float | None = None,
        motor_type: str | None = None,
        preset_type: str | None = None,
        material_type: str | None = None,
        limit: int | None = 50,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[list[dict]], ToolError]:
        """
        Query the OpenRocket built-in database.

        Actions:
            motors:    List available rocket motors. Without filters returns all ~1,900 motors.
                       Use filters to narrow results.
            presets:   List real manufacturer components by type. Requires 'preset_type'.
            materials: List structural materials. Requires 'material_type'.

        Args:
            action: One of 'motors', 'presets', 'materials'.
            manufacturer: Filter by manufacturer name substring (motors and presets).
            impulse_class: Filter motors by impulse class letter, e.g. 'D', 'F', 'H'.
            diameter_mm: Filter motors by diameter in mm, e.g. 18, 24, 29, 38, 54.
            motor_type: Filter motors by type: 'single-use', 'reloadable', 'hybrid'.
            preset_type: Required for 'presets'. One of: body-tube, nose-cone, transition,
                         tube-coupler, bulk-head, centering-ring, engine-block, launch-lug,
                         rail-button, streamer, parachute.
            material_type: Required for 'materials'. One of: bulk, surface, line.
            limit: Maximum number of results to return. Defaults to 50. Pass None for all results.
            openrocket_path: Optional path to the OpenRocket JAR file.
        """
        from rocketsmith.openrocket.database import list_motors, list_presets, list_materials
        from rocketsmith.openrocket.utils import get_openrocket_path

        def _apply_limit(items: list) -> list:
            return items[:limit] if limit is not None else items

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            if action == "motors":
                results = list_motors(
                    openrocket_path,
                    manufacturer=manufacturer,
                    impulse_class=impulse_class,
                    diameter_mm=diameter_mm,
                    motor_type=motor_type,
                )
                return tool_success(_apply_limit(results))

            elif action == "presets":
                if preset_type is None:
                    return tool_error(
                        "'preset_type' is required for action 'presets'.",
                        "MISSING_ARGUMENT",
                    )
                results = list_presets(openrocket_path, preset_type, manufacturer=manufacturer)
                return tool_success(_apply_limit(results))

            elif action == "materials":
                if material_type is None:
                    return tool_error(
                        "'material_type' is required for action 'materials'. Valid: bulk, surface, line.",
                        "MISSING_ARGUMENT",
                    )
                results = list_materials(openrocket_path, material_type)
                return tool_success(_apply_limit(results))

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                exception_type=type(e).__name__,
            )

        except ValueError as e:
            return tool_error(
                str(e),
                "INVALID_ARGUMENT",
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                f"Failed to query {action} database",
                "DATABASE_QUERY_FAILED",
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_database
