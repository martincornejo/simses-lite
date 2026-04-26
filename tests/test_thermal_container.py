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
    __slots__ = ("T", "heat")

    def __init__(self, T: float, heat: float = 0.0):
        self.T = T
        self.heat = heat


class _MockComponent:
    def __init__(self, T: float, loss: float, thermal_capacity: float, thermal_resistance: float):
        self.state = _MockState(T=T, heat=loss)
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


def _make_model(T_ambient=25.0, T_initial=25.0, tms=None, hvac=None, properties=None):
    return ContainerThermalModel(
        properties=properties if properties is not None else _unit_box_container(),
        T_ambient=T_ambient,
        T_initial=T_initial,
        tms=tms if tms is not None else ThermostatStrategy(T_setpoint=25.0, max_power=0.0),
        hvac=hvac if hvac is not None else ConstantCopHvac(),
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
        assert FortyFtContainer().A_surface > 100.0

    def test_forty_ft_V_internal(self):
        expected = 12.0 * 2.3 * 2.35
        assert FortyFtContainer().V_internal == pytest.approx(expected)

    def test_twenty_ft_smaller_than_forty_ft(self):
        assert TwentyFtContainer().A_surface < FortyFtContainer().A_surface
        assert TwentyFtContainer().V_internal < FortyFtContainer().V_internal

    def test_u_bridge_factor_default(self):
        assert _unit_box_container().u_bridge_factor == pytest.approx(1.0)

    def test_u_bridge_factor_custom(self):
        layer = ContainerLayer(thickness=0.001, conductivity=237.0, density=2700.0, specific_heat=910.0)
        props = ContainerProperties(
            length=1.0,
            width=1.0,
            height=1.0,
            h_inner=10.0,
            h_outer=10.0,
            inner=layer,
            mid=layer,
            outer=layer,
            u_bridge_factor=3.0,
        )
        assert props.u_bridge_factor == pytest.approx(3.0)


# ===================================================================
# ThermostatStrategy
# ===================================================================
class TestThermostatStrategy:
    def _make(self, T_setpoint=300.0, max_power=5000.0, threshold=5.0):
        return ThermostatStrategy(T_setpoint=T_setpoint, max_power=max_power, threshold=threshold)

    # --- initial mode ---
    def test_starts_idle(self):
        t = self._make()
        assert t.mode is ThermostatMode.IDLE

    # --- idle within dead-band ---
    def test_idle_no_trigger_within_band(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q = t.control(T_ref=302.0, dt=1.0)
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_idle_lower_edge_no_trigger(self):
        """Exactly at lower edge (T_sp - threshold) should not trigger heating."""
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q = t.control(T_ref=295.0, dt=1.0)
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_idle_upper_edge_no_trigger(self):
        """Exactly at upper edge (T_sp + threshold) should not trigger cooling."""
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q = t.control(T_ref=305.0, dt=1.0)
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    # --- heating transitions ---
    def test_idle_triggers_heating_below_band(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q = t.control(T_ref=294.0, dt=1.0)
        assert Q == pytest.approx(5000.0)
        assert t.mode is ThermostatMode.HEATING

    def test_heating_stops_at_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_ref=290.0, dt=1.0)  # enter heating
        Q = t.control(T_ref=300.0, dt=1.0)  # at setpoint → idle
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_heating_continues_below_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_ref=290.0, dt=1.0)  # enter heating
        Q = t.control(T_ref=298.0, dt=1.0)  # still below setpoint
        assert Q == pytest.approx(5000.0)
        assert t.mode is ThermostatMode.HEATING

    # --- cooling transitions ---
    def test_idle_triggers_cooling_above_band(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        Q = t.control(T_ref=306.0, dt=1.0)
        assert Q == pytest.approx(-5000.0)
        assert t.mode is ThermostatMode.COOLING

    def test_cooling_stops_at_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_ref=310.0, dt=1.0)  # enter cooling
        Q = t.control(T_ref=300.0, dt=1.0)  # at setpoint → idle
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE

    def test_cooling_continues_above_setpoint(self):
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_ref=310.0, dt=1.0)  # enter cooling
        Q = t.control(T_ref=302.0, dt=1.0)  # still above setpoint
        assert Q == pytest.approx(-5000.0)
        assert t.mode is ThermostatMode.COOLING

    # --- hysteresis ---
    def test_no_cooling_trigger_inside_band_after_heating(self):
        """After heating stops, must not immediately trigger cooling."""
        t = self._make(T_setpoint=300.0, threshold=5.0)
        t.control(T_ref=290.0, dt=1.0)  # → HEATING
        t.control(T_ref=300.0, dt=1.0)  # → IDLE at setpoint
        Q = t.control(T_ref=303.0, dt=1.0)  # inside band, should stay IDLE
        assert Q == pytest.approx(0.0)
        assert t.mode is ThermostatMode.IDLE


