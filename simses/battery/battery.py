import math

from simses.battery.cell import CellType
from simses.battery.derating import CurrentDerating
from simses.battery.state import BatteryState
from simses.degradation.degradation import DegradationModel


class Battery:
    """Battery system composed of cells in a series-parallel circuit."""

    def __init__(
        self,
        cell: CellType,
        circuit: tuple[int, int],  # (s, p)
        initial_states: dict,
        soc_limits: tuple[float, float] = (0.0, 1.0),  # in p.u.
        degradation: DegradationModel | bool | None = None,
        derating: CurrentDerating | None = None,
    ) -> None:
        if degradation is False:
            degradation = None
        if degradation is True:
            initial_soc = initial_states["start_soc"]
            degradation = cell.default_degradation_model(initial_soc)
            if degradation is None:
                raise ValueError(
                    f"{type(cell).__name__} has no default degradation model. "
                    "Pass an explicit DegradationModel or use degradation=None."
                )
        self.cell = cell
        self.circuit = circuit
        self.soc_limits = soc_limits
        self.degradation = degradation
        self.derating = derating
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
            heat=0,
            soc=start_soc,
            ocv=0,  # uninitialized
            hys=0,  # uninitialized
            entropy=0,  # uninitialized
            is_charge=True,
            rint=0,  # uninitialized
            soh_Q=start_soh_Q,
            soh_R=start_soh_R,
            i_max_charge=0.0,
            i_max_discharge=0.0,
        )
        state.ocv = state.v = self.open_circuit_voltage(state)
        state.hys = self.hystheresis_voltage(state)
        state.rint = self.internal_resistance(state)
        state.entropy = self.entropic_coefficient(state)
        return state

    def update(self, power_setpoint: float, dt: float) -> None:
        """
        Update the battery state based on a power setpoint and timestep.
        If the battery cannot fulfill the power setpoint due to technical limits, it will curtail the current and update the state accordingly.

            Args:
            power_sentpoint: float
                Input power target in W
            dt: float
                Timestep in s
        """
        state: BatteryState = self.state
        state.is_charge = power_setpoint > 0.0

        # --- phase 1: refresh derived cell properties from current soc/T ---
        # ocv, hys, rint are derived from inputs (soc, T, soh_R) that do not
        # change during this method, so updating them here is safe and ensures
        # all calculations — including derating — use consistent current values.
        ocv = state.ocv = self.open_circuit_voltage(state)
        hys = state.hys = self.hystheresis_voltage(state)
        rint = state.rint = self.internal_resistance(state)
        entropy = state.entropy = self.entropic_coefficient(state)
        Q = self.capacity(state)

        # 1. Calculate equilibrium current to meet power setpoint
        i = self.equilibrium_current(power_setpoint, ocv, hys, rint)

        # 2. Calculate hard current limits (C-rate, voltage, SOC)
        i_max_charge, i_max_discharge = self.calculate_max_currents(state, dt, ocv, hys, rint, Q)

        # 3. Curtail solved current to hard limits
        if i > 0:
            i = min(i, i_max_charge)
        elif i < 0:
            i = max(i, i_max_discharge)

        # 4. Apply derating (optional).
        # i_max_charge / i_max_discharge are only updated when derating actually reduces i,
        # so that the reported limits reflect the hard limits during normal operation and only
        # drop when the battery is genuinely in the derating zone.
        if self.derating is not None:
            i_derate = self.derating.derate(i, state)
            if i > 0 and i_derate < i:
                i = i_derate
                i_max_charge = min(i_max_charge, i_derate)
            elif i < 0 and i_derate > i:
                i = i_derate
                i_max_discharge = max(i_max_discharge, i_derate)

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
        loss_irr = (v - ocv) * i  # irreversible losses
        loss_rev = entropy * state.T * i  # reversible losses
        heat = loss_irr + loss_rev  # internal heat generation

        # --- phase 2: write output state ---
        state.v = v
        state.i = i
        state.power = power
        state.power_setpoint = power_setpoint
        state.loss = loss_irr
        state.heat = heat
        state.soc = soc
        state.is_charge = is_charge
        state.i_max_charge = i_max_charge
        state.i_max_discharge = i_max_discharge

        if self.degradation is not None:
            self.degradation.update(self.state, dt)  # updates state.soh_Q and state.soh_R

    def equilibrium_current(self, power_setpoint: float, ocv: float, hys: float, rint: float) -> float:
        """
        Calculates the battery current that fullfils the power setpoint.

        The equilibrium current is calculated based on the equivalent circuit model
        p = i * v
          = i * (ocv + rint * i)
        """
        ocv = ocv + hys  # include hysteresis in equilibrium calculation
        if power_setpoint == 0.0:
            return 0.0
        return -(ocv - math.sqrt(ocv**2 + 4 * rint * power_setpoint)) / (2 * rint)

    def calculate_max_currents(
        self, state: BatteryState, dt: float, ocv: float, hys: float, rint: float, Q: float
    ) -> tuple[float, float]:
        """Return (i_max_charge, i_max_discharge) based on C-rate, voltage and SOC limits."""
        (soc_min, soc_max) = self.soc_limits
        soc = state.soc

        # charge (all three values are positive; min = most restrictive)
        i_max_charge = min(
            self.max_charge_current,  # C-rate limit
            (self.max_voltage - ocv - hys) / rint,  # voltage limit
            (soc_max - soc) * Q / (dt / 3600),  # SOC limit
        )
        # discharge (all three values are negative; max = least negative = most restrictive)
        i_max_discharge = max(
            -self.max_discharge_current,  # C-rate limit
            (self.min_voltage - ocv - hys) / rint,  # voltage limit
            (soc_min - soc) * Q / (dt / 3600),  # SOC limit
        )
        return i_max_charge, i_max_discharge

    ## electrical properties
    def open_circuit_voltage(self, state: BatteryState) -> float:
        """Return the system-level open-circuit voltage in V."""
        (serial, parallel) = self.circuit

        return self.cell.open_circuit_voltage(state) * serial

    def hystheresis_voltage(self, state: BatteryState) -> float:
        """Return the system-level hysteresis voltage in V."""
        (serial, parallel) = self.circuit

        return self.cell.hystheresis_voltage(state) * serial

    def internal_resistance(self, state: BatteryState) -> float:
        """Return the system-level internal resistance in Ohms, scaled by SoH."""
        (serial, parallel) = self.circuit

        # state.i = state.i / parallel # <- should be scaled to the cell
        return self.cell.internal_resistance(state) / parallel * serial * state.soh_R

    def entropic_coefficient(self, state: BatteryState) -> float:
        """Return the system-level entropic coefficient in V/K."""
        (serial, parallel) = self.circuit
        return self.cell.entropic_coefficient(state) * serial

    def capacity(self, state: BatteryState) -> float:
        """Return the current capacity in Ah, scaled by SoH."""
        return self.nominal_capacity * state.soh_Q

    def energy_capacity(self, state: BatteryState) -> float:
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
    def max_charge_current(self) -> float:
        """Maximum allowed charge current in A."""
        (serial, parallel) = self.circuit

        return self.cell.electrical.nominal_capacity * self.cell.electrical.max_charge_rate * parallel

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
    def thermal_capacity(self) -> float:
        """Total thermal capacity of the battery system in J/K."""
        (serial, parallel) = self.circuit

        return self.cell.thermal.specific_heat * self.cell.thermal.mass * serial * parallel

    @property
    def convection_coefficient(self) -> float:
        """Convection coefficient of the cell in W/m2K."""
        return self.cell.thermal.convection_coefficient

    @property
    def thermal_resistance(self) -> float:
        """Thermal resistance of the battery system in K/W."""
        return 1 / (self.convection_coefficient * self.area)

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
        """Effective cooling area of all cells in m2.

        Assumes prismatic cells are stacked so only the top and bottom faces
        (2 * width * length) exchange heat with the environment.
        """
        (serial, parallel) = self.circuit

        return 2 * self.volume / (self.cell.format.height * 1e-3)  # height mm -> m
