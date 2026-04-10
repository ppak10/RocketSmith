"""MCP tool: generate flight reports from OpenRocket simulations."""

from mcp.server.fastmcp import FastMCP


def register_openrocket_report(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolError, ToolSuccess
    from rocketsmith.mcp.utils import resolve_path, tool_error, tool_success
    from rocketsmith.openrocket.models import FlightReportResult

    @app.tool(
        title="Generate OpenRocket Flight Report",
        description=(
            "Run all simulations in an OpenRocket .ork file and generate a "
            "flight report for each simulation. Each report is a Markdown file "
            "with embedded plot references, saved alongside altitude, velocity, "
            "acceleration, stability, thrust/mass, and drag/Mach plots as PNGs. "
            "Reports are written to <project_root>/openrocket/reports/<sim_name>/."
        ),
        structured_output=True,
    )
    async def openrocket_report(
        rocket_file_path: Path,
        project_root: Path | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[list[FlightReportResult]], ToolError]:
        """Generate flight reports with plots for every simulation in a rocket file.

        Args:
            rocket_file_path: Path to the .ork (or .rkt) design file.
            project_root:     Project directory; reports go to
                              ``<project_root>/openrocket/reports/<sim_name>/``.
                              Defaults to the rocket file's grandparent
                              (assuming the file lives at
                              ``<project_root>/openrocket/<name>.ork``).
            openrocket_path:  Path to the OpenRocket JAR.  Auto-detected if
                              omitted.

        Returns:
            On success, a list of ``FlightReportResult`` objects with paths to
            the generated report and plots, plus the key flight summary numbers.
        """
        from rocketsmith.openrocket.report import generate_flight_report
        from rocketsmith.openrocket.simulation import run_simulation
        from rocketsmith.openrocket.utils import get_openrocket_path

        rocket_file_path = resolve_path(rocket_file_path)
        if not rocket_file_path.exists():
            return tool_error(
                f"Design file not found: {rocket_file_path}",
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
            )

        if project_root is not None:
            project_root = resolve_path(project_root)
        else:
            # Convention: <project_root>/openrocket/<name>.ork
            project_root = rocket_file_path.parent.parent

        reports_base = project_root / "openrocket" / "reports"

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            sims = run_simulation(
                path=rocket_file_path,
                openrocket_path=openrocket_path,
            )

            if not sims:
                return tool_error(
                    "No simulations found in the rocket file. "
                    "Use openrocket_flight(action='create', ...) to add one first.",
                    "NO_SIMULATIONS",
                    file_path=str(rocket_file_path),
                )

            from datetime import datetime, timezone

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            results: list[FlightReportResult] = []
            for sim in sims:
                # Folder name: timestamp + sanitized sim name for
                # chronological sorting while remaining identifiable.
                safe_name = (
                    sim.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
                )
                dir_name = f"{timestamp}_{safe_name}"
                out_dir = reports_base / dir_name
                result = generate_flight_report(sim, out_dir)
                results.append(result)

            return tool_success(results)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
            )
        except Exception as e:
            return tool_error(
                "Failed to generate flight report",
                "REPORT_FAILED",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_report
