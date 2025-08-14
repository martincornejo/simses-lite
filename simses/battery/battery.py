import math

from simses.battery.cell import CellType
from simses.battery.state import BatteryState


class Battery:
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

        return i

    ## electrical properties
    def open_circuit_voltage(self, state):
        (serial, parallel) = self.circuit

        return self.cell.open_circuit_voltage(state) * serial

    def hystheresis_voltage(self, state):
        (serial, parallel) = self.circuit

        return self.cell.hystheresis_voltage(state) * serial

    def internal_resistance(self, state):
        (serial, parallel) = self.circuit

        # state.i = state.i / parallel # <- should be scaled to the cell
        return self.cell.internal_resistance(state) / parallel * serial * state.soh_R

    def capacity(self, state):
        return self.nominal_capacity * state.soh_Q

    def energy_capacity(self, state):
        return self.nominal_energy_capacity * state.soh_Q

    @property
    def nominal_capacity(self) -> float:
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_capacity * parallel

    @property
    def nominal_voltage(self) -> float:
        # TODO: is this required?
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_voltage * serial

    @property
    def nominal_energy_capacity(self) -> float:
        return self.nominal_capacity * self.nominal_voltage

    @property
    def min_voltage(self) -> float:
        (serial, parallel) = self.circuit

        return self.cell.electrical.min_voltage * serial

    @property
    def max_voltage(self) -> float:
        (serial, parallel) = self.circuit

        return self.cell.electrical.max_voltage * serial

    @property
    def max_charge_current(self) -> float:
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_capacity * self.cell.electrical.max_discharge_rate * parallel

    @property
    def max_discharge_current(self) -> float:
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_capacity * self.cell.electrical.max_discharge_rate * parallel

    @property
    def coulomb_efficiency(self) -> float:
        return self.cell.electrical.coulomb_efficiency

    ## thermal properties
    @property
    def specific_heat(self) -> float:
        (serial, parallel) = self.circuit

        return self.cell.thermal.specific_heat * self.cell.thermal.mass * serial * parallel

    @property
    def convection_coefficient(self) -> float:
        return self.cell.thermal.convection_coefficient

    @property
    def min_temperature(self) -> float:
        return self.cell.thermal.min_temperature

    @property
    def max_temperature(self) -> float:
        return self.cell.thermal.max_temperature

    ## cell format
    @property
    def volume(self) -> float:
        # TODO: is this required?
        (serial, parallel) = self.circuit

        return self.cell.format.volume * serial * parallel

    @property
    def area(self) -> float:
        # TODO: is this required?
        (serial, parallel) = self.circuit

        return self.cell.format.area * serial * parallel
