"""Structural protocols shared across all thermal models."""

from typing import Protocol


class ThermalComponentState(Protocol):
    """State interface that thermal component nodes must expose."""

    T: float
    heat: float


class ThermalComponent(Protocol):
    """Protocol for objects that can be registered as thermal nodes.

    Satisfying this protocol does not require explicit inheritance — any
    object with these attributes qualifies (structural subtyping).

    Attributes:
        state:              Mutable state object exposing ``T`` (temperature in K,
                            read/written) and ``heat`` (heat generation in W, read).
        thermal_capacity:   Thermal capacity in J/K.
        thermal_resistance: Thermal resistance to the thermal environment in K/W.
    """

    state: ThermalComponentState
    thermal_capacity: float
    thermal_resistance: float
