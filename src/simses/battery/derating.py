from typing import Protocol

from simses.battery.state import BatteryState


class CurrentDerating(Protocol):
    """Protocol for current derating strategies.

    A derating function receives the candidate current (already clamped to hard
    limits) and the current battery state, and returns a (possibly reduced) current.

    Sign convention:
    - If i > 0 (charging), return a value in [0, i]
    - If i < 0 (discharging), return a value in [i, 0]
    - If i == 0, return 0
    """

    def derate(self, i: float, state: BatteryState) -> float:
        """Return the derated current."""
        ...


class LinearVoltageDerating:
    """Linearly reduce current when terminal voltage enters the derating zone.

    Charge:    ramp from full current at charge_start_voltage down to 0 at max_voltage.
    Discharge: ramp from full current at discharge_start_voltage down to 0 at min_voltage.

    All voltage values must be at the system level (cell voltage * serial count).
    """

    def __init__(
        self,
        max_voltage: float,
        min_voltage: float,
        charge_start_voltage: float | None = None,
        discharge_start_voltage: float | None = None,
    ) -> None:
        self.max_voltage = max_voltage
        self.min_voltage = min_voltage
        self.charge_start_voltage = charge_start_voltage
        self.discharge_start_voltage = discharge_start_voltage

    @classmethod
    def from_cell(cls, cell, serial: int) -> "LinearVoltageDerating | None":
        """Build from cell electrical properties, scaling voltages to system level.

        Returns None if neither derating threshold is configured on the cell.
        """
        e = cell.electrical
        if e.charge_derate_voltage_start is None and e.discharge_derate_voltage_start is None:
            return None
        return cls(
            max_voltage=e.max_voltage * serial,
            min_voltage=e.min_voltage * serial,
            charge_start_voltage=e.charge_derate_voltage_start * serial
            if e.charge_derate_voltage_start is not None
            else None,
            discharge_start_voltage=e.discharge_derate_voltage_start * serial
            if e.discharge_derate_voltage_start is not None
            else None,
        )

    def derate(self, i: float, state: BatteryState) -> float:
        """Return the current scaled down if the derating zone is active.

        The terminal voltage is computed from the incoming current and the
        state's OCV / hysteresis / Rint, then:

        * Charge (``i > 0``): full current below ``charge_start_voltage``,
          zero at ``max_voltage``, linear in between.
        * Discharge (``i < 0``): full current above
          ``discharge_start_voltage``, zero at ``min_voltage``, linear in
          between.

        If the corresponding start voltage is ``None``, no derating is
        applied for that direction.

        Args:
            i: Candidate current in A (already clamped to hard limits).
            state: Current battery state.

        Returns:
            Derated current in A (same sign as ``i``, magnitude ≤ ``|i|``).
        """
        if i == 0.0:
            return i

        v = state.ocv + state.hys + state.rint * i

        if i > 0:  # charge
            dv = self.charge_start_voltage
            if dv is None or v <= dv:
                return i
            if v >= self.max_voltage:
                return 0.0
            return i * (self.max_voltage - v) / (self.max_voltage - dv)

        else:  # discharge
            dv = self.discharge_start_voltage
            if dv is None or v >= dv:
                return i
            if v <= self.min_voltage:
                return 0.0
            return i * (v - self.min_voltage) / (dv - self.min_voltage)


class LinearThermalDerating:
    """Linearly reduce current when temperature enters the derating zone.

    Between T_start and T_max, current is scaled linearly from 100% down to 0%.
    Below T_start: no derating. At or above T_max: current is forced to 0.

    All temperatures must be in °C. Separate thresholds can be configured for
    charge and discharge; if omitted, discharge reuses the charge thresholds.
    """

    def __init__(
        self,
        charge_T_start: float,
        charge_T_max: float,
        discharge_T_start: float | None = None,
        discharge_T_max: float | None = None,
    ) -> None:
        self.charge_T_start = charge_T_start
        self.charge_T_max = charge_T_max
        self.discharge_T_start = discharge_T_start if discharge_T_start is not None else charge_T_start
        self.discharge_T_max = discharge_T_max if discharge_T_max is not None else charge_T_max

    def derate(self, i: float, state: BatteryState) -> float:
        """Return the current scaled down if the temperature derating zone is active.

        Below the start temperature no derating is applied; between start
        and max the current is scaled linearly from 100% down to 0%; at or
        above the max temperature the current is forced to 0.

        Args:
            i: Candidate current in A (already clamped to hard limits).
            state: Current battery state (reads ``T``).

        Returns:
            Derated current in A (same sign as ``i``, magnitude ≤ ``|i|``).
        """
        if i == 0.0:
            return i

        T = state.T

        if i > 0:  # charge
            if T <= self.charge_T_start:
                return i
            if T >= self.charge_T_max:
                return 0.0
            return i * (self.charge_T_max - T) / (self.charge_T_max - self.charge_T_start)

        else:  # discharge
            if T <= self.discharge_T_start:
                return i
            if T >= self.discharge_T_max:
                return 0.0
            return i * (self.discharge_T_max - T) / (self.discharge_T_max - self.discharge_T_start)


class DeratingChain:
    """Applies multiple derating strategies in sequence.

    Each strategy receives the output of the previous one. Since each step can
    only reduce |i|, the most restrictive combination wins naturally. The chain
    short-circuits when i reaches 0.

    DeratingChain itself satisfies the CurrentDerating protocol and can be nested.
    """

    def __init__(self, strategies: list) -> None:
        self._strategies = list(strategies)

    def derate(self, i: float, state: BatteryState) -> float:
        """Apply each strategy in sequence, short-circuiting at zero.

        Args:
            i: Candidate current in A.
            state: Current battery state.

        Returns:
            Current after all strategies have been applied in order.
        """
        for strategy in self._strategies:
            i = strategy.derate(i, state)
            if i == 0.0:
                break
        return i
