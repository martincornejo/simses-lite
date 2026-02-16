"""Unit tests for the Battery model."""

import pytest

from simses.battery.battery import Battery
from simses.battery.cell import CellType
from simses.battery.format import PrismaticCell
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties
from simses.battery.state import BatteryState


# ---------------------------------------------------------------------------
# Minimal concrete CellType for testing (simple linear OCV, constant Rint)
# ---------------------------------------------------------------------------
class SimpleCell(CellType):
    """Cell with linear OCV(soc) = min_v + soc * (max_v - min_v) and constant Rint."""

    RINT = 1e-3  # 1 mΩ

    def __init__(self, **electrical_overrides):
        defaults = dict(
            nominal_capacity=100.0,  # Ah
            nominal_voltage=3.6,  # V
            min_voltage=3.0,  # V
            max_voltage=4.2,  # V
            max_charge_rate=1.0,  # C
            max_discharge_rate=1.0,  # C
        )
        defaults.update(electrical_overrides)
        super().__init__(
            electrical=ElectricalCellProperties(**defaults),
            thermal=ThermalCellProperties(
                min_temperature=233.15,
                max_temperature=333.15,
                mass=1.0,
                specific_heat=1000.0,
                convection_coefficient=10.0,
            ),
            cell_format=PrismaticCell(height=100, width=30, length=150),
        )

    def open_circuit_voltage(self, state: BatteryState) -> float:
        return self.electrical.min_voltage + state.soc * (self.electrical.max_voltage - self.electrical.min_voltage)

    def internal_resistance(self, state: BatteryState) -> float:
        return self.RINT


def _make_battery(circuit=(1, 1), soc=0.5, T=298.15, soc_limits=(0.0, 1.0), **cell_kw) -> Battery:
    """Helper to create a Battery with the SimpleCell."""
    return Battery(
        cell=SimpleCell(**cell_kw),
        circuit=circuit,
        initial_states={"start_soc": soc, "start_T": T},
        soc_limits=soc_limits,
    )


# ===================================================================
# Initialization
# ===================================================================
class TestBatteryInitialization:
    def test_initial_soc(self):
        bat = _make_battery(soc=0.8)
        assert bat.state.soc == 0.8

    def test_initial_temperature(self):
        bat = _make_battery(T=310.0)
        assert bat.state.T == 310.0

    def test_initial_soh_defaults(self):
        bat = _make_battery()
        assert bat.state.soh_Q == 1.0
        assert bat.state.soh_R == 1.0

    def test_initial_ocv_matches_cell(self):
        bat = _make_battery(soc=0.5)
        expected_ocv = 3.0 + 0.5 * (4.2 - 3.0)  # 3.6
        assert bat.state.ocv == pytest.approx(expected_ocv)

    def test_initial_rint(self):
        bat = _make_battery(soc=0.5)
        assert bat.state.rint == pytest.approx(SimpleCell.RINT)


# ===================================================================
# Nominal / system-level properties (scaling with circuit)
# ===================================================================
class TestBatteryProperties:
    def test_nominal_capacity_parallel(self):
        bat = _make_battery(circuit=(1, 3))
        assert bat.nominal_capacity == pytest.approx(300.0)

    def test_voltage_serial(self):
        bat = _make_battery(circuit=(4, 1))
        assert bat.nominal_voltage == pytest.approx(4 * 3.6)

    def test_nominal_energy_capacity(self):
        bat = _make_battery(circuit=(2, 2))
        assert bat.nominal_energy_capacity == pytest.approx(2 * 100.0 * 2 * 3.6)

    def test_min_voltage_serial(self):
        bat = _make_battery(circuit=(3, 1))
        assert bat.min_voltage == pytest.approx(3 * 3.0)

    def test_max_voltage_serial(self):
        bat = _make_battery(circuit=(3, 1))
        assert bat.max_voltage == pytest.approx(3 * 4.2)

    def test_max_charge_current_parallel(self):
        bat = _make_battery(circuit=(1, 2))
        # max_discharge_rate * nominal_capacity * parallel (note: max_charge uses max_discharge_rate in code)
        assert bat.max_charge_current == pytest.approx(1.0 * 100.0 * 2)

    def test_max_discharge_current_parallel(self):
        bat = _make_battery(circuit=(1, 2))
        assert bat.max_discharge_current == pytest.approx(1.0 * 100.0 * 2)

    def test_internal_resistance_scaling(self):
        bat = _make_battery(circuit=(4, 2), soc=0.5)
        # cell rint * serial / parallel * soh_R
        expected = SimpleCell.RINT * 4 / 2 * 1.0
        assert bat.internal_resistance(bat.state) == pytest.approx(expected)

    def test_internal_resistance_soh(self):
        bat = _make_battery(circuit=(1, 1), soc=0.5)
        bat.state.soh_R = 1.5
        expected = SimpleCell.RINT * 1.5
        assert bat.internal_resistance(bat.state) == pytest.approx(expected)

    def test_capacity_soh(self):
        bat = _make_battery(circuit=(1, 1))
        bat.state.soh_Q = 0.8
        assert bat.capacity(bat.state) == pytest.approx(100.0 * 0.8)

    def test_ocv_scaling_serial(self):
        bat = _make_battery(circuit=(3, 1), soc=0.5)
        cell_ocv = 3.0 + 0.5 * 1.2  # 3.6
        assert bat.open_circuit_voltage(bat.state) == pytest.approx(3 * cell_ocv)


