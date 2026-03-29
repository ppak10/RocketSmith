import numpy as np

from pydantic import BaseModel
from orhelper import FlightDataType, FlightEvent


class OpenRocketSimulation(BaseModel):
    """Flight data from a single OpenRocket simulation run."""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    timeseries: dict[FlightDataType, np.ndarray]
    events: dict[FlightEvent, list[float]]
