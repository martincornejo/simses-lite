"""Container thermal model for containerised BESS installations.

Models heat exchange between batteries, internal container air, three-layer
container walls, and the external environment, with an optional HVAC strategy.
"""

import enum
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ContainerLayer:
    """Physical properties of a single wall layer.

    Attributes:
        thickness:     Layer thickness in m.
        conductivity:  Thermal conductivity in W/mK.
        density:       Material density in kg/m³.
        specific_heat: Specific heat capacity in J/kgK.
    """

    thickness: float
    conductivity: float
    density: float
    specific_heat: float


@dataclass
class ContainerProperties:
    """Geometry and thermal properties of a container.

    Internal dimensions are used to derive surface area and internal volume.
    Convection coefficients apply at inner and outer surfaces.

    Attributes:
        length:     Internal length in m.
        width:      Internal width in m.
        height:     Internal height in m.
        h_inner:    Inner surface convection coefficient in W/m²K.
        h_outer:    Outer surface convection coefficient in W/m²K.
        inner:      Innermost wall layer (e.g. aluminium).
        mid:        Middle wall layer (e.g. insulation).
        outer:      Outermost wall layer (e.g. steel).
        vol_air:    Factor of volume of the container occupied by air in % (default: 1.0)
        A_surface:  Total surface area in m² (derived).
        V_internal: Internal volume in m³ (derived).
    """

    length: float
    width: float
    height: float
    h_inner: float
    h_outer: float
    inner: ContainerLayer
    mid: ContainerLayer
    outer: ContainerLayer
    vol_air : float = 1.0
    A_surface: float = field(init=False)
    V_internal: float = field(init=False)
    
    def __post_init__(self):
        self.A_surface = 2 * (
            self.length * self.width
            + self.length * self.height
            + self.width * self.height
        )
        self.V_internal = self.length * self.width * self.height * self.vol_air


@dataclass
class ContainerThermalState:
    """Mutable state of a :class:`ContainerThermalModel`.

    Attributes:
        T_air:      Internal air temperature in K.
        T_in:       Inner wall layer temperature in K.
        T_mid:      Middle wall layer temperature in K.
        T_out:      Outer wall layer temperature in K.
        T_ambient:  External ambient temperature in K.
        Q_solar:    Solar irradiance heat load on the outer wall in W
                    (default 0).
        power_th:   HVAC thermal power delivered to the air in W
                    (positive = heating, negative = cooling, 0 = idle).
        power_el:   HVAC electrical power consumption in W (always ≥ 0).
    """

    T_air: float
    T_in: float
    T_mid: float
    T_out: float
    T_amb: float
    Q_solar: float = 0.0
    power_th: float = 0.0
    power_el: float = 0.0


class ThermostatMode(enum.Enum):
    IDLE = "idle"
    HEATING = "heating"
    COOLING = "cooling"


class HvacModel(Protocol):
    """Protocol for HVAC hardware models.

    The sole responsibility is to convert a thermal power demand into the
    corresponding electrical consumption.  The model is stateless — no results
    are stored internally; the caller (the thermal model) is responsible for
    recording them in its state.
    """

    def electrical_consumption(self, Q_thermal: float) -> float:
        """Return the electrical power required to deliver ``Q_thermal``.

        Args:
            Q_thermal: Thermal power in W
                (positive = heating, negative = cooling, 0 = idle).

        Returns:
            Electrical power draw in W (always ≥ 0).
        """
        ...


class ThermalManagementStrategy(Protocol):
    """Protocol for thermostat control strategies.

    Used by :class:`ContainerThermalModel`.  ``control()`` returns the
    requested thermal power based on a reference temperature derived from
    the registered storage components.
    """

    def control(self, T_ref: float, dt: float) -> float:
        """Advance the strategy and return the requested thermal power.

        Args:
            T_ref: Reference temperature in K — the maximum temperature
                   across all registered storage components.
            dt:    Timestep in seconds.

        Returns:
            ``Q_thermal``: thermal power in W
              (positive = adds heat, negative = removes heat, 0 = idle).
        """
        ...


