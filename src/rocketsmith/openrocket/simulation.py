from pathlib import Path

from rocketsmith.openrocket.models import OpenRocketSimulation
from rocketsmith.openrocket.utils import get_openrocket_jvm


def run_simulation(
    ork_path: Path,
    openrocket_path: Path,
) -> list[OpenRocketSimulation]:
    """
    Load an .ork file and run all simulations defined within it.

    Args:
        ork_path: Path to the OpenRocket .ork design file.
        openrocket_path: Path to the OpenRocket JAR file.

    Returns:
        List of OpenRocketSimulation, one per simulation in the .ork file.
    """
    import orhelper
    from orhelper import FlightDataType, FlightEvent

    results = []

    jvm = get_openrocket_jvm(openrocket_path)
    if jvm:
        import os
        # JAVA_HOME must point to the JRE home (three levels up from libjvm.dylib)
        # e.g. .../jre.bundle/Contents/Home/lib/server/libjvm.dylib -> .../Home
        os.environ["JAVA_HOME"] = str(jvm.parent.parent.parent)

    with orhelper.OpenRocketInstance(str(openrocket_path), log_level="ERROR") as instance:
        helper = orhelper.Helper(instance)
        doc = helper.load_doc(str(ork_path))

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

            results.append(OpenRocketSimulation(
                name=str(sim.getName()),
                timeseries=helper.get_timeseries(sim, valid_types),
                events=helper.get_events(sim),
            ))

    return results
