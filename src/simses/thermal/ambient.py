from dataclasses import dataclass

from simses.thermal.protocol import ThermalComponent


@dataclass
class AmbientThermalState:
    """Mutable state of a :class:`AmbientThermalModel`.

    Attributes:
        T_ambient:     External ambient temperature in K.
    """

    T_ambient: float


class AmbientThermalModel:
    """Zero-dimensional room thermal model with constant ambient temperature.

    Models heat exchange between registered components and a constant-temperature
    environment. Each component is an independent thermal node with its own
    temperature, thermal capacity, and thermal resistance.

    Per-component ODE (forward Euler integration)::

        dT_i / dt = Q_heat_i / C_th_i + (T_ambient - T_i) / (R_th_i * C_th_i)

    Components are registered via :meth:`add_component` and must provide:

    * ``state.T``             -- current temperature in K (read/written)
    * ``state.heat``          -- total heat generation in W (read)
    * ``thermal_capacity``    -- thermal capacity in J/K (read)
    * ``thermal_resistance``  -- thermal resistance in K/W (read)
    """

    def __init__(self, T_ambient: float, components: list | None = None) -> None:
        """
        Args:
            T_ambient: Ambient temperature in K. May be overwritten at any
                time via the ``T_ambient`` attribute to drive a
                time-varying profile.
            components: Initial list of :class:`ThermalComponent` nodes.
                ``None`` (default) starts with no components — add them
                via :meth:`add_component`.
        """
        self.state = AmbientThermalState(T_ambient=T_ambient)
        self._components: list = list(components) if components else []

    def add_component(self, component: ThermalComponent) -> None:
        """Register a component as a thermal node.

        Args:
            component: Any object satisfying the :class:`ThermalComponent` protocol.
        """
        self._components.append(component)

    def step(self, dt: float) -> None:
        """Advance every registered component's temperature by one timestep.

        Args:
            dt: Timestep in seconds.
        """
        T_amb = self.T_ambient
        for comp in self._components:
            T = comp.state.T
            C_th = comp.thermal_capacity
            R_th = comp.thermal_resistance
            Q_loss = comp.state.heat

            dT_dt = Q_loss / C_th + (T_amb - T) / (R_th * C_th)
            comp.state.T = T + dT_dt * dt

    @property
    def T_ambient(self) -> float:
        """External ambient temperature in K (convenience accessor for ``state.T_ambient``)."""
        return self.state.T_ambient

    @T_ambient.setter
    def T_ambient(self, value: float) -> None:
        self.state.T_ambient = value
