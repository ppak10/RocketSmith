from mcp.server.fastmcp import FastMCP


def register_openrocket_flight(app: FastMCP):
    from pathlib import Path
    from typing import Literal, Union

    from rocketsmith.mcp.types import ToolSuccess, ToolError
    from rocketsmith.mcp.utils import tool_success, tool_error

    @app.tool(
        title="OpenRocket Flight",
        description=(
            "Create or delete a simulation entry in an OpenRocket .ork file. "
            "Use 'create' to assign a motor to a mount and add a simulation ready to run. "
            "Use 'delete' to remove a simulation by name. "
            "Run simulations with the openrocket_simulate tool after creating them."
        ),
        structured_output=True,
    )
    async def openrocket_flight(
        action: Literal["create", "delete"],
        ork_path: Path,
        motor_designation: str | None = None,
        sim_name: str | None = None,
        mount_name: str | None = None,
        launch_rod_length_m: float = 1.0,
        launch_rod_angle_deg: float = 0.0,
        launch_altitude_m: float = 0.0,
        launch_temperature_c: float | None = None,
        wind_speed_ms: float = 0.0,
        openrocket_path: Path | None = None,
    ) -> Union[ToolSuccess[dict], ToolError]:
        """
        Create or delete a simulation entry in an .ork file.

        Actions:
            create: Assign a motor to a mount component, create a flight
                    configuration, and add a named simulation. The file is
                    saved in-place and is ready to pass to openrocket_simulate.
            delete: Remove a named simulation. Requires 'sim_name'.

        Motor lookup:
            motor_designation is matched against the common name (e.g. 'H128W')
            or full designation (e.g. 'H128W-14A'). Use openrocket_database with
            action='motors' to find valid designations.

        Motor mount:
            If mount_name is omitted, the first InnerTube in the rocket is used,
            falling back to the first BodyTube. To use a specific component as the
            mount, pass its name as mount_name.

        Args:
            action: 'create' or 'delete'.
            ork_path: Path to the OpenRocket .ork design file.
            motor_designation: Motor common name or designation (required for create).
            sim_name: Name for the simulation (create: defaults to motor designation;
                      delete: name of the simulation to remove).
            mount_name: Named component to use as motor mount (create only, optional).
            launch_rod_length_m: Launch rod length in metres (default 1.0).
            launch_rod_angle_deg: Rod angle from vertical in degrees (default 0.0).
            launch_altitude_m: Launch site altitude in metres ASL (default 0.0).
            launch_temperature_c: Launch temperature in °C. Uses ISA standard if None.
            wind_speed_ms: Average wind speed in m/s (default 0.0).
            openrocket_path: Optional path to the OpenRocket JAR file.
        """
        from rocketsmith.openrocket.simulation import create_simulation, delete_simulation
        from rocketsmith.openrocket.utils import get_openrocket_path

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
                    ork_path=ork_path,
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
                    ork_path=ork_path,
                    openrocket_path=openrocket_path,
                    sim_name=sim_name,
                )
                return tool_success({"deleted": deleted})

        except FileNotFoundError as e:
            return tool_error(
                str(e),
                "FILE_NOT_FOUND",
                ork_path=str(ork_path),
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
                f"Failed to {action} simulation",
                "SIMULATION_FAILED",
                ork_path=str(ork_path),
                action=action,
                exception_type=type(e).__name__,
                exception_message=str(e),
            )

    _ = openrocket_flight
