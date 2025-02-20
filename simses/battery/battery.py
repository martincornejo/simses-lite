import math
from dataclasses import dataclass

from simses.battery.cell import CellType


@dataclass(slots=True)
class BatteryState:
    v: float  # V
    i: float  # A
    T: float  # K
    power: float  # W
    power_setpoint: float  # W
    soc: float  # p.u.
    ocv: float  # V
    hys: float  # V
    rint: float  # ohm
    soh_Q: float  # p.u.
    soh_R: float  # p.u.
    is_charge: bool
    loss: float  # in W
    # reversible heat


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
        state.rint = self.internal_resistance(state) * start_soh_R
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

        # update soc, ocv and rint based on previous state
        soc = state.soc + state.i * dt / (self.nominal_capacity * state.soh_Q) / 3600
        ocv = self.open_circuit_voltage(state)
        hys = self.hystheresis_voltage(state)
        rint = self.internal_resistance(state) * state.soh_R
        Q = state.soh_Q * self.nominal_capacity

        # update degradation based on previous state
        soh_Q = state.soh_Q  # self.cell.capacity_loss(state)
        # soh_R = state.soh_R  # self.cell.resistance_increase(state)

        # calculate current to fullfil power by solving the quadratic equation (-b +/- sqrt(b^2 - 4 * a * c)) / (2 * a)
        # only one of the roots is feasible
        # p = i * v
        #   = i * (ocv - r * i) <- find i
        i = -(ocv - math.sqrt(ocv**2 + 4 * rint * power_setpoint)) / (2 * rint)

        # check current limits / voltage limits / soc limits
        i = self._get_maximum_current(i, dt, soc, ocv, hys, rint, Q, soh_Q)  # TODO: improve?

        # check current direction, maintain previous state if in rest
        is_charge = state.is_charge if i == 0 else i > 0

        # update terminal voltage and power
        v = ocv + hys + rint * i
        power = v * i

        # update losses
        rint_loss = rint * i**2
        # hys_loss = abs(ocv - hys) * i # ?
        # reversible loss ?

        # update temperature
        # T = state.T

        # update state
        self.state.v = v
        self.state.i = i
        self.state.power = power
        self.state.power_setpoint = power_setpoint
        self.state.loss = rint_loss
        self.state.soc = soc
        self.state.ocv = ocv
        # self.state.hys = hys
        self.state.rint = rint
        # self.state.soh_Q = soh_Q
        # self.state.soh_R = soh_R
        self.state.is_charge = is_charge
        # return state
        # return BatteryState(v, i, T, power, power_setpoint, soc, ocv, hys, rint, soh_Q, soh_R, is_charge)

    def _get_maximum_current(self, i, dt, soc, ocv, hys, rint, Q, soh_Q) -> float:
        (soc_min, soc_max) = self.soc_limits

        if i == 0:  # rest
            i_max = 0.0

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
            i_max = min(i, i_max_i_lim, i_max_v_lim, i_max_soc_lim)

        else:  # discharge
            # current limits
            i_max_i_lim = -self.max_discharge_current

            # voltage limits
            delta_v_max = self.min_voltage - ocv - hys
            i_max_v_lim = delta_v_max / rint

            # soc_limits
            delta_soc_max = soc_min - soc
            Q = soh_Q * self.nominal_capacity
            i_max_soc_lim = delta_soc_max * Q / (dt / 3600)

            # limit
            i_max = max(i, i_max_i_lim, i_max_v_lim, i_max_soc_lim)

        return i_max

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
        return self.cell.internal_resistance(state) / parallel * serial

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
