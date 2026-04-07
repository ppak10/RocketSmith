from pathlib import Path

from rocketsmith.openrocket.models import OpenRocketSimulation


def _find_motor_mount(rocket, mount_name: str | None):
    """Walk the component tree and return the first MotorMount component.

    If mount_name is given, find that specific component and verify it can be
    a motor mount. Otherwise return the first InnerTube found, or fall back to
    the first BodyTube in the first stage.
    """
    import jpype

    MotorMount = jpype.JPackage("net").sf.openrocket.rocketcomponent.MotorMount

    def _walk(comp):
        yield comp
        for i in range(comp.getChildCount()):
            yield from _walk(comp.getChild(i))

    if mount_name:
        for comp in _walk(rocket):
            if str(comp.getName()) == mount_name:
                if MotorMount.class_.isInstance(comp):
                    return comp
                raise ValueError(
                    f"Component '{mount_name}' is not a motor mount. "
                    "Use an inner-tube or body-tube component."
                )
        raise ValueError(f"Component '{mount_name}' not found.")

    # Prefer InnerTube (explicit motor mount tube)
    for comp in _walk(rocket):
        type_name = str(comp.getClass().getSimpleName())
        if type_name == "InnerTube":
            return comp

    # Fall back to first BodyTube
    for comp in _walk(rocket):
        type_name = str(comp.getClass().getSimpleName())
        if type_name == "BodyTube":
            return comp

    raise ValueError(
        "No motor mount found. Add an inner-tube component to the rocket first."
    )


def _find_motor_by_designation(designation: str):
    """Search the ThrustCurveMotorSetDatabase for a motor matching the designation.

    Matches against common_name (e.g. 'H128W') and full designation (e.g. 'H128W-14A').
    Returns the first (primary) ThrustCurveMotor variant.
    Raises ValueError if no match found.
    """
    import jpype

    Application = jpype.JPackage("net").sf.openrocket.startup.Application
    motor_sets = Application.getThrustCurveMotorSetDatabase().getMotorSets()

    designation_lower = designation.lower().replace("-", "")

    for i in range(motor_sets.size()):
        ms = motor_sets.get(i)
        common = str(ms.getCommonName()).lower().replace("-", "")
        full = str(ms.getDesignation()).lower().replace("-", "")
        if designation_lower == common or designation_lower == full:
            return ms.getMotors().get(0)

    raise ValueError(
        f"Motor '{designation}' not found. "
        "Use openrocket_database(action='motors') to find valid designations."
    )


