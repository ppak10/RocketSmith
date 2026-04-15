from mcp.server.fastmcp import FastMCP


def register_openrocket_flight(app: FastMCP):
    import json
    from pathlib import Path
    from typing import Literal, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import resolve_path, tool_success, tool_error
    from rocketsmith.openrocket.models import OpenRocketFlightSummary

    @app.tool(
        title="OpenRocket or RockSim Flight",
        description=(
            "Create, delete, or run flight configurations in an OpenRocket .ork "
            "or RockSim .rkt file. "
            "Use 'create' to assign a motor to a mount and add a flight config. "
            "Use 'delete' to remove a flight config by name. "
            "Use 'run' to execute all flight configs and save full timeseries data."
        ),
        structured_output=True,
    )
    async def openrocket_flight(
        action: Literal["create", "delete", "run"],
        rocket_file_path: Path,
        motor_designation: str | None = None,
        sim_name: str | None = None,
        mount_name: str | None = None,
        launch_rod_length_m: float = 1.0,
        launch_rod_angle_deg: float = 0.0,
        launch_altitude_m: float = 0.0,
        launch_temperature_c: float | None = None,
        wind_speed_ms: float = 0.0,
        out_dir: Path | None = None,
        openrocket_path: Path | None = None,
    ) -> Union[
        ToolSuccess[dict], ToolSuccess[list[OpenRocketFlightSummary]], ToolError
    ]:
        """
        Create, delete, or run flight configurations in an .ork or .rkt file.

        Actions:
            create: Assign a motor to a mount component, create a flight
                    configuration, and add a named flight entry. The file is
                    saved in-place and is ready to run.
            delete: Remove a named flight entry. Requires 'sim_name'.
            run:    Execute all flight configs in the file and save full
                    timeseries data as JSON.

        Motor lookup:
            motor_designation is matched against the common name (e.g. 'H128W')
            or full designation (e.g. 'H128W-14A'). Use openrocket_database with
            action='motors' to find valid designations.

        Motor mount:
            If mount_name is omitted, the first InnerTube in the rocket is used,
            falling back to the first BodyTube. To use a specific component as the
            mount, pass its name as mount_name.

        Args:
            action: 'create', 'delete', or 'run'.
            rocket_file_path: Path to the .ork or .rkt design file.
            motor_designation: Motor common name or designation (required for create).
            sim_name: Name for the flight config (create: defaults to motor designation;
                      delete: name of the flight config to remove).
            mount_name: Named component to use as motor mount (create only, optional).
            launch_rod_length_m: Launch rod length in metres (default 1.0).
            launch_rod_angle_deg: Rod angle from vertical in degrees (default 0.0).
            launch_altitude_m: Launch site altitude in metres ASL (default 0.0).
            launch_temperature_c: Launch temperature in °C. Uses ISA standard if None.
            wind_speed_ms: Average wind speed in m/s (default 0.0).
            out_dir: Optional directory to write flight JSON files. Defaults to
                     ``<project_dir>/openrocket/flights/``.
            openrocket_path: Optional path to the OpenRocket JAR file.
        """
        from rocketsmith.openrocket.simulation import (
            create_simulation,
            delete_simulation,
            run_simulation,
        )
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

            if action == "create":
                if motor_designation is None:
                    return tool_error(
                        "'motor_designation' is required for action 'create'.",
                        "MISSING_ARGUMENT",
                    )
                result = create_simulation(
                    path=rocket_file_path,
                    openrocket_path=openrocket_path,
                    motor_designation=motor_designation,
                    sim_name=sim_name,
                    mount_name=mount_name,
                    launch_rod_length_m=launch_rod_length_m,
                    launch_rod_angle_deg=launch_rod_angle_deg,
                    launch_altitude_m=launch_altitude_m,
                    launch_temperature_c=launch_temperature_c,
                    wind_speed_ms=wind_speed_ms,
                )
                return tool_success(result)

            elif action == "delete":
                if sim_name is None:
                    return tool_error(
                        "'sim_name' is required for action 'delete'.",
                        "MISSING_ARGUMENT",
                    )
                deleted = delete_simulation(
                    path=rocket_file_path,
                    openrocket_path=openrocket_path,
                    sim_name=sim_name,
                )
                return tool_success({"deleted": deleted})

            elif action == "run":
                from orhelper import FlightDataType, FlightEvent
                from rocketsmith.mcp.utils import get_project_dir
                from rocketsmith.gui.layout import FLIGHTS_DIR

                if out_dir is not None:
                    flight_dir = resolve_path(out_dir)
                else:
                    flight_dir = get_project_dir() / FLIGHTS_DIR
                flight_dir.mkdir(parents=True, exist_ok=True)

                # Config name from the .ork filename (without extension).
                config_name = rocket_file_path.stem

                simulations = run_simulation(
                    path=rocket_file_path,
                    openrocket_path=openrocket_path,
                )

                summaries = []
                for sim in simulations:
                    # Sanitize flight name for filename.
                    safe_name = (
                        sim.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
                    )
                    json_filename = f"{safe_name}.json"
                    json_path = flight_dir / json_filename

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

                    max_altitude_m = (
                        float(altitude.max()) if altitude is not None else 0.0
                    )
                    max_velocity_ms = (
                        float(velocity.max()) if velocity is not None else 0.0
                    )
                    flight_time_s = (
                        float(time_arr.max()) if time_arr is not None else 0.0
                    )

                    apogee_events = sim.events.get(FlightEvent.APOGEE)
                    time_to_apogee_s = (
                        float(apogee_events[0]) if apogee_events else None
                    )

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
                        "flight_name": sim.name,
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
                        OpenRocketFlightSummary(
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

        except ValueError as e:
            return tool_error(
                str(e),
                "INVALID_ARGUMENT",
                exception_type=type(e).__name__,
            )

        except Exception as e:
            return tool_error(
                f"Failed to {action} flight",
                "FLIGHT_FAILED",
                file_path=str(rocket_file_path),
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_flight
