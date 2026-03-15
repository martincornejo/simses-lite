"""Tests for ContainerThermalModel, ContainerProperties, and ThermostatStrategy."""

import pytest

from simses.model.thermal.containers import FortyFtContainer, TwentyFtContainer
from simses.thermal.container import (
    ConstantCopHvac,
    ContainerLayer,
    ContainerProperties,
    ContainerThermalModel,
    ThermostatMode,
    ThermostatStrategy,
)
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
    def __init__(self, T: float, loss: float, thermal_capacity: float, thermal_resistance: float):
        self.state = _MockState(T=T, loss=loss)
        self.thermal_capacity = thermal_capacity
        self.thermal_resistance = thermal_resistance


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------
def _unit_box_container() -> ContainerProperties:
    """1 m × 1 m × 1 m container with simple aluminium-only walls (no insulation)."""
    layer = ContainerLayer(thickness=0.001, conductivity=237.0, density=2700.0, specific_heat=910.0)
    return ContainerProperties(
        length=1.0,
        width=1.0,
        height=1.0,
        h_inner=10.0,
        h_outer=10.0,
        inner=layer,
        mid=layer,
        outer=layer,
    )


def _make_model(T_ambient=298.15, T_initial=298.15, hvac=None):
    return ContainerThermalModel(
        properties=_unit_box_container(),
        T_ambient=T_ambient,
        T_initial=T_initial,
        hvac=hvac,
    )


# ===================================================================
# ContainerProperties
# ===================================================================
class TestContainerProperties:
    def test_unit_box_A_surface(self):
        props = _unit_box_container()
        assert props.A_surface == pytest.approx(6.0)

    def test_unit_box_V_internal(self):
        props = _unit_box_container()
        assert props.V_internal == pytest.approx(1.0)

    def test_forty_ft_A_surface_sanity(self):
        # 2*(12*2.3 + 12*2.35 + 2.3*2.35) = 2*(27.6 + 28.2 + 5.405) = 2*61.205 ≈ 122.41
        # expect > 100
        assert FortyFtContainer.A_surface > 100.0

    def test_forty_ft_V_internal(self):
        expected = 12.0 * 2.3 * 2.35
        assert FortyFtContainer.V_internal == pytest.approx(expected)

    def test_twenty_ft_smaller_than_forty_ft(self):
        assert TwentyFtContainer.A_surface < FortyFtContainer.A_surface
        assert TwentyFtContainer.V_internal < FortyFtContainer.V_internal


# ===================================================================
# ThermostatStrategy
# ===================================================================
class TestThermostatStrategy:
    def _make(self, T_setpoint=300.0, max_power=5000.0, threshold=5.0):
        return ThermostatStrategy(
            T_setpoint=T_setpoint, max_power=max_power, hvac=ConstantCopHvac(), threshold=threshold
        )

    # --- initial mode ---
    def test_starts_idle(self):
        t = self._make()
        assert t.mode is ThermostatMode.IDLE

    # --- idle within dead-band ---
    def test_idle_no_trigger_within_band(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q, _ = t.control(T_air=302.0, dt=1.0)
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_idle_lower_edge_no_trigger(self):
        """Exactly at lower edge (T_sp - threshold) should not trigger heating."""
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q, _ = t.control(T_air=295.0, dt=1.0)
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_idle_upper_edge_no_trigger(self):
        """Exactly at upper edge (T_sp + threshold) should not trigger cooling."""
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q, _ = t.control(T_air=305.0, dt=1.0)
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    # --- heating transitions ---
    def test_idle_triggers_heating_below_band(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q, _ = t.control(T_air=294.0, dt=1.0)
        assert Q == pytest.approx(5000.0)
        assert t.mode is ThermostatMode.HEATING

    def test_heating_stops_at_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_air=290.0, dt=1.0)  # enter heating
        Q, _ = t.control(T_air=300.0, dt=1.0)  # at setpoint → idle
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_heating_continues_below_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_air=290.0, dt=1.0)  # enter heating
        Q, _ = t.control(T_air=298.0, dt=1.0)  # still below setpoint
        assert Q == pytest.approx(5000.0)
        assert t.mode is ThermostatMode.HEATING

    # --- cooling transitions ---
    def test_idle_triggers_cooling_above_band(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q, _ = t.control(T_air=306.0, dt=1.0)
        assert Q == pytest.approx(-5000.0)
        assert t.mode is ThermostatMode.COOLING

    def test_cooling_stops_at_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_air=310.0, dt=1.0)  # enter cooling
        Q, _ = t.control(T_air=300.0, dt=1.0)  # at setpoint → idle
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_cooling_continues_above_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_air=310.0, dt=1.0)  # enter cooling
        Q, _ = t.control(T_air=302.0, dt=1.0)  # still above setpoint
        assert Q == pytest.approx(-5000.0)
        assert t.mode is ThermostatMode.COOLING

    # --- hysteresis ---
    def test_no_cooling_trigger_inside_band_after_heating(self):
        """After heating stops, must not immediately trigger cooling."""
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_air=290.0, dt=1.0)  # → HEATING
        t.control(T_air=300.0, dt=1.0)  # → IDLE at setpoint
        Q, _ = t.control(T_air=303.0, dt=1.0)  # inside band, should stay IDLE
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE


