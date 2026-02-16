import math

from simses.battery.cell import CellType
from simses.battery.state import BatteryState


class Battery:
    """Battery system composed of cells in a series-parallel circuit."""

    def __init__(
        self,
        cell: CellType,
        circuit: tuple[int, int],  # (s, p)
        initial_states: dict,
        soc_limits: tuple[float, float] = (0.0, 1.0),  # in p.u.
    ) -> None:
        self.cell = cell
        self.circuit = circuit
        self.soc_limits = soc_limits
        self.state = self.initialize_state(**initial_states)

    def initialize_state(
        self, start_soc: float, start_T: float, start_soh_Q: float = 1.0, start_soh_R: float = 1.0
    ) -> BatteryState:
        """Create the initial battery state from starting conditions."""
        state = BatteryState(
            v=0,  # uninitialized
            i=0,  # uninitialized
            T=start_T,
            power=0,
            power_setpoint=0,
            loss=0,
            soc=start_soc,
            ocv=0,  # uninitialized
            hys=0,  # uninitialized
            is_charge=True,
            rint=0,  # uninitialized
            soh_Q=start_soh_Q,
            soh_R=start_soh_R,
        )
        state.ocv = state.v = self.open_circuit_voltage(state)
        state.hys = self.hystheresis_voltage(state)
        state.rint = self.internal_resistance(state)
        return state

    def update(self, power_setpoint, dt) -> None:
        """
        Input
            state: BatteryState
            power_sentpoint: float
                Input power target in W
            dt: float
                Timestep in s
        """
        state: BatteryState = self.state
        # update state
        state.is_charge = power_setpoint > 0.0

        # update soc, ocv and rint based on previous state
        ocv = self.open_circuit_voltage(state)
        hys = self.hystheresis_voltage(state)
        rint = self.internal_resistance(state)
        Q = self.capacity(state)

        i = self.equilibrium_current(state, power_setpoint, dt)  # TODO: improve?

        # update soc
        (soc_min, soc_max) = self.soc_limits
        soc = state.soc + i * dt / Q / 3600
        soc = max(soc_min, min(soc, soc_max))

        # check current direction, maintain previous state if in rest
        is_charge = state.is_charge if i == 0 else i > 0

        # update terminal voltage and power
        v = ocv + hys + rint * i
        power = v * i

        # update losses
        rint_loss = rint * i**2
        # hys_loss = abs(ocv - hys) * i # ?
        # reversible loss ?

        # update state
        self.state.v = v
        self.state.i = i
        self.state.power = power
        self.state.power_setpoint = power_setpoint
        self.state.loss = rint_loss
        self.state.soc = soc
        self.state.ocv = ocv
        self.state.hys = hys
        self.state.rint = rint
        self.state.is_charge = is_charge

    def equilibrium_current(self, state: BatteryState, power_setpoint: float, dt: float) -> float:
        """
        Calculates the battery current that fullfils the power setpoint and curtails it if above the allowed technical limits (de-rating).

        The equilibrium current is calculated based on the equivalent circuit model
        p = i * v
          = i * (ocv - r * i)

        The maximum current is based on the cell charge/discharge C-rate limits, cell voltage limits, and specified SOC limits.
        """

        if power_setpoint == 0.0:
            return 0.0  # i = 0

        # battery state
        (soc_min, soc_max) = self.soc_limits
        soc = state.soc
        ocv = self.open_circuit_voltage(state)
        hys = self.hystheresis_voltage(state)
        rint = self.internal_resistance(state)
        Q = self.capacity(state)

        # calculate current to fullfil power by solving the quadratic equation (-b +/- sqrt(b^2 - 4 * a * c)) / (2 * a)
        # only one of the roots is feasible
        # p = i * v
        #   = i * (ocv - r * i) <- find i
        i = -(ocv - math.sqrt(ocv**2 + 4 * rint * power_setpoint)) / (2 * rint)

        # check current limits / voltage limits / soc limits
        if i == 0:  # rest
            i = 0.0

        elif i > 0:  # charge
            # current limits
            i_max_i_lim = self.max_charge_current

            # voltage limits
            delta_v_max = self.max_voltage - ocv - hys
            i_max_v_lim = delta_v_max / rint

            # soc limits
            delta_soc_max = soc_max - soc
            i_max_soc_lim = delta_soc_max * Q / (dt / 3600)

            # limits
            i = min(i, i_max_i_lim, i_max_v_lim, i_max_soc_lim)

        else:  # discharge
            # current limits
            i_max_i_lim = -self.max_discharge_current

            # voltage limits
            delta_v_max = self.min_voltage - ocv - hys
            i_max_v_lim = delta_v_max / rint

            # soc_limits
            delta_soc_max = soc_min - soc
            i_max_soc_lim = delta_soc_max * Q / (dt / 3600)

            # limit
            i = max(i, i_max_i_lim, i_max_v_lim, i_max_soc_lim)

        # optional voltage derating based on terminal voltage
        i = self._apply_linear_voltage_derating(i, ocv, hys, rint)

        return i

    def _apply_linear_voltage_derating(self, i: float, ocv: float, hys: float, rint: float) -> float:
        """Reduce current if the terminal voltage is in the derating zone.

        After all other limits have been applied, the terminal voltage is
        computed as v_terminal = ocv + hys + rint * i.  If it falls inside
        the derating region the current is scaled down linearly:

        Charge  (i > 0): between charge_derate_voltage_start and max_voltage
        Discharge (i < 0): between discharge_derate_voltage_start and min_voltage
        """
        if i == 0.0:
            return i

        v = ocv + hys + rint * i

        if i > 0:  # charge
            derate_v = self.charge_derate_voltage_start
            if derate_v is None:
                return i
            if v <= derate_v:
                return i  # below derating zone
            if v >= self.max_voltage:
                return 0.0
            factor = (self.max_voltage - v) / (self.max_voltage - derate_v)
            return i * factor

        else:  # discharge
            derate_v = self.discharge_derate_voltage_start
            if derate_v is None:
                return i
            if v >= derate_v:
                return i  # above derating zone
            if v <= self.min_voltage:
                return 0.0
            factor = (v - self.min_voltage) / (derate_v - self.min_voltage)
            return i * factor

    ## electrical properties
    def open_circuit_voltage(self, state):
        """Return the system-level open-circuit voltage in V."""
        (serial, parallel) = self.circuit

        return self.cell.open_circuit_voltage(state) * serial

    def hystheresis_voltage(self, state):
        """Return the system-level hysteresis voltage in V."""
        (serial, parallel) = self.circuit

        return self.cell.hystheresis_voltage(state) * serial

    def internal_resistance(self, state):
        """Return the system-level internal resistance in Ohms, scaled by SoH."""
        (serial, parallel) = self.circuit

        # state.i = state.i / parallel # <- should be scaled to the cell
        return self.cell.internal_resistance(state) / parallel * serial * state.soh_R

    def capacity(self, state):
        """Return the current capacity in Ah, scaled by SoH."""
        return self.nominal_capacity * state.soh_Q

    def energy_capacity(self, state):
        """Return the current energy capacity in Wh, scaled by SoH."""
        return self.nominal_energy_capacity * state.soh_Q

    @property
    def nominal_capacity(self) -> float:
        """Nominal capacity of the battery system in Ah."""
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_capacity * parallel

    @property
    def nominal_voltage(self) -> float:
        """Nominal voltage of the battery system in V."""
        # TODO: is this required?
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_voltage * serial

    @property
    def nominal_energy_capacity(self) -> float:
        """Nominal energy capacity of the battery system in Wh."""
        return self.nominal_capacity * self.nominal_voltage

    @property
    def min_voltage(self) -> float:
        """Minimum allowed voltage of the battery system in V."""
        (serial, parallel) = self.circuit

        return self.cell.electrical.min_voltage * serial

    @property
    def max_voltage(self) -> float:
        """Maximum allowed voltage of the battery system in V."""
        (serial, parallel) = self.circuit

        return self.cell.electrical.max_voltage * serial

    @property
    def charge_derate_voltage_start(self) -> float | None:
        """System-level voltage at which charge derating begins, or None if disabled."""
        v = self.cell.electrical.charge_derate_voltage_start
        if v is None:
            return None
        (serial, parallel) = self.circuit
        return v * serial

    @property
    def discharge_derate_voltage_start(self) -> float | None:
        """System-level voltage at which discharge derating begins, or None if disabled."""
        v = self.cell.electrical.discharge_derate_voltage_start
        if v is None:
            return None
        (serial, parallel) = self.circuit
        return v * serial

    @property
    def max_charge_current(self) -> float:
        """Maximum allowed charge current in A."""
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_capacity * self.cell.electrical.max_discharge_rate * parallel

    @property
    def max_discharge_current(self) -> float:
        """Maximum allowed discharge current in A."""
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_capacity * self.cell.electrical.max_discharge_rate * parallel

    @property
    def coulomb_efficiency(self) -> float:
        """Coulomb efficiency of the cell in p.u."""
        return self.cell.electrical.coulomb_efficiency

    ## thermal properties
    @property
    def specific_heat(self) -> float:
        """Total thermal capacity of the battery system in J/K."""
        (serial, parallel) = self.circuit

        return self.cell.thermal.specific_heat * self.cell.thermal.mass * serial * parallel

    @property
    def convection_coefficient(self) -> float:
        """Convection coefficient of the cell in W/m2K."""
        return self.cell.thermal.convection_coefficient

    @property
    def min_temperature(self) -> float:
        """Minimum allowed temperature in K."""
        return self.cell.thermal.min_temperature

    @property
    def max_temperature(self) -> float:
        """Maximum allowed temperature in K."""
        return self.cell.thermal.max_temperature

    ## cell format
    @property
    def volume(self) -> float:
        """Total volume of all cells in m3."""
        # TODO: is this required?
        (serial, parallel) = self.circuit

        return self.cell.format.volume * serial * parallel

    @property
    def area(self) -> float:
        """Total surface area of all cells in m2."""
        # TODO: is this required?
        (serial, parallel) = self.circuit

        return self.cell.format.area * serial * parallel