# ===================================================================
# Equilibrium current calculation
# ===================================================================
class TestEquilibriumCurrent:
    def test_zero_power_returns_zero(self):
        bat = _make_battery(soc=0.5)
        i = bat.equilibrium_current(bat.state, 0.0, dt=1.0)
        assert i == 0.0

    def test_current_limited_by_c_rate_charge(self):
        """A very high charge power should be clamped by the C-rate limit."""
        bat = _make_battery(soc=0.5)
        i = bat.equilibrium_current(bat.state, 1e6, dt=3600.0)
        assert i <= bat.max_charge_current + 1e-9

    def test_current_limited_by_c_rate_discharge(self):
        """A high discharge power should be clamped by the C-rate limit."""
        bat = _make_battery(soc=0.5)
        i = bat.equilibrium_current(bat.state, -2000.0, dt=3600.0)
        assert i >= -bat.max_discharge_current - 1e-9

    def test_current_limited_by_soc_max(self):
        """Near SOC=1 with limited dt, the SOC limit should constrain the current."""
        bat = _make_battery(soc=0.99, soc_limits=(0.0, 1.0))
        dt = 1.0  # 1 second
        i = bat.equilibrium_current(bat.state, 1e6, dt=dt)
        Q = bat.capacity(bat.state)
        # i * dt / Q / 3600 should not push soc above 1.0
        delta_soc = i * dt / Q / 3600
        assert bat.state.soc + delta_soc <= 1.0 + 1e-9

    def test_current_limited_by_soc_min(self):
        bat = _make_battery(soc=0.01, soc_limits=(0.0, 1.0))
        dt = 3600.0
        i = bat.equilibrium_current(bat.state, -500.0, dt=dt)
        Q = bat.capacity(bat.state)
        delta_soc = i * dt / Q / 3600
        assert bat.state.soc + delta_soc >= 0.0 - 1e-9

    def test_current_limited_by_voltage_max(self):
        """At high SOC the OCV is near max_voltage, so voltage limit should kick in."""
        bat = _make_battery(soc=0.99)
        i = bat.equilibrium_current(bat.state, 1e6, dt=3600.0)
        ocv = bat.open_circuit_voltage(bat.state)
        hys = bat.hystheresis_voltage(bat.state)
        rint = bat.internal_resistance(bat.state)
        v_terminal = ocv + hys + rint * i
        assert v_terminal <= bat.max_voltage + 1e-6

    def test_current_limited_by_voltage_min(self):
        bat = _make_battery(soc=0.01)
        i = bat.equilibrium_current(bat.state, -1000.0, dt=1.0)
        ocv = bat.open_circuit_voltage(bat.state)
        hys = bat.hystheresis_voltage(bat.state)
        rint = bat.internal_resistance(bat.state)
        v_terminal = ocv + hys + rint * i
        assert v_terminal >= bat.min_voltage - 1e-6

    def test_power_equilibrium(self):
        """The returned current should approximately satisfy p = v * i when no limits are hit."""
        bat = _make_battery(soc=0.5)
        p_set = 10.0  # small enough that no limit constrains the current
        i = bat.equilibrium_current(bat.state, p_set, dt=1.0)
        ocv = bat.open_circuit_voltage(bat.state)
        rint = bat.internal_resistance(bat.state)
        v = ocv + rint * i
        p_actual = v * i
        assert p_actual == pytest.approx(p_set, rel=1e-6)

    def test_custom_soc_limits(self):
        """SOC limits narrower than 0-1 should be respected."""
        bat = _make_battery(soc=0.89, soc_limits=(0.1, 0.9))
        dt = 1.0
        i = bat.equilibrium_current(bat.state, 1e6, dt=dt)
        Q = bat.capacity(bat.state)
        delta_soc = i * dt / Q / 3600
        assert bat.state.soc + delta_soc <= 0.9 + 1e-9