# ===================================================================
# ContainerThermalModel — unit tests (mock components)
# ===================================================================
class TestContainerThermalModelUnit:
    def test_equilibrium_no_components_no_change(self):
        """All nodes at ambient, no losses → temperatures unchanged."""
        model = _make_model(T_ambient=298.15, T_initial=298.15)
        model.update(dt=1.0)
        assert model.state.T_air == pytest.approx(298.15)

    def test_T_air_rises_with_battery_loss(self):
        """Battery generating heat raises T_air: step 1 heats battery, step 2 heat flows to air."""
        model = _make_model(T_ambient=298.15, T_initial=298.15)
        comp = _MockComponent(T=298.15, loss=1000.0, thermal_capacity=5000.0, thermal_resistance=0.05)
        model.add_component(comp)
        model.update(dt=1.0)  # battery heats up; no gradient to air yet
        model.update(dt=1.0)  # now T_bat > T_air → heat flows to air
        assert model.state.T_air > 298.15

    def test_T_bat_rises_with_loss(self):
        """Battery temperature increases when loss > 0."""
        model = _make_model(T_ambient=298.15, T_initial=298.15)
        comp = _MockComponent(T=298.15, loss=500.0, thermal_capacity=5000.0, thermal_resistance=0.1)
        model.add_component(comp)
        model.update(dt=1.0)
        assert comp.state.T > 298.15

    def test_outer_wall_moves_toward_ambient(self):
        """When T_initial > T_ambient the outer wall cools toward ambient."""
        model = _make_model(T_ambient=298.15, T_initial=350.0)
        T_out_before = 350.0
        model.update(dt=1.0)
        assert model.state.T_out < T_out_before

    def test_inner_wall_moves_toward_air(self):
        """With T_ambient << T_initial, heat drains out through all wall layers over time.

        The cooling cascade is: outer wall cools first (step 1), then mid wall (step 2),
        then inner wall (step 3+). Using FortyFtContainer (rock-wool insulation) whose
        explicit-Euler time constants are stable at dt=1 s.
        """
        from simses.model.thermal.containers import FortyFtContainer

        model = ContainerThermalModel(properties=FortyFtContainer, T_ambient=250.0, T_initial=350.0)
        T_in_before = 350.0
        for _ in range(300):
            model.update(dt=1.0)
        assert model.state.T_in < T_in_before

    def test_hvac_heating_raises_T_air(self):
        """HVAC in heating mode raises T_air above the no-HVAC baseline."""
        # Start cold: T_initial well below setpoint to trigger heating immediately
        T_sp = 298.15
        hvac = ThermostatStrategy(T_setpoint=T_sp, max_power=10000.0, hvac=ConstantCopHvac(), threshold=5.0)
        model_hvac = ContainerThermalModel(
            properties=_unit_box_container(), T_ambient=270.0, T_initial=280.0, hvac=hvac
        )
        model_no = ContainerThermalModel(properties=_unit_box_container(), T_ambient=270.0, T_initial=280.0, hvac=None)
        model_hvac.update(dt=10.0)
        model_no.update(dt=10.0)
        assert model_hvac.state.T_air > model_no.state.T_air

    def test_hvac_cooling_lowers_T_air(self):
        """HVAC in cooling mode lowers T_air below the no-HVAC baseline."""
        T_sp = 298.15
        hvac = ThermostatStrategy(T_setpoint=T_sp, max_power=10000.0, hvac=ConstantCopHvac(), threshold=5.0)
        model_hvac = ContainerThermalModel(
            properties=_unit_box_container(), T_ambient=320.0, T_initial=310.0, hvac=hvac
        )
        model_no = ContainerThermalModel(properties=_unit_box_container(), T_ambient=320.0, T_initial=310.0, hvac=None)
        model_hvac.update(dt=10.0)
        model_no.update(dt=10.0)
        assert model_hvac.state.T_air < model_no.state.T_air

    def test_exact_euler_step_battery(self):
        """Verify forward-Euler formula for battery node temperature."""
        T_bat0 = 310.0
        T_air0 = 298.15
        Q_loss = 200.0
        C_bat = 800.0
        R_bat = 0.1
        dt = 2.0

        dT_bat = Q_loss / C_bat - (T_bat0 - T_air0) / (R_bat * C_bat)
        T_bat_expected = T_bat0 + dT_bat * dt

        model = _make_model(T_ambient=298.15, T_initial=T_air0)
        comp = _MockComponent(T=T_bat0, loss=Q_loss, thermal_capacity=C_bat, thermal_resistance=R_bat)
        model.add_component(comp)
        model.update(dt=dt)

        assert comp.state.T == pytest.approx(T_bat_expected)

    def test_exact_euler_step_air(self):
        """Verify forward-Euler formula for air node (single battery, pre-step values)."""
        T_bat0 = 310.0
        T_air0 = 298.15
        T_in0 = 298.15
        Q_loss = 200.0
        R_bat = 0.1
        dt = 1.0

        props = _unit_box_container()
        A = props.A_surface  # 6 m²
        rho_air = 1.204
        cp_air = 1006.0
        C_air = rho_air * props.V_internal * cp_air

        R_in_air = 1.0 / (props.h_inner * A)

        Q_bat_to_air = (T_bat0 - T_air0) / R_bat
        Q_in_to_air = (T_in0 - T_air0) / R_in_air
        dT_air = (Q_bat_to_air + Q_in_to_air) / C_air
        T_air_expected = T_air0 + dT_air * dt

        model = ContainerThermalModel(properties=props, T_ambient=298.15, T_initial=T_air0)
        comp = _MockComponent(T=T_bat0, loss=Q_loss, thermal_capacity=5000.0, thermal_resistance=R_bat)
        model.add_component(comp)
        model.update(dt=dt)

        assert model.state.T_air == pytest.approx(T_air_expected)