def create_simulation(
    path: Path,
    openrocket_path: Path,
    motor_designation: str,
    sim_name: str | None = None,
    mount_name: str | None = None,
    launch_rod_length_m: float = 1.0,
    launch_rod_angle_deg: float = 0.0,
    launch_altitude_m: float = 0.0,
    launch_temperature_c: float | None = None,
    wind_speed_ms: float = 0.0,
) -> dict:
    """Add a new simulation to an .ork or .rkt file with a motor assignment.

    Finds or creates a flight configuration, assigns the given motor to the
    best available motor mount, creates a Simulation entry, and saves the file.

    Args:
        path: Path to the .ork or .rkt design file (modified in-place).
        openrocket_path: Path to the OpenRocket JAR.
        motor_designation: Motor common name or designation (e.g. 'H128W', 'D12').
        sim_name: Name for the new simulation entry. Defaults to the motor designation.
        mount_name: Named component to use as motor mount. Auto-detected if omitted.
        launch_rod_length_m: Launch rod length in metres (default 1.0).
        launch_rod_angle_deg: Rod angle from vertical in degrees (default 0.0).
        launch_altitude_m: Launch site altitude in metres ASL (default 0.0).
        launch_temperature_c: Launch temperature in °C. Uses ISA standard if None.
        wind_speed_ms: Average wind speed in m/s (default 0.0).

    Returns:
        Dict with simulation name, motor info, and mount component name.
    """
    import jpype
    import orhelper
    import math
    from rocketsmith.openrocket.components import _or_context, _save_doc

    OR = jpype.JPackage("net").sf.openrocket

    with _or_context(openrocket_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(path))
        rocket = doc.getRocket()

        motor = _find_motor_by_designation(motor_designation)
        mount = _find_motor_mount(rocket, mount_name)

        # Enable motor mounting on the component (required for BodyTube, no-op for InnerTube)
        try:
            mount.setMotorMount(True)
        except Exception:
            pass

        # Create a new flight configuration
        FlightConfigurationId = OR.rocketcomponent.FlightConfigurationId
        MotorConfiguration = OR.motor.MotorConfiguration

        fcid = FlightConfigurationId()
        rocket.createFlightConfiguration(fcid)

        # Assign motor to mount under this flight config
        motor_config = MotorConfiguration(mount, fcid)
        motor_config.setMotor(motor)
        mount.setMotorConfig(motor_config, fcid)

        # Create simulation  (constructor is (OpenRocketDocument, Rocket))
        Simulation = OR.document.Simulation
        sim = Simulation(doc, rocket)
        name = sim_name or motor_designation
        sim.setName(name)
        sim.setFlightConfigurationId(fcid)

        opts = sim.getOptions()
        opts.setLaunchRodLength(float(launch_rod_length_m))
        opts.setLaunchRodAngle(math.radians(float(launch_rod_angle_deg)))
        opts.setLaunchAltitude(float(launch_altitude_m))
        opts.setWindSpeedAverage(float(wind_speed_ms))
        if launch_temperature_c is not None:
            opts.setLaunchTemperature(float(launch_temperature_c + 273.15))
            opts.setISAAtmosphere(False)

        doc.addSimulation(sim)
        _save_doc(doc, path)

    return {
        "simulation_name": name,
        "motor_designation": motor_designation,
        "mount_component": str(mount.getName()),
        "launch_rod_length_m": launch_rod_length_m,
        "launch_rod_angle_deg": launch_rod_angle_deg,
        "launch_altitude_m": launch_altitude_m,
        "wind_speed_ms": wind_speed_ms,
    }


def delete_simulation(path: Path, openrocket_path: Path, sim_name: str) -> str:
    """Remove a named simulation from an .ork or .rkt file and save in-place."""
    import orhelper
    from rocketsmith.openrocket.components import _or_context, _save_doc

    with _or_context(openrocket_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(path))
        sims = doc.getSimulations()

        for i in range(sims.size()):
            sim = sims.get(i)
            if str(sim.getName()) == sim_name:
                doc.removeSimulation(i)
                _save_doc(doc, path)
                return sim_name

    raise ValueError(f"Simulation '{sim_name}' not found.")


def run_simulation(
    path: Path,
    openrocket_path: Path,
) -> list[OpenRocketSimulation]:
    """
    Load an .ork or .rkt file and run all simulations defined within it.

    Args:
        path: Path to the OpenRocket .ork or RockSim .rkt design file.
        openrocket_path: Path to the OpenRocket JAR file.

    Returns:
        List of OpenRocketSimulation, one per simulation in the file.
    """
    import orhelper
    from orhelper import FlightDataType, FlightEvent
    from rocketsmith.openrocket.components import _or_context

    results = []

    with _or_context(openrocket_path) as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(path))

        # Filter to FlightDataType members that exist in the installed OpenRocket JAR.
        # orhelper's Python enum may include entries added in later OpenRocket versions.
        valid_types = []
        for t in FlightDataType:
            try:
                helper.translate_flight_data_type(t)
                valid_types.append(t)
            except AttributeError:
                pass

        sims = doc.getSimulations()
        for i in range(sims.size()):
            sim = sims.get(i)
            helper.run_simulation(sim)

            # Extract stability directly from FlightData (more reliable than timeseries)
            max_stability_cal = None
            min_stability_cal = None
            try:
                import math

                flight_data = sim.getSimulatedData()
                if flight_data is not None:
                    max_val = float(flight_data.getMaxStabilityMargin())
                    min_val = float(flight_data.getMinStabilityMargin())
                    if not math.isnan(max_val):
                        max_stability_cal = max_val
                    if not math.isnan(min_val):
                        min_stability_cal = min_val
            except Exception:
                pass

            results.append(
                OpenRocketSimulation(
                    name=str(sim.getName()),
                    timeseries=helper.get_timeseries(sim, valid_types),
                    events=helper.get_events(sim),
                    max_stability_cal=max_stability_cal,
                    min_stability_cal=min_stability_cal,
                )
            )

    return results