# ===================================================================
# Update method
# ===================================================================
class TestBatteryUpdate:
    def test_soc_increases_on_charge(self):
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=100.0, dt=60.0)
        assert bat.state.soc > 0.5

    def test_soc_decreases_on_discharge(self):
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=-100.0, dt=60.0)
        assert bat.state.soc < 0.5

    def test_soc_clamped_at_max(self):
        bat = _make_battery(soc=0.999, soc_limits=(0.0, 1.0))
        bat.update(power_setpoint=1e6, dt=3600.0)
        assert bat.state.soc <= 1.0

    def test_soc_clamped_at_min(self):
        bat = _make_battery(soc=0.001, soc_limits=(0.0, 1.0))
        bat.update(power_setpoint=-500.0, dt=3600.0)
        assert bat.state.soc >= 0.0

    def test_voltage_within_limits_charge(self):
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=1e6, dt=60.0)
        assert bat.state.v <= bat.max_voltage + 1e-6

    def test_voltage_within_limits_discharge(self):
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=-2000.0, dt=60.0)
        assert bat.state.v >= bat.min_voltage - 1e-6

    def test_rest_preserves_is_charge(self):
        bat = _make_battery(soc=0.5)
        bat.state.is_charge = False
        bat.update(power_setpoint=0.0, dt=60.0)
        # is_charge should stay False when at rest
        assert bat.state.is_charge is False

    def test_loss_is_positive(self):
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=200.0, dt=60.0)
        assert bat.state.loss >= 0.0

    def test_power_setpoint_stored(self):
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=123.0, dt=60.0)
        assert bat.state.power_setpoint == 123.0

    def test_zero_power_no_soc_change(self):
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=0.0, dt=60.0)
        assert bat.state.soc == 0.5
        assert bat.state.i == 0.0

    def test_multiple_updates_monotonic_charge(self):
        bat = _make_battery(soc=0.1)
        socs = [bat.state.soc]
        for _ in range(10):
            bat.update(power_setpoint=50.0, dt=60.0)
            socs.append(bat.state.soc)
        assert all(s2 >= s1 for s1, s2 in zip(socs, socs[1:]))