class ConstantCopHvac:
    """HVAC hardware model with fixed coefficients of performance.

    Electrical consumption is proportional to the thermal demand:

      heating (Q_thermal > 0): P_el = Q_thermal / cop_heating
      cooling (Q_thermal < 0): P_el = |Q_thermal| / cop_cooling

    Args:
        cop_cooling: COP for cooling mode (default 3.0).
        cop_heating: COP for heating mode (default 2.5).
    """

    def __init__(self, cop_cooling: float = 3.0, cop_heating: float = 2.5) -> None:
        self.cop_cooling = cop_cooling
        self.cop_heating = cop_heating

    def electrical_consumption(self, Q_thermal: float) -> float:
        """Return the electrical power required to deliver ``Q_thermal``."""
        if Q_thermal > 0:
            return Q_thermal / self.cop_heating
        if Q_thermal < 0:
            return -Q_thermal / self.cop_cooling
        return 0.0


class ThermostatStrategy:
    """Hysteresis thermostat control strategy.

    Decides when to heat or cool based on setpoint and dead-band.  The
    requested thermal power (±``max_power``) is passed to an :class:`HvacModel`
    to obtain the corresponding electrical consumption.  No power values are
    stored in the strategy itself.

    State machine transitions:
      IDLE    → HEATING  if T_air < T_setpoint - threshold
      IDLE    → COOLING  if T_air > T_setpoint + threshold
      HEATING → IDLE     if T_air >= T_setpoint
      COOLING → IDLE     if T_air <= T_setpoint

    Args:
        T_setpoint: Target internal air temperature in K.
        max_power:  Maximum thermal output requested from the HVAC unit in W.
        hvac:       HVAC hardware model that converts Q_thermal → P_el.
        threshold:  Half-width of the dead-band in K (default 5.0).
    """

    def __init__(
        self,
        T_setpoint: float,
        max_power: float,
        threshold: float = 5.0,
    ) -> None:
        self.T_setpoint = T_setpoint
        self.max_power = max_power
        self.threshold = threshold
        self._mode = ThermostatMode.IDLE

    @property
    def mode(self) -> ThermostatMode:
        """Current thermostat operating mode."""
        return self._mode

    def control(self, T_ref: float, dt: float) -> float:
        """Advance the state machine and return the requested thermal power.

        Args:
            T_ref: Reference temperature in K (max battery temperature).
            dt:    Timestep in seconds (unused but required by protocol).

        Returns:
            ``Q_thermal``: thermal power in W (±max_power or 0.0).
        """
        T_sp = self.T_setpoint
        thresh = self.threshold

        if self._mode is ThermostatMode.IDLE:
            if T_ref < T_sp - thresh:
                self._mode = ThermostatMode.HEATING
            elif T_ref > T_sp + thresh:
                self._mode = ThermostatMode.COOLING
        elif self._mode is ThermostatMode.HEATING:
            if T_ref >= T_sp:
                self._mode = ThermostatMode.IDLE
        else:  # COOLING
            if T_ref <= T_sp:
                self._mode = ThermostatMode.IDLE

        if self._mode is ThermostatMode.HEATING:
            Q = self.max_power
        elif self._mode is ThermostatMode.COOLING:
            Q = -self.max_power
        else:
            Q = 0.0

        return Q


class ExternalThermalManagement:
    """Pass-through thermal management strategy for external controllers.

    Instead of computing HVAC power internally, this strategy returns a
    value set externally via the :attr:`Q_hvac` property.  Use this when
    an external controller (e.g. MPC) decides the thermal power.

    Example::

        tms = ExternalThermalManagement()
        container = ContainerThermalModel(..., tms=tms)

        # In the simulation loop:
        tms.Q_hvac = mpc_computed_power
        container.update(dt=1.0)
    """

    def __init__(self) -> None:
        self.Q_hvac: float = 0.0

    def control(self, T_ref: float, dt: float) -> float:  # noqa: ARG002
        """Return the externally-set thermal power."""
        return self.Q_hvac


