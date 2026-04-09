from mcp.server.fastmcp import FastMCP

from pathlib import Path
from typing import Literal, Union


def register_prusaslicer_database(app: FastMCP):
    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        name="prusaslicer_database",
        title="PrusaSlicer Vendor Preset Database",
        description=(
            "Search PrusaSlicer's bundled vendor preset database for printer, filament, "
            "and print profiles. Inheritance is resolved so results include meaningful "
            "settings (bed size, temperatures, layer height, etc.) rather than just "
            "inherits references. "
            "Use 'vendor' to filter by vendor name (e.g. 'Voron', 'Prusa') and 'name' "
            "to filter by preset name substring. Use 'limit' to cap results (default 50). "
            "Paths returned can be passed to prusaslicer_config to import a preset into "
            "the project."
        ),
        structured_output=True,
    )
    async def prusaslicer_database(
        action: Literal["printer", "filament", "print"],
        vendor: str | None = None,
        name: str | None = None,
        limit: int | None = 50,
        prusaslicer_path: Path | None = None,
    ) -> Union[ToolSuccess[list[dict]], ToolError]:
        """
        Search the PrusaSlicer vendor preset database.

        Args:
            action: Profile category to search — printer, filament, or print.
            vendor: Filter by vendor name substring, e.g. 'Voron', 'Prusa', 'Creality'.
            name: Filter by preset name substring, e.g. '350', 'PETG', '0.20mm'.
            limit: Maximum number of results to return. Defaults to 50. Pass None for all.
            prusaslicer_path: Optional path to the PrusaSlicer executable, used to
                              locate the bundled profiles directory.
        """
        from rocketsmith.prusaslicer.database import get_profiles_path, list_database

        try:
            profiles_path = get_profiles_path(prusaslicer_path)
        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "PRUSASLICER_NOT_FOUND",
                exception_type=type(e).__name__,
            )

        try:
            results = list_database(
                profiles_path,
                action,
                vendor=vendor,
                name=name,
            )

            if limit is not None:
                results = results[:limit]

            return tool_success(results)

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

    _ = prusaslicer_database
