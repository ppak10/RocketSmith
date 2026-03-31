from mcp.server.fastmcp import FastMCP


def register_openrocket_simulate(app: FastMCP):
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error
    from rocketsmith.openrocket.models import OpenRocketSimulationSummary

    @app.tool(
        title="Run OpenRocket Simulation",
        description="Run all simulations in an OpenRocket .ork file and return flight summaries.",
        structured_output=True,
    )
    async def openrocket_simulate(
        ork_path: Path,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[list[OpenRocketSimulationSummary]], ToolError]:
        """
        Run all simulations defined in an OpenRocket design file.

        Args:
            ork_path: Path to the OpenRocket .ork design file.
            openrocket_path: Optional path to the OpenRocket JAR file. If not
                             provided, the installed JAR is located automatically.
        """
        from orhelper import FlightDataType, FlightEvent
        from rocketsmith.openrocket.simulation import run_simulation
        from rocketsmith.openrocket.utils import get_openrocket_path

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

                max_altitude_m = float(altitude.max()) if altitude is not None else 0.0
                max_velocity_ms = float(velocity.max()) if velocity is not None else 0.0
                flight_time_s = float(time.max()) if time is not None else 0.0

                apogee_events = sim.events.get(FlightEvent.APOGEE)
                time_to_apogee_s = float(apogee_events[0]) if apogee_events else None

                summaries.append(OpenRocketSimulationSummary(
                    name=sim.name,
                    max_altitude_m=max_altitude_m,
                    max_velocity_ms=max_velocity_ms,
                    time_to_apogee_s=time_to_apogee_s,
                    flight_time_s=flight_time_s,
                ))

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
