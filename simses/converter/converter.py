from dataclasses import dataclass

# TODO: add thermal propoerties


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
    """AC/DC converter that wraps a storage system with a loss model.

    Clamps the AC power setpoint to the rated max_power, converts it to DC
    using the loss model, and forwards it to the underlying storage.  If the
    storage cannot fulfill the requested DC power, the converter recalculates
    the actual AC power from the delivered DC power.

    Attributes:
        max_power (float): Rated maximum power of the converter in W.
        state (ConverterState): Current converter state (power, setpoint, loss).
        model: Loss model providing ac_to_dc and dc_to_ac conversion methods.
        storage: Underlying storage system (e.g. Battery) with an update method.

    Methods:
        update(power_setpoint, dt): Apply a power setpoint over a timestep.
    """

    def __init__(self, loss_model, max_power, storage) -> None:
        self.max_power = max_power
        self.state = ConverterState()
        self.model = loss_model
        self.storage = storage

    def update(self, power_setpoint, dt):
        max_power = self.max_power
        power_ac = max(-max_power, min(power_setpoint, max_power))
        power_dc = self.ac_to_dc(power_ac)

        self.storage.update(power_dc, dt)
        power_storage = self.storage.state.power

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