# ===================================================================
# ContainerThermalModel — unit tests (mock components)
# ===================================================================
class TestContainerThermalModelUnit:
    def test_equilibrium_no_components_no_change(self):
        """All nodes at ambient, no losses → temperatures unchanged."""
        model = _make_model(T_ambient=25.0, T_initial=25.0)
        model.step(dt=1.0)
        assert model.state.T_air == pytest.approx(25.0)

    def test_T_air_rises_with_battery_loss(self):
        """Battery generating heat raises T_air: step 1 heats battery, step 2 heat flows to air."""
        model = _make_model(T_ambient=25.0, T_initial=25.0)
        comp = _MockComponent(T=25.0, loss=1000.0, thermal_capacity=5000.0, thermal_resistance=0.05)
        model.add_component(comp)
        model.step(dt=1.0)  # battery heats up; no gradient to air yet
        model.step(dt=1.0)  # now T_bat > T_air → heat flows to air
        assert model.state.T_air > 25.0

    def test_T_bat_rises_with_loss(self):
        """Battery temperature increases when loss > 0."""
        model = _make_model(T_ambient=25.0, T_initial=25.0)
        comp = _MockComponent(T=25.0, loss=500.0, thermal_capacity=5000.0, thermal_resistance=0.1)
        model.add_component(comp)
        model.step(dt=1.0)
        assert comp.state.T > 25.0

    def test_outer_wall_moves_toward_ambient(self):
        """When T_initial > T_ambient the outer wall cools toward ambient."""
        model = _make_model(T_ambient=25.0, T_initial=77.0)
        T_out_before = 77.0
        model.step(dt=1.0)
        assert model.state.T_out < T_out_before

    def test_inner_wall_moves_toward_air(self):
        """With T_ambient << T_initial, heat drains out through all wall layers over time.

        The cooling cascade is: outer wall cools first (step 1), then mid wall (step 2),
        then inner wall (step 3+). Using FortyFtContainer (rock-wool insulation) whose
        explicit-Euler time constants are stable at dt=1 s.
        """
        from simses.model.thermal.containers import FortyFtContainer

        model = _make_model(properties=FortyFtContainer(), T_ambient=-23.0, T_initial=77.0)
        T_in_before = 350.0
        for _ in range(300):
            model.step(dt=1.0)
        assert model.state.T_in < T_in_before

    def test_hvac_heating_raises_T_air(self):
        """HVAC in heating mode raises T_air above the no-HVAC baseline."""
        # Start cold: T_initial well below setpoint to trigger heating immediately
        T_sp = 25.0
        tms = ThermostatStrategy(T_setpoint=T_sp, max_power=10000.0, threshold=5.0)
        hvac = ConstantCopHvac()
        model_hvac = _make_model(T_ambient=-3.0, T_initial=7.0, tms=tms, hvac=hvac)
        model_no = _make_model(T_ambient=-3.0, T_initial=7.0)
        model_hvac.step(dt=10.0)
        model_no.step(dt=10.0)
        assert model_hvac.state.T_air > model_no.state.T_air

    def test_hvac_cooling_lowers_T_air(self):
        """HVAC in cooling mode lowers T_air below the no-HVAC baseline."""
        T_sp = 25.0
        tms = ThermostatStrategy(T_setpoint=T_sp, max_power=10000.0, threshold=5.0)
        hvac = ConstantCopHvac()
        model_hvac = _make_model(T_ambient=47.0, T_initial=37.0, tms=tms, hvac=hvac)
        model_no = _make_model(T_ambient=47.0, T_initial=37.0)
        model_hvac.step(dt=10.0)
        model_no.step(dt=10.0)
        assert model_hvac.state.T_air < model_no.state.T_air

    def test_exact_euler_step_battery(self):
        """Verify forward-Euler formula for battery node temperature."""
        T_bat0 = 37.0
        T_air0 = 25.0
        Q_loss = 200.0
        C_bat = 800.0
        R_bat = 0.1
        dt = 2.0

        dT_bat = Q_loss / C_bat - (T_bat0 - T_air0) / (R_bat * C_bat)
        T_bat_expected = T_bat0 + dT_bat * dt

        model = _make_model(T_ambient=25.0, T_initial=T_air0)
        comp = _MockComponent(T=T_bat0, loss=Q_loss, thermal_capacity=C_bat, thermal_resistance=R_bat)
        model.add_component(comp)
        model.step(dt=dt)

        assert comp.state.T == pytest.approx(T_bat_expected)

    def test_u_bridge_factor_reduces_mid_layer_resistance(self):
        """u_bridge_factor halves r_mid so T_mid cools faster once T_out–T_mid gradient builds.

        Step 1: all wall nodes equal T_initial → dT_mid = 0 for both models.
        Step 2: T_out fell in step 1 → non-zero T_out–T_mid gradient; model with
        u_bridge_factor=2 has half the R_out_mid and therefore a larger drop in T_mid.
        """
        metal = ContainerLayer(thickness=0.001, conductivity=237.0, density=2700.0, specific_heat=910.0)
        insulation = ContainerLayer(thickness=0.05, conductivity=0.05, density=100.0, specific_heat=840.0)

        def _make_props(u: float) -> ContainerProperties:
            return ContainerProperties(
                length=6.0,
                width=2.5,
                height=2.5,
                h_inner=30.0,
                h_outer=30.0,
                inner=metal,
                mid=insulation,
                outer=metal,
                u_bridge_factor=u,
            )

        T_initial, T_amb = 50.0, 20.0
        model1 = _make_model(properties=_make_props(1.0), T_ambient=T_amb, T_initial=T_initial)
        model2 = _make_model(properties=_make_props(2.0), T_ambient=T_amb, T_initial=T_initial)

        # Step 1: T_out drops toward ambient; T_mid unchanged (T_out == T_mid initially → zero flux)
        model1.step(dt=1.0)
        model2.step(dt=1.0)
        assert model1.state.T_mid == pytest.approx(T_initial)
        assert model2.state.T_mid == pytest.approx(T_initial)

        # Step 2: T_out < T_mid now → heat drains from T_mid; model2 drains more (halved R_out_mid)
        model1.step(dt=1.0)
        model2.step(dt=1.0)
        assert model2.state.T_mid < model1.state.T_mid

    def test_exact_euler_step_air(self):
        """Verify forward-Euler formula for air node (single battery, pre-step values)."""
        T_bat0 = 37.0
        T_air0 = 25.0
        T_in0 = 25.0
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

        model = _make_model(properties=props, T_ambient=25.0, T_initial=T_air0)
        comp = _MockComponent(T=T_bat0, loss=Q_loss, thermal_capacity=5000.0, thermal_resistance=R_bat)
        model.add_component(comp)
        model.step(dt=dt)

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
        bat = _make_battery(T=25.0, soc=0.5)
        model = _make_model(properties=FortyFtContainer())
        model.add_component(bat)

        for _ in range(100):
            bat.step(power_setpoint=500.0, dt=1.0)
            model.step(dt=1.0)

        assert bat.state.T > 25.0
        assert model.state.T_air > 25.0

    def test_hot_battery_at_rest_cools_toward_air(self):
        """Hot battery with no power input cools toward T_air."""
        bat = _make_battery(T=47.0, soc=0.5)
        model = _make_model()
        model.add_component(bat)

        bat.step(power_setpoint=0.0, dt=1.0)
        T_bat_before = bat.state.T
        model.step(dt=60.0)

        assert bat.state.T < T_bat_before

    def test_forty_ft_container_runs_without_error(self):
        bat = _make_battery(T=25.0, soc=0.5)
        model = _make_model(properties=FortyFtContainer())
        model.add_component(bat)
        for _ in range(5):
            bat.step(power_setpoint=500.0, dt=60.0)
            model.step(dt=60.0)

    def test_twenty_ft_container_runs_without_error(self):
        bat = _make_battery(T=25.0, soc=0.5)
        model = _make_model(properties=TwentyFtContainer())
        model.add_component(bat)
        for _ in range(5):
            bat.step(power_setpoint=500.0, dt=60.0)
            model.step(dt=60.0)

    def test_100_steps_physical_temperature_bounds(self):
        """Over 100 steps at dt=1 s, all temperatures remain physically plausible (-100–200 °C)."""
        bat = _make_battery(T=25.0, soc=0.5)
        model = _make_model(properties=FortyFtContainer())
        model.add_component(bat)

        for _ in range(100):
            bat.step(power_setpoint=200.0, dt=1.0)
            model.step(dt=1.0)

        assert -100 < bat.state.T < 200
        assert -100 < model.state.T_air < 200
        assert -100 < model.state.T_in < 200
        assert -100 < model.state.T_mid < 200
        assert -100 < model.state.T_out < 200


