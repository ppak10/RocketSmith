import numpy as np

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field
from orhelper import FlightDataType, FlightEvent
from pintdantic import QuantityModel, QuantityField


# ── Flight models ──────────────────────────────────────────────────────────────


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


# ── Component dimension models (pintdantic) ────────────────────────────────────


class NoseConeDimensions(QuantityModel):
    """Reference dimensions for a nose cone."""

    kind: Literal["nose_cone"] = "nose_cone"
    shape: str = "ogive"
    length: QuantityField = (0.0, "mm")
    base_od: QuantityField = (0.0, "mm")
    wall: QuantityField | None = None


class TubeDimensions(QuantityModel):
    """Reference dimensions for tubular components (BodyTube, InnerTube, TubeCoupler)."""

    kind: Literal["tube"] = "tube"
    length: QuantityField = (0.0, "mm")
    od: QuantityField = (0.0, "mm")
    id: QuantityField = (0.0, "mm")
    motor_mount: bool = False


class TransitionDimensions(QuantityModel):
    """Reference dimensions for a transition (conical or ogive reducer)."""

    kind: Literal["transition"] = "transition"
    shape: str = "conical"
    length: QuantityField = (0.0, "mm")
    fore_od: QuantityField = (0.0, "mm")
    aft_od: QuantityField = (0.0, "mm")
    wall: QuantityField | None = None


class FinSetDimensions(QuantityModel):
    """Reference dimensions for a fin set (trapezoid, elliptical, freeform)."""

    kind: Literal["fin_set"] = "fin_set"
    fin_type: str = "trapezoid"
    count: int = 3
    root_chord: QuantityField = (0.0, "mm")
    tip_chord: QuantityField = (0.0, "mm")
    span: QuantityField = (0.0, "mm")
    sweep: QuantityField = (0.0, "mm")
    thickness: QuantityField = (0.0, "mm")


class RingDimensions(QuantityModel):
    """Reference dimensions for centering rings and bulkheads."""

    kind: Literal["ring"] = "ring"
    od: QuantityField = (0.0, "mm")
    id: QuantityField = (0.0, "mm")
    thickness: QuantityField = (0.0, "mm")


class RecoveryDimensions(QuantityModel):
    """Reference dimensions for recovery devices (parachutes, streamers, shock cords)."""

    kind: Literal["recovery"] = "recovery"
    diameter: QuantityField | None = None
    length: QuantityField | None = None
    width: QuantityField | None = None
    packed_length: QuantityField | None = None
    packed_diameter: QuantityField | None = None


class RailButtonDimensions(QuantityModel):
    """Reference dimensions for a rail button."""

    kind: Literal["rail_button"] = "rail_button"
    outer_diameter: QuantityField = (0.0, "mm")
    inner_diameter: QuantityField = (0.0, "mm")
    height: QuantityField = (0.0, "mm")
    instance_count: int = 1
    axial_offset: QuantityField = (0.0, "mm")


class LugDimensions(QuantityModel):
    """Reference dimensions for a launch lug."""

    kind: Literal["lug"] = "lug"
    outer_diameter: QuantityField = (0.0, "mm")
    inner_diameter: QuantityField = (0.0, "mm")
    length: QuantityField = (0.0, "mm")
    axial_offset: QuantityField = (0.0, "mm")


class GenericDimensions(QuantityModel):
    """Fallback dimensions for components without a specific model."""

    kind: Literal["generic"] = "generic"
    length: QuantityField | None = None
    width: QuantityField | None = None
    height: QuantityField | None = None
    mass: QuantityField | None = None


Dimensions = Annotated[
    Union[
        NoseConeDimensions,
        TubeDimensions,
        TransitionDimensions,
        FinSetDimensions,
        RingDimensions,
        RecoveryDimensions,
        RailButtonDimensions,
        LugDimensions,
        GenericDimensions,
    ],
    Field(discriminator="kind"),
]

# Map OpenRocket type → dimension model kind
_TYPE_TO_DIMENSION_KIND: dict[str, str] = {
    "NoseCone": "nose_cone",
    "BodyTube": "tube",
    "InnerTube": "tube",
    "TubeCoupler": "tube",
    "Transition": "transition",
    "TrapezoidFinSet": "fin_set",
    "EllipticalFinSet": "fin_set",
    "FreeformFinSet": "fin_set",
    "CenteringRing": "ring",
    "BulkHead": "ring",
    "EngineBlock": "ring",
    "Parachute": "recovery",
    "Streamer": "recovery",
    "ShockCord": "recovery",
    "RailButton": "rail_button",
    "LaunchLug": "lug",
}


def dimension_kind(component_type: str) -> str:
    """Return the dimension model ``kind`` for an OpenRocket component type."""
    return _TYPE_TO_DIMENSION_KIND.get(component_type, "generic")