# ===================================================================
# Voltage derating
# ===================================================================
class TestVoltageDerating:
    """Tests for the optional linear voltage derating feature, verified via update()."""

    def _make_derate_battery(self, soc=0.5, charge_derate=None, discharge_derate=None):
        kw = {}
        if charge_derate is not None:
            kw["charge_derate_voltage_start"] = charge_derate
        if discharge_derate is not None:
            kw["discharge_derate_voltage_start"] = discharge_derate
        return _make_battery(soc=soc, **kw)

    # --- derating disabled by default ---
    def test_no_derating_by_default(self):
        bat = _make_battery(soc=0.5)
        assert bat.charge_derate_voltage_start is None
        assert bat.discharge_derate_voltage_start is None

    def test_no_derating_same_as_baseline(self):
        """Without derating configured, behaviour is identical to a plain battery."""
        bat = _make_battery(soc=0.9)
        bat.update(power_setpoint=1e4, dt=60.0)
        bat_no = _make_battery(soc=0.9)
        bat_no.update(power_setpoint=1e4, dt=60.0)
        assert bat.state.i == pytest.approx(bat_no.state.i)
        assert bat.state.v == pytest.approx(bat_no.state.v)

    # --- charge derating ---
    def test_charge_derate_reduces_current_vs_no_derate(self):
        """With charge derating at high SOC, charging current is lower than without."""
        dt = 60.0
        p = 1e4

        bat_no = _make_battery(soc=0.9)
        bat_no.update(power_setpoint=p, dt=dt)

        bat_dr = self._make_derate_battery(soc=0.9, charge_derate=4.0)
        bat_dr.update(power_setpoint=p, dt=dt)

        assert bat_dr.state.i <= bat_no.state.i + 1e-12
        assert bat_dr.state.i >= 0  # still charging or zero

    def test_charge_derate_voltage_stays_below_max(self):
        """After update with derating, terminal voltage should not exceed max."""
        bat = self._make_derate_battery(soc=0.95, charge_derate=4.0)
        bat.update(power_setpoint=1e6, dt=60.0)
        assert bat.state.v <= bat.max_voltage + 1e-6

    def test_charge_derate_no_effect_at_low_soc(self):
        """At low SOC the terminal voltage is well below the derate threshold, so no reduction."""
        dt = 60.0
        p = 100.0

        bat_no = _make_battery(soc=0.3)
        bat_no.update(power_setpoint=p, dt=dt)

        bat_dr = self._make_derate_battery(soc=0.3, charge_derate=4.0)
        bat_dr.update(power_setpoint=p, dt=dt)

        assert bat_dr.state.i == pytest.approx(bat_no.state.i, rel=1e-9)
        assert bat_dr.state.soc == pytest.approx(bat_no.state.soc, rel=1e-9)

    def test_charge_derate_reduces_soc_gain(self):
        """With derating active, less energy is accepted → SOC increases less."""
        dt = 60.0
        p = 1e4

        bat_no = _make_battery(soc=0.9)
        bat_no.update(power_setpoint=p, dt=dt)

        bat_dr = self._make_derate_battery(soc=0.9, charge_derate=4.0)
        bat_dr.update(power_setpoint=p, dt=dt)

        assert bat_dr.state.soc <= bat_no.state.soc + 1e-12

    def test_charge_derate_power_reduced(self):
        """Actual power delivered should be less with derating active at high SOC."""
        dt = 60.0
        p = 1e4

        bat_no = _make_battery(soc=0.9)
        bat_no.update(power_setpoint=p, dt=dt)

        bat_dr = self._make_derate_battery(soc=0.9, charge_derate=4.0)
        bat_dr.update(power_setpoint=p, dt=dt)

        assert bat_dr.state.power <= bat_no.state.power + 1e-6

    # --- discharge derating ---
    def test_discharge_derate_reduces_current_vs_no_derate(self):
        """With discharge derating at low SOC, discharge current magnitude is smaller."""
        dt = 60.0
        p = -2000.0

        bat_no = _make_battery(soc=0.1)
        bat_no.update(power_setpoint=p, dt=dt)

        bat_dr = self._make_derate_battery(soc=0.1, discharge_derate=3.2)
        bat_dr.update(power_setpoint=p, dt=dt)

        # discharge current is negative; derated should be less negative (closer to 0)
        assert bat_dr.state.i >= bat_no.state.i - 1e-12
        assert bat_dr.state.i <= 0  # still discharging or zero

    def test_discharge_derate_voltage_stays_above_min(self):
        """After update with derating, terminal voltage should not drop below min."""
        bat = self._make_derate_battery(soc=0.05, discharge_derate=3.2)
        bat.update(power_setpoint=-2000.0, dt=60.0)
        assert bat.state.v >= bat.min_voltage - 1e-6

    def test_discharge_derate_no_effect_at_high_soc(self):
        """At high SOC the terminal voltage is above the derate threshold, so no reduction."""
        dt = 60.0
        p = -100.0

        bat_no = _make_battery(soc=0.7)
        bat_no.update(power_setpoint=p, dt=dt)

        bat_dr = self._make_derate_battery(soc=0.7, discharge_derate=3.2)
        bat_dr.update(power_setpoint=p, dt=dt)

        assert bat_dr.state.i == pytest.approx(bat_no.state.i, rel=1e-9)
        assert bat_dr.state.soc == pytest.approx(bat_no.state.soc, rel=1e-9)

    def test_discharge_derate_reduces_soc_drop(self):
        """With derating active, less energy is extracted → SOC decreases less."""
        dt = 60.0
        p = -2000.0

        bat_no = _make_battery(soc=0.1)
        bat_no.update(power_setpoint=p, dt=dt)

        bat_dr = self._make_derate_battery(soc=0.1, discharge_derate=3.2)
        bat_dr.update(power_setpoint=p, dt=dt)

        assert bat_dr.state.soc >= bat_no.state.soc - 1e-12

    # --- zero power ---
    def test_zero_power_unaffected_by_derating(self):
        bat = self._make_derate_battery(soc=0.5, charge_derate=4.0, discharge_derate=3.2)
        bat.update(power_setpoint=0.0, dt=60.0)
        assert bat.state.i == 0.0
        assert bat.state.soc == 0.5


# ===================================================================
# Edge cases
# ===================================================================
class TestEdgeCases:
    def test_single_cell_circuit(self):
        bat = _make_battery(circuit=(1, 1), soc=0.5)
        assert bat.nominal_capacity == 100.0
        assert bat.nominal_voltage == pytest.approx(3.6)

    def test_large_circuit(self):
        bat = _make_battery(circuit=(100, 50), soc=0.5)
        assert bat.nominal_capacity == pytest.approx(100.0 * 50)
        assert bat.nominal_voltage == pytest.approx(3.6 * 100)

    def test_soc_at_zero(self):
        bat = _make_battery(soc=0.0)
        assert bat.state.soc == 0.0
        ocv = bat.open_circuit_voltage(bat.state)
        assert ocv == pytest.approx(3.0)  # min voltage

    def test_soc_at_one(self):
        bat = _make_battery(soc=1.0)
        assert bat.state.soc == 1.0
        ocv = bat.open_circuit_voltage(bat.state)
        assert ocv == pytest.approx(4.2)  # max voltage

    def test_degraded_soh(self):
        bat = _make_battery(soc=0.5)
        bat.state.soh_Q = 0.8
        bat.state.soh_R = 1.2
        assert bat.capacity(bat.state) == pytest.approx(100.0 * 0.8)
        assert bat.internal_resistance(bat.state) == pytest.approx(SimpleCell.RINT * 1.2)