# ===================================================================
# ContainerThermalModel — integration tests (real Battery)
# ===================================================================
class TestContainerThermalModelIntegration:
    def test_charging_heats_battery_and_air(self):
        """Charging creates loss → both T_bat and T_air rise over multiple steps.

        Uses FortyFtContainer and dt=1 s to stay within the explicit-Euler stability
        limit (τ_air ≈ 21 s for a 40-ft container).
        """
        bat = _make_battery(T=298.15, soc=0.5)
        model = ContainerThermalModel(
            properties=FortyFtContainer,
            T_ambient=298.15,
            T_initial=298.15,
        )
        model.add_component(bat)

        for _ in range(100):
            bat.update(power_setpoint=500.0, dt=1.0)
            model.update(dt=1.0)

        assert bat.state.T > 298.15
        assert model.state.T_air > 298.15

    def test_hot_battery_at_rest_cools_toward_air(self):
        """Hot battery with no power input cools toward T_air."""
        bat = _make_battery(T=320.0, soc=0.5)
        model = ContainerThermalModel(
            properties=_unit_box_container(),
            T_ambient=298.15,
            T_initial=298.15,
        )
        model.add_component(bat)

        bat.update(power_setpoint=0.0, dt=1.0)
        T_bat_before = bat.state.T
        model.update(dt=60.0)

        assert bat.state.T < T_bat_before

    def test_forty_ft_container_runs_without_error(self):
        bat = _make_battery(T=298.15, soc=0.5)
        model = ContainerThermalModel(
            properties=FortyFtContainer,
            T_ambient=298.15,
            T_initial=298.15,
        )
        model.add_component(bat)
        for _ in range(5):
            bat.update(power_setpoint=500.0, dt=60.0)
            model.update(dt=60.0)

    def test_twenty_ft_container_runs_without_error(self):
        bat = _make_battery(T=298.15, soc=0.5)
        model = ContainerThermalModel(
            properties=TwentyFtContainer,
            T_ambient=298.15,
            T_initial=298.15,
        )
        model.add_component(bat)
        for _ in range(5):
            bat.update(power_setpoint=500.0, dt=60.0)
            model.update(dt=60.0)

    def test_100_steps_physical_temperature_bounds(self):
        """Over 100 steps at dt=1 s, all temperatures remain physically plausible (200–400 K)."""
        bat = _make_battery(T=298.15, soc=0.5)
        model = ContainerThermalModel(
            properties=FortyFtContainer,
            T_ambient=298.15,
            T_initial=298.15,
        )
        model.add_component(bat)

        for _ in range(100):
            bat.update(power_setpoint=200.0, dt=1.0)
            model.update(dt=1.0)

        assert 200.0 < bat.state.T < 400.0
        assert 200.0 < model.state.T_air < 400.0
        assert 200.0 < model.state.T_in < 400.0
        assert 200.0 < model.state.T_mid < 400.0
        assert 200.0 < model.state.T_out < 400.0


