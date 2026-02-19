class RoomThermalModel:
    """Zero-dimensional room thermal model with constant ambient temperature.

    Models heat exchange between registered components and a constant-temperature
    environment. Each component is an independent thermal node with its own
    temperature, thermal capacity, and thermal resistance.

    Per-component ODE (forward Euler integration)::

        dT_i / dt = Q_loss_i / C_th_i + (T_ambient - T_i) / (R_th_i * C_th_i)

    Components are registered via :meth:`add_component` and must provide:

    * ``state.T``             -- current temperature in K (read/written)
    * ``state.loss``          -- heat generation in W (read)
    * ``thermal_capacity``    -- thermal capacity in J/K (read)
    * ``thermal_resistance``  -- thermal resistance in K/W (read)
    """

    def __init__(self, T_ambient: float, components: list | None = None) -> None:
        self.T_ambient = T_ambient
        self._components: list = list(components) if components else []

    def add_component(self, component) -> None:
        """Register a component as a thermal node.

        Args:
            component: Any object satisfying the duck-typed interface
                (state.T, state.loss, thermal_capacity, thermal_resistance).
        """
        self._components.append(component)

    def update(self, dt: float) -> None:
        """Advance every registered component's temperature by one timestep.

        Args:
            dt: Timestep in seconds.
        """
        T_amb = self.T_ambient
        for comp in self._components:
            T = comp.state.T
            C_th = comp.thermal_capacity
            R_th = comp.thermal_resistance
            Q_loss = comp.state.loss

            dT_dt = Q_loss / C_th + (T_amb - T) / (R_th * C_th)
            comp.state.T = T + dT_dt * dt