class ContainerThermalModel:
    """Physics-based container thermal model with three-layer walls and HVAC.

    Five coupled thermal nodes (forward Euler):
      - Battery nodes (one per registered component)
      - Internal air
      - Inner wall layer
      - Mid wall layer
      - Outer wall layer

    The outer wall is coupled to a constant ambient temperature.
    Observable outputs are stored in :attr:`state` after each :meth:`update`.

    Components are registered via :meth:`add_component` and must provide:

    * ``state.T``            -- current temperature in K (read/written)
    * ``state.heat``         -- total heat generation in W (read)
    * ``thermal_capacity``   -- thermal capacity in J/K (read)
    * ``thermal_resistance`` -- thermal resistance to internal air in K/W (read)

    Args:
        properties: Container geometry and wall parameters.
        T_ambient:  External ambient temperature in K (constant).
        T_initial:  Initial temperature for all internal nodes in K.
        hvac:       Optional HVAC strategy; ``None`` means no active HVAC.
    """

    _RHO_AIR: float = 1.204   # kg/m³
    _CP_AIR: float = 1006.0   # J/kgK

    def __init__(
        self,
        properties: ContainerProperties,
        T_ambient: float,
        T_initial: float,
        hvac: HvacModel,
        tms: ThermalManagementStrategy,
    ) -> None:
        self._props = properties
        self.hvac = hvac
        self.tms = tms
        self._components: list = []

        self.state = ContainerThermalState(
            T_air=T_initial,
            T_in=T_initial,
            T_mid=T_initial,
            T_out=T_initial,
            T_amb=T_ambient,
        )

        # precompute thermal capacities
        A = properties.A_surface
        V = properties.V_internal
        inner = properties.inner
        mid = properties.mid
        outer = properties.outer

        self._C_air = self._RHO_AIR * V * self._CP_AIR
        self._C_in = inner.density * inner.thickness * A * inner.specific_heat
        self._C_mid = mid.density * mid.thickness * A * mid.specific_heat
        self._C_out = outer.density * outer.thickness * A * outer.specific_heat

        # precompute thermal resistances
        self._R_air_out = 1.0 / (properties.h_outer * A)
        self._R_out_mid = (
            outer.thickness / (outer.conductivity * A)
            + 0.5 * mid.thickness / (mid.conductivity * A)
        )
        self._R_mid_in = (
            0.5 * mid.thickness / (mid.conductivity * A)
            + inner.thickness / (inner.conductivity * A)
        )
        self._R_in_air = 1.0 / (properties.h_inner * A)

    @property
    def T_ambient(self) -> float:
        """External ambient temperature in K (convenience accessor for ``state.T_ambient``)."""
        return self.state.T_amb

    @T_ambient.setter
    def T_ambient(self, value: float) -> None:
        self.state.T_amb = value

    @property
    def Q_solar(self) -> float:
        """Solar irradiance heat load on the outer wall in W."""
        return self.state.Q_solar

    @Q_solar.setter
    def Q_solar(self, value: float) -> None:
        self.state.Q_solar = value

    def add_component(self, component) -> None:
        """Register a component as a thermal node.

        Args:
            component: Any object satisfying the duck-typed interface.
        """
        self._components.append(component)

    def update(self, dt: float) -> None:
        """Advance all thermal nodes by one timestep.

        Args:
            dt: Timestep in seconds.
        """
        T_air = self.state.T_air
        T_in = self.state.T_in
        T_mid = self.state.T_mid
        T_out = self.state.T_out
        T_amb = self.state.T_amb

        # resistances (short names for readability)
        R_air_out = self._R_air_out
        R_out_mid = self._R_out_mid
        R_mid_in = self._R_mid_in
        R_in_air = self._R_in_air

        # HVAC: thermal power injected into air and associated electrical consumption
        T_ref = max((c.state.T for c in self._components), default=T_air)
        Q_hvac = self.tms.control(T_ref, dt)
        P_el = self.hvac.electrical_consumption(Q_hvac)

        # battery nodes — compute all dT before write-back
        bat_dTs: list[float] = []
        Q_bats_to_air = 0.0
        for comp in self._components:
            T_bat = comp.state.T
            C_bat = comp.thermal_capacity
            R_bat = comp.thermal_resistance
            dT = (comp.state.heat / C_bat) - (T_bat - T_air) / (R_bat * C_bat)
            bat_dTs.append(dT)
            Q_bats_to_air += (T_bat - T_air) / R_bat

        # air node
        dT_air = (Q_bats_to_air + (T_in - T_air) / R_in_air + Q_hvac) / self._C_air

        # wall nodes
        dT_in = ((T_mid - T_in) / R_mid_in - (T_in - T_air) / R_in_air) / self._C_in
        dT_mid = ((T_out - T_mid) / R_out_mid - (T_mid - T_in) / R_mid_in) / self._C_mid
        dT_out = (self.state.Q_solar + (T_amb - T_out) / R_air_out - (T_out - T_mid) / R_out_mid) / self._C_out

        # write back — batteries first, then state, then walls
        for comp, dT in zip(self._components, bat_dTs, strict=True):
            comp.state.T += dT * dt

        self.state.T_air = T_air + dT_air * dt
        self.state.power_th = Q_hvac
        self.state.power_el = P_el

        self.state.T_in = T_in + dT_in * dt
        self.state.T_mid = T_mid + dT_mid * dt
        self.state.T_out = T_out + dT_out * dt
