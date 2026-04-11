from mcp.server.fastmcp import FastMCP


def register_openrocket_simulation(app: FastMCP):
    import json
    from pathlib import Path
    from typing import Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error
    from rocketsmith.openrocket.models import OpenRocketSimulationSummary

    @app.tool(
        name="openrocket_simulation",
        title="Run OpenRocket Simulation",
        description=(
            "Run all simulations in an OpenRocket .ork or RockSim .rkt file. "
            "Saves the full timeseries data as JSON under "
            "openrocket/simulations/<config>_<sim_name>.json and returns "
            "flight summaries with paths to the JSON files."
        ),
        structured_output=True,
    )
    async def openrocket_simulation(
        rocket_file_path: Path,
        project_dir: Path | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[list[OpenRocketSimulationSummary]], ToolError]:
        """
        Run all simulations and save full timeseries data as JSON.

        Each simulation's data is written to
        ``<project_dir>/openrocket/simulations/<config>_<sim_name>.json``
        containing all flight data types (altitude, velocity, stability,
        thrust, drag coefficients, etc.) as arrays indexed by time.

        Args:
            rocket_file_path: Path to the .ork or .rkt design file.
            project_dir: Project directory. If omitted, defaults to the
                         rocket file's grandparent (assuming the file lives
                         at ``<project_dir>/openrocket/<name>.ork``).
            openrocket_path: Optional path to the OpenRocket JAR file.
        """
        from orhelper import FlightDataType, FlightEvent
        from rocketsmith.openrocket.simulation import run_simulation
        from rocketsmith.openrocket.utils import get_openrocket_path

        rocket_file_path = resolve_path(rocket_file_path)
        if not rocket_file_path.exists():
            return tool_error(
                f"Design file not found: {rocket_file_path}",
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
            )

        # Determine project directory and simulations output dir.
        if project_dir is not None:
            proj = resolve_path(project_dir)
        else:
            # Convention: <project_dir>/openrocket/<name>.ork
            proj = rocket_file_path.parent.parent

        sim_dir = proj / "openrocket" / "simulations"
        sim_dir.mkdir(parents=True, exist_ok=True)

        # Config name from the .ork filename (without extension).
        config_name = rocket_file_path.stem

        try:
            if openrocket_path is None:
                openrocket_path = get_openrocket_path()

            simulations = run_simulation(
                path=rocket_file_path,
                openrocket_path=openrocket_path,
            )

            summaries = []
            for sim in simulations:
                # Sanitize simulation name for filename.
                safe_name = (
                    sim.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
                )
                json_filename = f"{config_name}_{safe_name}.json"
                json_path = sim_dir / json_filename

                # Build JSON-serializable timeseries.
                timeseries_data: dict[str, list[float]] = {}
                for fdt, arr in sim.timeseries.items():
                    timeseries_data[fdt.name] = arr.tolist()

                # Build JSON-serializable events.
                events_data: dict[str, list[float]] = {}
                for evt, times in sim.events.items():
                    events_data[evt.name] = times

                # Extract scalar summaries.
                altitude = sim.timeseries.get(FlightDataType.TYPE_ALTITUDE)
                velocity = sim.timeseries.get(FlightDataType.TYPE_VELOCITY_TOTAL)
                time_arr = sim.timeseries.get(FlightDataType.TYPE_TIME)
                stability = sim.timeseries.get(FlightDataType.TYPE_STABILITY)

                max_altitude_m = float(altitude.max()) if altitude is not None else 0.0
                max_velocity_ms = float(velocity.max()) if velocity is not None else 0.0
                flight_time_s = float(time_arr.max()) if time_arr is not None else 0.0

                apogee_events = sim.events.get(FlightEvent.APOGEE)
                time_to_apogee_s = float(apogee_events[0]) if apogee_events else None

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

                # Write the full timeseries JSON.
                output = {
                    "simulation_name": sim.name,
                    "config": config_name,
                    "summary": {
                        "max_altitude_m": max_altitude_m,
                        "max_velocity_ms": max_velocity_ms,
                        "time_to_apogee_s": time_to_apogee_s,
                        "flight_time_s": flight_time_s,
                        "min_stability_cal": min_stability_cal,
                        "max_stability_cal": max_stability_cal,
                    },
                    "timeseries": timeseries_data,
                    "events": events_data,
                }

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=2)

                summaries.append(
                    OpenRocketSimulationSummary(
                        name=sim.name,
                        max_altitude_m=max_altitude_m,
                        max_velocity_ms=max_velocity_ms,
                        time_to_apogee_s=time_to_apogee_s,
                        flight_time_s=flight_time_s,
                        min_stability_cal=min_stability_cal,
                        max_stability_cal=max_stability_cal,
                        timeseries_path=str(json_path),
                    )
                )

            return tool_success(summaries)

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                "Failed to run simulation",
                "SIMULATION_FAILED",
                file_path=str(rocket_file_path),
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_simulation