# ===================================================================
# ThermostatStrategy — electrical power (COP model)
# ===================================================================
class TestThermostatStrategyPowerEl:
    def _make(self, T_setpoint=300.0, max_power=5000.0, cop_cooling=3.0, cop_heating=2.5):
        return ThermostatStrategy(
            T_setpoint=T_setpoint,
            max_power=max_power,
            hvac=ConstantCopHvac(cop_cooling=cop_cooling, cop_heating=cop_heating),
        )

    def test_power_el_zero_when_idle(self):
        t = self._make()
        _, P_el = t.control(T_air=300.0, dt=1.0)  # within band → idle
        assert P_el == pytest.approx(0.0)

    def test_power_el_heating(self):
        """Heating: P_el = max_power / cop_heating."""
        t = self._make(max_power=6000.0, cop_heating=2.5)
        _, P_el = t.control(T_air=290.0, dt=1.0)  # trigger heating
        assert P_el == pytest.approx(6000.0 / 2.5)

    def test_power_el_cooling(self):
        """Cooling: P_el = max_power / cop_cooling."""
        t = self._make(max_power=6000.0, cop_cooling=3.0)
        _, P_el = t.control(T_air=310.0, dt=1.0)  # trigger cooling
        assert P_el == pytest.approx(6000.0 / 3.0)

    def test_power_el_resets_to_zero_on_idle(self):
        """P_el drops to 0 once the unit returns to idle."""
        t = self._make(max_power=5000.0, cop_heating=2.5)
        _, P_el = t.control(T_air=290.0, dt=1.0)  # → HEATING, P_el > 0
        assert P_el > 0.0
        _, P_el = t.control(T_air=300.0, dt=1.0)  # → IDLE
        assert P_el == pytest.approx(0.0)

    def test_power_el_always_non_negative(self):
        """P_el is ≥ 0 in all modes."""
        t = self._make()
        for T in [285.0, 300.0, 315.0]:
            _, P_el = t.control(T_air=T, dt=1.0)
            assert P_el >= 0.0

    def test_custom_cop_values(self):
        """Custom COP values are respected independently for each mode."""
        cop_c, cop_h = 4.5, 3.2
        t = self._make(max_power=8000.0, cop_cooling=cop_c, cop_heating=cop_h)
        _, P_el = t.control(T_air=290.0, dt=1.0)  # → HEATING
        assert P_el == pytest.approx(8000.0 / cop_h)
        t.control(T_air=300.0, dt=1.0)  # → IDLE
        _, P_el = t.control(T_air=310.0, dt=1.0)  # → COOLING
        assert P_el == pytest.approx(8000.0 / cop_c)


# ===================================================================
# ContainerThermalModel — state.power_el
# ===================================================================
class TestContainerThermalModelPowerEl:
    def test_power_el_zero_without_hvac(self):
        model = _make_model(hvac=None)
        assert model.state.power_el == pytest.approx(0.0)
        model.update(dt=1.0)
        assert model.state.power_el == pytest.approx(0.0)

    def test_power_el_zero_when_hvac_idle(self):
        """HVAC within dead-band → power_el stays 0."""
        hvac = ThermostatStrategy(
            T_setpoint=298.15, max_power=5000.0, hvac=ConstantCopHvac(), threshold=5.0
        )
        model = _make_model(T_ambient=298.15, T_initial=298.15, hvac=hvac)
        model.update(dt=1.0)
        assert model.state.power_el == pytest.approx(0.0)

    def test_power_el_positive_when_heating(self):
        """HVAC in heating mode → model.state.power_el > 0."""
        cop_h = 2.5
        hvac = ThermostatStrategy(
            T_setpoint=300.0, max_power=5000.0, hvac=ConstantCopHvac(cop_heating=cop_h), threshold=5.0
        )
        # T_initial well below setpoint − threshold → heating triggered immediately
        model = _make_model(T_ambient=270.0, T_initial=280.0, hvac=hvac)
        model.update(dt=1.0)
        assert model.state.power_el == pytest.approx(5000.0 / cop_h)

    def test_power_el_positive_when_cooling(self):
        """HVAC in cooling mode → model.state.power_el > 0."""
        cop_c = 3.0
        hvac = ThermostatStrategy(
            T_setpoint=298.15, max_power=5000.0, hvac=ConstantCopHvac(cop_cooling=cop_c), threshold=5.0
        )
        # T_initial well above setpoint + threshold → cooling triggered immediately
        model = _make_model(T_ambient=320.0, T_initial=310.0, hvac=hvac)
        model.update(dt=1.0)
        assert model.state.power_el == pytest.approx(5000.0 / cop_c)

    def test_power_el_reflects_hvac_consumption(self):
        """model.state.power_el reflects the HVAC electrical consumption."""
        cop_h = 2.5
        hvac = ThermostatStrategy(
            T_setpoint=300.0, max_power=4000.0, hvac=ConstantCopHvac(cop_heating=cop_h), threshold=5.0
        )
        model = _make_model(T_ambient=270.0, T_initial=280.0, hvac=hvac)
        model.update(dt=1.0)
        assert model.state.power_el == pytest.approx(4000.0 / cop_h)
