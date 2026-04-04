from mcp.server.fastmcp import FastMCP


def register_openrocket_simulate(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error, resolve_workspace
    from rocketsmith.openrocket.models import OpenRocketSimulationSummary

    @app.tool(
        title="Run OpenRocket Simulation",
        description="Run all simulations in an OpenRocket .ork file and return flight summaries.",
        structured_output=True,
    )
    async def openrocket_simulate(
        ork_filename: str,
        workspace_name: str | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[list[OpenRocketSimulationSummary]], ToolError]:
        """
        Run all simulations defined in an OpenRocket design file.

        Returns a summary per simulation including max_altitude_m, max_velocity_ms,
        time_to_apogee_s, flight_time_s, min_stability_cal, and max_stability_cal.

        Note on stability values: min_stability_cal and max_stability_cal may return
        null if the OpenRocket JAR does not expose TYPE_STABILITY in its timeseries API.
        If null, compute stability manually from the component tree:
            stability_cal = (CP_from_nose_m - CG_from_nose_m) / reference_diameter_m
        where reference_diameter_m is the maximum body diameter. Use openrocket_inspect
        to read the component tree and derive CG/CP positions, or apply the Barrowman
        equations directly from component dimensions.

        Args:
            ork_filename: The .ork file in the workspace openrocket/ folder.
            workspace_name: The workspace name.
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
        """
        from orhelper import FlightDataType, FlightEvent
        from rocketsmith.openrocket.simulation import run_simulation
        from rocketsmith.openrocket.utils import get_openrocket_path

        workspace_or_error = resolve_workspace(workspace_name)
        if isinstance(workspace_or_error, ToolError):
            return workspace_or_error
        workspace = workspace_or_error

        if not ork_filename.endswith(".ork"):
            ork_filename += ".ork"

        ork_path = workspace.path / "openrocket" / ork_filename

        if not ork_path.exists():
            return tool_error(
                f"OpenRocket file not found: {ork_path}",
                "FILE_NOT_FOUND",
                ork_path=str(ork_path),
            )

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            simulations = run_simulation(
                ork_path=ork_path,
                openrocket_path=openrocket_path,
            )

            summaries = []
            for sim in simulations:
                altitude = sim.timeseries.get(FlightDataType.TYPE_ALTITUDE)
                velocity = sim.timeseries.get(FlightDataType.TYPE_VELOCITY_TOTAL)
                time = sim.timeseries.get(FlightDataType.TYPE_TIME)
                stability = sim.timeseries.get(FlightDataType.TYPE_STABILITY)

                max_altitude_m = float(altitude.max()) if altitude is not None else 0.0
                max_velocity_ms = float(velocity.max()) if velocity is not None else 0.0
                flight_time_s = float(time.max()) if time is not None else 0.0

                apogee_events = sim.events.get(FlightEvent.APOGEE)
                time_to_apogee_s = float(apogee_events[0]) if apogee_events else None

                # Prefer FlightData direct values; fall back to timeseries
                if (
                    sim.min_stability_cal is not None
                    or sim.max_stability_cal is not None
                ):
                    min_stability_cal = sim.min_stability_cal
                    max_stability_cal = sim.max_stability_cal
                else:
                    min_stability_cal = (
                        float(stability.min()) if stability is not None else None
                    )
                    max_stability_cal = (
                        float(stability.max()) if stability is not None else None
                    )

                summaries.append(
                    OpenRocketSimulationSummary(
                        name=sim.name,
                        max_altitude_m=max_altitude_m,
                        max_velocity_ms=max_velocity_ms,
                        time_to_apogee_s=time_to_apogee_s,
                        flight_time_s=flight_time_s,
                        min_stability_cal=min_stability_cal,
                        max_stability_cal=max_stability_cal,
                    )
                )

            return tool_success(summaries)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                ork_path=str(ork_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to run OpenRocket simulation",
                "SIMULATION_FAILED",
                ork_path=str(ork_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_simulate
