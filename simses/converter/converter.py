from dataclasses import dataclass
from typing import Protocol

# TODO: add thermal propoerties


class ConverterLossModel(Protocol):
    """Protocol for AC/DC converter loss models.

    All power values are normalised to p.u. of max_power.
    Sign convention: positive = charging, negative = discharging.
    """

    def ac_to_dc(self, power_norm: float) -> float:
        """Convert normalised AC power to normalised DC power."""
        ...

    def dc_to_ac(self, power_norm: float) -> float:
        """Convert normalised DC power to normalised AC power."""
        ...


@dataclass
class ConverterState:
    """
    Dataclass representing the state of a converter.

    power_setpoint: float
        Desired power setpoint for the converter in watts (W).
    power: float
        Actual power delivered by the converter in watts (W).
    loss: float
        Power loss of the converter in watts (W).
    """

    power_setpoint: float = 0.0
    power: float = 0.0
    loss: float = 0.0


class Converter:
    """AC/DC converter that wraps a downstream component with a loss model.

    Clamps the AC power setpoint to the rated max_power, converts it to DC
    using the loss model, and forwards it to the component.  If the component
    cannot fulfill the requested DC power, the converter recalculates the
    actual AC power from the delivered DC power.

    The component can be any object with an ``update(power_setpoint, dt)``
    method and a ``state.power`` attribute — typically a Battery, but also
    another Converter (enabling converter chaining).

    Attributes:
        max_power (float): Rated maximum power of the converter in W.
        state (ConverterState): Current converter state (power, setpoint, loss).
        model (ConverterLossModel): Loss model for AC/DC conversion.
        component: Downstream component receiving the DC power setpoint.

    Methods:
        update(power_setpoint, dt): Apply a power setpoint over a timestep.
    """

    def __init__(self, loss_model: ConverterLossModel, max_power: float, component) -> None:
        self.max_power = max_power
        self.state = ConverterState()
        self.model = loss_model
        self.component = component

    def update(self, power_setpoint, dt):
        max_power = self.max_power
        power_ac = max(-max_power, min(power_setpoint, max_power))
        power_dc = self.ac_to_dc(power_ac)

        self.component.update(power_dc, dt)
        power_storage = self.component.state.power

        # check if subsystem fullfilled DC power
        # if not, re-calculate required AC power
        if power_dc != 0 and (abs(power_dc - power_storage) / abs(power_dc)) > 0.01:  # 1% difference tolerance
            power_dc = power_storage
            power_ac = self.dc_to_ac(power_dc)

        # calculate conversion losses
        loss = power_ac - power_dc

        # update state
        self.state.power_setpoint = power_setpoint
        self.state.power = power_ac
        self.state.loss = loss

    def dc_to_ac(self, power_dc):
        max_power = self.max_power
        return self.model.dc_to_ac(power_dc / max_power) * max_power

    def ac_to_dc(self, power_ac):
        max_power = self.max_power
        return self.model.ac_to_dc(power_ac / max_power) * max_power
