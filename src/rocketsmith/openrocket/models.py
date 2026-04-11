import numpy as np

from pydantic import BaseModel
from orhelper import FlightDataType, FlightEvent


class OpenRocketFlight(BaseModel):
    """Flight data from a single OpenRocket flight run."""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    timeseries: dict[FlightDataType, np.ndarray]
    events: dict[FlightEvent, list[float]]
    max_stability_cal: float | None = None
    min_stability_cal: float | None = None


class OpenRocketFlightSummary(BaseModel):
    """JSON-serializable summary of a single OpenRocket flight, for MCP output."""

    name: str
    max_altitude_m: float
    max_velocity_ms: float
    time_to_apogee_s: float | None
    flight_time_s: float
    min_stability_cal: float | None
    max_stability_cal: float | None
    timeseries_path: str | None = None
