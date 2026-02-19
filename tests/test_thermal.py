"""Unit and integration tests for the RoomThermalModel."""

from itertools import pairwise

import pytest

from simses.thermal.thermal import RoomThermalModel
from tests.test_battery import _make_battery


# ---------------------------------------------------------------------------
# Lightweight mock component (duck-typed to match the thermal model interface)
# ---------------------------------------------------------------------------
class _MockState:
    __slots__ = ("T", "loss")

    def __init__(self, T: float, loss: float = 0.0):
        self.T = T
        self.loss = loss


class _MockComponent:
    """Minimal component satisfying the RoomThermalModel duck-typed interface."""

    def __init__(self, T: float, loss: float, thermal_capacity: float, thermal_resistance: float):
        self.state = _MockState(T=T, loss=loss)
        self.thermal_capacity = thermal_capacity
        self.thermal_resistance = thermal_resistance


# ===================================================================
# Unit tests (mock components — isolated thermal physics)
# ===================================================================
class TestRoomThermalModelUnit:
    def test_equilibrium_no_loss(self):
        """T == T_ambient and loss == 0 => temperature unchanged."""
        comp = _MockComponent(T=298.15, loss=0.0, thermal_capacity=1000.0, thermal_resistance=1.0)
        model = RoomThermalModel(T_ambient=298.15, components=[comp])

        model.update(dt=1.0)

        assert comp.state.T == pytest.approx(298.15)

    def test_heating_from_loss(self):
        """Positive loss at T == T_ambient raises temperature."""
        comp = _MockComponent(T=298.15, loss=500.0, thermal_capacity=1000.0, thermal_resistance=1.0)
        model = RoomThermalModel(T_ambient=298.15, components=[comp])

        model.update(dt=1.0)

        # dT = (500 / 1000 + 0) * 1 = 0.5 K
        assert comp.state.T == pytest.approx(298.65)

    def test_cooling_toward_ambient(self):
        """Hot component with no loss cools toward ambient."""
        comp = _MockComponent(T=310.0, loss=0.0, thermal_capacity=1000.0, thermal_resistance=1.0)
        model = RoomThermalModel(T_ambient=298.15, components=[comp])

        model.update(dt=1.0)

        # dT = (0 + (298.15 - 310) / (1 * 1000)) * 1 = -0.01185 K
        assert comp.state.T < 310.0
        assert comp.state.T > 298.15
        assert comp.state.T == pytest.approx(310.0 - 11.85 / 1000)

    def test_warming_toward_ambient(self):
        """Cold component with no loss warms toward ambient."""
        comp = _MockComponent(T=280.0, loss=0.0, thermal_capacity=1000.0, thermal_resistance=1.0)
        model = RoomThermalModel(T_ambient=298.15, components=[comp])

        model.update(dt=1.0)

        assert comp.state.T > 280.0
        assert comp.state.T < 298.15

    def test_steady_state_temperature(self):
        """With constant loss, T converges to T_ambient + Q_loss * R_th."""
        Q_loss = 100.0
        R_th = 2.0
        C_th = 500.0
        T_amb = 298.15
        T_expected = T_amb + Q_loss * R_th  # 498.15 K

        comp = _MockComponent(T=T_amb, loss=Q_loss, thermal_capacity=C_th, thermal_resistance=R_th)
        model = RoomThermalModel(T_ambient=T_amb, components=[comp])

        for _ in range(100_000):
            model.update(dt=1.0)

        assert comp.state.T == pytest.approx(T_expected, rel=1e-3)

    def test_multiple_components_independent(self):
        """Each component evolves independently with its own thermal properties."""
        comp_hot = _MockComponent(T=350.0, loss=0.0, thermal_capacity=1000.0, thermal_resistance=1.0)
        comp_cold = _MockComponent(T=270.0, loss=0.0, thermal_capacity=2000.0, thermal_resistance=0.5)
        model = RoomThermalModel(T_ambient=298.15, components=[comp_hot, comp_cold])

        model.update(dt=10.0)

        assert comp_hot.state.T < 350.0   # cooled
        assert comp_cold.state.T > 270.0  # warmed

    def test_no_components_is_noop(self):
        """update() with no components registered does nothing."""
        model = RoomThermalModel(T_ambient=298.15)
        model.update(dt=1.0)  # should not raise

    def test_exact_euler_step(self):
        """Verify the forward Euler formula for one step."""
        T_0 = 300.0
        Q = 200.0
        C = 800.0
        R = 1.5
        T_amb = 295.0
        dt = 2.0

        dT_dt = Q / C + (T_amb - T_0) / (R * C)
        T_expected = T_0 + dT_dt * dt

        comp = _MockComponent(T=T_0, loss=Q, thermal_capacity=C, thermal_resistance=R)
        model = RoomThermalModel(T_ambient=T_amb, components=[comp])
        model.update(dt=dt)

        assert comp.state.T == pytest.approx(T_expected)

    def test_constructor_and_add_component_are_equivalent(self):
        """Passing components via constructor or add_component gives the same result."""
        comp_a = _MockComponent(T=310.0, loss=100.0, thermal_capacity=1000.0, thermal_resistance=1.0)
        comp_b = _MockComponent(T=310.0, loss=100.0, thermal_capacity=1000.0, thermal_resistance=1.0)

        model_ctor = RoomThermalModel(T_ambient=298.15, components=[comp_a])
        model_ctor.update(dt=5.0)

        model_add = RoomThermalModel(T_ambient=298.15)
        model_add.add_component(comp_b)
        model_add.update(dt=5.0)

        assert comp_a.state.T == pytest.approx(comp_b.state.T)


