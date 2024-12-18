from dataclasses import dataclass

from scipy.optimize import fsolve

from simses.battery.cell import CellType


@dataclass
class BatteryState:
    t: float  # datetime ?
    v: float  # TODO: cell voltage or battery voltage??
    i: float
    T: float
    power: float
    power_setpoint: float
    soc: float
    ocv: float
    hys: float
    rint: float
    soh_Q: float
    soh_R: float
    is_charge: bool
    # loss

    @classmethod
    def initialize(cls, battery, start_soc, start_T, start_soh_Q: float = 1.0, start_soh_R: float = 1.0):
        state = cls(
            t=-2,
            v=0,  # uninitialized
            i=0,  # uninitialized
            T=start_T,
            power=0,
            power_setpoint=0,
            soc=start_soc,
            ocv=0,  # uninitialized
            hys=0,  # uninitialized
            is_charge=True,
            rint=0,  # uninitialized
            soh_Q=start_soh_Q,
            soh_R=start_soh_R,
        )
        state = battery.update(state, t=-1, power_setpoint=0)  # initialize ocv, rint
        return state


class Battery:
    def __init__(
        self,
        cell: CellType,
        voltage: float,  # in V
        energy_capacity: float,  # in Wh
        soc_limits: tuple[float, float] = (0.0, 1.0),  # in p.u.
    ) -> None:
        self.cell = cell
        self.voltage = voltage
        self.energy_capacity = energy_capacity
        self._soc_limits = soc_limits  # TODO assert input

        self._circuit = self._calculate_circuit(cell, voltage, energy_capacity)

    def _calculate_circuit(self, cell, voltage, energy_capacity, exact_size=False) -> tuple[float, float]:
        cell_voltage = cell.electrical.nominal_voltage
        cell_charge_capacity = cell.electrical.nominal_capacity

        # if exact_size:
        # TODO: not exact_size
        serial = voltage / cell_voltage
        parallel = energy_capacity / voltage / cell_charge_capacity
        return serial, parallel

    def update(self, state: BatteryState, power_setpoint, t) -> BatteryState:
        # update soc, ocv and rint based on previous state
        delta_t = (t - state.t) / 3600  # in h
        soc = state.soc + state.i * delta_t / (self.nominal_capacity * state.soh_Q)
        ocv = self.open_circuit_voltage(state)
        hys = self.hystheresis_voltage(state)
        rint = self.internal_resistance(state) * state.soh_R
        Q = state.soh_Q * self.nominal_capacity

        # update degradation based on previous state
        soh_Q = state.soh_Q  # self.cell.capacity_loss(state)
        soh_R = state.soh_R  # self.cell.resistance_increase(state)

        # calculate current to fullfil power
        i = float(fsolve(lambda i: power_setpoint - i * (ocv + hys + i * rint), x0=0.0)[0])

        # check current limits / voltage limits / soc limits
        i = self._get_maximum_current(i, delta_t, soc, ocv, hys, rint, Q, soh_Q)  # TODO: improve?

        # check current direction, maintain previous state if in rest
        is_charge = state.is_charge if i == 0 else i > 0

        # update terminal voltage and power
        v = ocv + hys + rint * i
        power = v * i

        # update losses
        # rint_loss = rint * i**2
        # hys_loss = abs(ocv - hys) * i # ?
        # reversible loss ?

        # update temperature
        T = state.T

        return BatteryState(t, v, i, T, power, power_setpoint, soc, ocv, hys, rint, soh_Q, soh_R, is_charge)

    def _get_maximum_current(self, i, delta_t, soc, ocv, hys, rint, Q, soh_Q) -> float:
        # TODO: differentiate between charge and discharge
        (soc_min, soc_max) = self._soc_limits

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
            i_max_soc_lim = delta_soc_max * Q / delta_t

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
            i_max_soc_lim = delta_soc_max * Q / delta_t

            # limit
            i_max = max(i, i_max_i_lim, i_max_v_lim, i_max_soc_lim)

        return i_max

    ## electrical properties
    def open_circuit_voltage(self, state):
        (serial, parallel) = self._circuit
        return self.cell.open_circuit_voltage(state) * parallel

    def hystheresis_voltage(self, state):
        (serial, parallel) = self._circuit
        return self.cell.hystheresis_voltage(state) * parallel

    def internal_resistance(self, state):
        (serial, parallel) = self._circuit
        # state.i = state.i / parallel # <- should be scaled to the cell
        return self.cell.internal_resistance(state) / parallel * serial

    @property
    def nominal_capacity(self) -> float:
        (serial, parallel) = self._circuit
        return self.cell.electrical.nominal_capacity * parallel

    @property
    def nominal_voltage(self) -> float:
        # TODO: is this required?
        (serial, parallel) = self._circuit
        return self.cell.electrical.nominal_voltage * serial

    @property
    def min_voltage(self) -> float:
        (serial, parallel) = self._circuit
        return self.cell.electrical.min_voltage * serial

    @property
    def max_voltage(self) -> float:
        (serial, parallel) = self._circuit
        return self.cell.electrical.max_voltage * serial

    @property
    def max_charge_current(self) -> float:
        (serial, parallel) = self._circuit
        return self.cell.electrical.nominal_capacity * self.cell.electrical.max_discharge_rate * parallel

    @property
    def max_discharge_current(self) -> float:
        (serial, parallel) = self._circuit
        return self.cell.electrical.nominal_capacity * self.cell.electrical.max_discharge_rate * parallel

    # def self_discharge_current(self, state) -> float:
    #     # TODO: ??
    #     (serial, parallel) = self.circuit
    #     return self.cell.electrical.self_discharge_rate * state.soc * serial * parallel

    @property
    def coulomb_efficiency(self) -> float:
        return self.cell.electrical.coulomb_efficiency

    ## thermal properties
    @property
    def specific_heat(self) -> float:
        (serial, parallel) = self._circuit
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
        (serial, parallel) = self._circuit
        return self.cell.format.volume * serial * parallel

    @property
    def area(self) -> float:
        # TODO: is this required?
        (serial, parallel) = self._circuit
        return self.cell.format.area * serial * parallel