# ===================================================================
# ConstantCopHvac — electrical consumption model
# ===================================================================
class TestConstantCopHvac:
    def test_zero_thermal_gives_zero_electrical(self):
        hvac = ConstantCopHvac()
        assert hvac.electrical_consumption(0.0) == pytest.approx(0.0)

    def test_heating_consumption(self):
        """Heating (Q > 0): P_el = Q / cop_heating."""
        hvac = ConstantCopHvac(cop_heating=2.5)
        assert hvac.electrical_consumption(6000.0) == pytest.approx(6000.0 / 2.5)

    def test_cooling_consumption(self):
        """Cooling (Q < 0): P_el = |Q| / cop_cooling."""
        hvac = ConstantCopHvac(cop_cooling=3.0)
        assert hvac.electrical_consumption(-6000.0) == pytest.approx(6000.0 / 3.0)

    def test_always_non_negative(self):
        """P_el is ≥ 0 for any thermal power."""
        hvac = ConstantCopHvac()
        for Q in [-5000.0, 0.0, 5000.0]:
            assert hvac.electrical_consumption(Q) >= 0.0

    def test_custom_cop_values(self):
        """Custom COP values are respected independently for each direction."""
        cop_c, cop_h = 4.5, 3.2
        hvac = ConstantCopHvac(cop_cooling=cop_c, cop_heating=cop_h)
        assert hvac.electrical_consumption(8000.0) == pytest.approx(8000.0 / cop_h)
        assert hvac.electrical_consumption(-8000.0) == pytest.approx(8000.0 / cop_c)