# ===================================================================
# Integration tests (real Battery)
# ===================================================================
class TestRoomThermalModelWithBattery:
    def test_battery_heats_on_charge(self):
        """Charging creates loss which heats the battery."""
        bat = _make_battery(T=298.15)
        bat.update(power_setpoint=1000.0, dt=1.0)
        assert bat.state.loss > 0

        model = RoomThermalModel(T_ambient=298.15)
        model.add_component(bat)
        model.update(dt=1.0)

        assert bat.state.T > 298.15

    def test_battery_heats_on_discharge(self):
        """Discharging creates loss which heats the battery."""
        bat = _make_battery(T=298.15)
        bat.update(power_setpoint=-1000.0, dt=1.0)
        assert bat.state.loss > 0

        model = RoomThermalModel(T_ambient=298.15)
        model.add_component(bat)
        model.update(dt=1.0)

        assert bat.state.T > 298.15

    def test_battery_cools_at_rest(self):
        """Hot battery at rest cools toward ambient."""
        bat = _make_battery(T=320.0)
        bat.update(power_setpoint=0.0, dt=1.0)
        assert bat.state.loss == 0.0

        model = RoomThermalModel(T_ambient=298.15)
        model.add_component(bat)
        model.update(dt=60.0)

        assert bat.state.T < 320.0

    def test_simulation_loop(self):
        """Full simulation loop: battery.update then thermal.update each step."""
        bat = _make_battery(T=298.15, soc=0.5)
        model = RoomThermalModel(T_ambient=298.15)
        model.add_component(bat)

        temps = [bat.state.T]
        for _ in range(20):
            bat.update(power_setpoint=500.0, dt=60.0)
            model.update(dt=60.0)
            temps.append(bat.state.T)

        # temperature should rise monotonically (losses always positive, starting at ambient)
        assert all(t2 >= t1 - 1e-12 for t1, t2 in pairwise(temps))
        assert temps[-1] > temps[0]

    def test_two_batteries_diverge(self):
        """Two batteries with different loads develop different temperatures."""
        bat_high = _make_battery(T=298.15, soc=0.5)
        bat_low = _make_battery(T=298.15, soc=0.5)

        model = RoomThermalModel(T_ambient=298.15)
        model.add_component(bat_high)
        model.add_component(bat_low)

        for _ in range(10):
            bat_high.update(power_setpoint=2000.0, dt=60.0)
            bat_low.update(power_setpoint=100.0, dt=60.0)
            model.update(dt=60.0)

        # higher load => more loss => higher temperature
        assert bat_high.state.T > bat_low.state.T