# ===================================================================
# ContainerThermalModel — state.power_el
# ===================================================================
class TestContainerThermalModelPowerEl:
    def test_power_el_zero_without_hvac(self):
        model = _make_model()  # no-op tms/hvac → Q=0 → P_el=0
        assert model.state.power_el == pytest.approx(0.0)
        model.step(dt=1.0)
        assert model.state.power_el == pytest.approx(0.0)

    def test_power_el_zero_when_hvac_idle(self):
        """HVAC within dead-band → power_el stays 0."""
        tms = ThermostatStrategy(T_setpoint=25.0, max_power=5000.0, threshold=5.0)
        hvac = ConstantCopHvac()
        model = _make_model(T_ambient=25.0, T_initial=25.0, tms=tms, hvac=hvac)
        model.step(dt=1.0)
        assert model.state.power_el == pytest.approx(0.0)

    def test_power_el_positive_when_heating(self):
        """HVAC in heating mode → model.state.power_el > 0."""
        cop_h = 2.5
        tms = ThermostatStrategy(T_setpoint=27.0, max_power=5000.0, threshold=5.0)
        hvac = ConstantCopHvac(cop_heating=cop_h)
        # T_initial well below setpoint − threshold → heating triggered immediately
        model = _make_model(T_ambient=-3.0, T_initial=7.0, tms=tms, hvac=hvac)
        model.step(dt=1.0)
        assert model.state.power_el == pytest.approx(5000.0 / cop_h)

    def test_power_el_positive_when_cooling(self):
        """HVAC in cooling mode → model.state.power_el > 0."""
        cop_c = 3.0
        tms = ThermostatStrategy(T_setpoint=25.0, max_power=5000.0, threshold=5.0)
        hvac = ConstantCopHvac(cop_cooling=cop_c)
        # T_initial well above setpoint + threshold → cooling triggered immediately
        model = _make_model(T_ambient=47.0, T_initial=37.0, tms=tms, hvac=hvac)
        model.step(dt=1.0)
        assert model.state.power_el == pytest.approx(5000.0 / cop_c)

    def test_power_el_reflects_hvac_consumption(self):
        """model.state.power_el reflects the HVAC electrical consumption."""
        cop_h = 2.5
        tms = ThermostatStrategy(T_setpoint=27.0, max_power=4000.0, threshold=5.0)
        hvac = ConstantCopHvac(cop_heating=cop_h)
        model = _make_model(T_ambient=-3.0, T_initial=7.0, tms=tms, hvac=hvac)
        model.step(dt=1.0)
        assert model.state.power_el == pytest.approx(4000.0 / cop_h)
