"""Unit tests for the Converter class."""

import pytest

from simses.converter.converter import Converter, ConverterState
from simses.model.converter.fix_efficiency import FixedEfficiency

# Import test utilities from test_battery
from tests.test_battery import _make_battery


def _make_converter(max_power, effc=0.95, effd=None, circuit=(10, 1), soc=0.5, **battery_kw):
    """Helper to create a Converter with FixedEfficiency and SimpleCell battery."""
    battery = _make_battery(circuit=circuit, soc=soc, **battery_kw)
    model = FixedEfficiency(effc=effc, effd=effd)
    return Converter(loss_model=model, max_power=max_power, storage=battery)


# ===================================================================
# Converter initialization
# ===================================================================
class TestConverterInitialization:
    def test_initial_state(self):
        """Converter should initialize with zero state."""
        conv = _make_converter(max_power=1000.0)

        assert conv.state.power_setpoint == 0.0
        assert conv.state.power == 0.0
        assert conv.state.loss == 0.0

    def test_max_power_stored(self):
        """Max power should be stored correctly."""
        conv = _make_converter(max_power=500.0)

        assert conv.max_power == 500.0

    def test_model_stored(self):
        """Loss model should be stored correctly."""
        conv = _make_converter(max_power=1000.0)

        assert conv.model is not None


# ===================================================================
# Power limiting
# ===================================================================
class TestConverterPowerLimiting:
    def test_power_within_limit(self):
        """Power below max should not be limited."""
        conv = _make_converter(max_power=1000.0)

        conv.update(power_setpoint=500.0, dt=1.0)

        assert conv.state.power == pytest.approx(500.0, abs=1e-6)

    def test_power_exceeds_max_charge(self):
        """Charge power exceeding max should be clamped."""
        conv = _make_converter(max_power=1000.0)

        conv.update(power_setpoint=5000.0, dt=1.0)

        assert conv.state.power == pytest.approx(1000.0, abs=1e-6)

    def test_power_exceeds_max_discharge(self):
        """Discharge power exceeding max should be clamped."""
        conv = _make_converter(max_power=1000.0)

        conv.update(power_setpoint=-5000.0, dt=1.0)

        assert conv.state.power == pytest.approx(-1000.0, abs=1e-6)


# ===================================================================
# Storage interaction and power adjustment
# ===================================================================
class TestConverterStorageInteraction:
    def test_battery_soc_increases_on_charge(self):
        """Charging through converter should increase battery SOC."""
        conv = _make_converter(max_power=1000.0)

        soc_before = conv.storage.state.soc
        conv.update(power_setpoint=1000.0, dt=60.0)

        assert conv.storage.state.soc > soc_before

    def test_battery_soc_decreases_on_discharge(self):
        """Discharging through converter should decrease battery SOC."""
        conv = _make_converter(max_power=1000.0)

        soc_before = conv.storage.state.soc
        conv.update(power_setpoint=-1000.0, dt=60.0)

        assert conv.storage.state.soc < soc_before

    def test_battery_fulfills_power_request(self):
        """When battery can fulfill power, no re-calculation needed."""
        conv = _make_converter(max_power=1000.0)

        conv.update(power_setpoint=100.0, dt=1.0)

        # AC power should match setpoint (within limits)
        assert conv.state.power == pytest.approx(100.0, abs=1e-6)

    def test_battery_cannot_fulfill_at_high_soc(self):
        """At high SOC, battery may not accept full charge power."""
        conv = _make_converter(max_power=1000.0, soc=0.99, soc_limits=(0.0, 1.0))

        conv.update(power_setpoint=5000.0, dt=10.0)

        # Converter should recalculate based on what battery actually accepted
        # Power should be less than setpoint
        assert conv.state.power < 5000.0

    def test_battery_cannot_fulfill_at_low_soc(self):
        """At low SOC, battery may not provide full discharge power."""
        conv = _make_converter(max_power=1000.0, soc=0.01, soc_limits=(0.0, 1.0))

        conv.update(power_setpoint=-5000.0, dt=10.0)

        # Converter should recalculate based on what battery actually delivered
        # Power magnitude should be less than setpoint magnitude
        assert abs(conv.state.power) < 5000.0

    def test_zero_power_no_soc_change(self):
        """Zero power request should not change battery SOC."""
        conv = _make_converter(max_power=1000.0)

        soc_before = conv.storage.state.soc
        conv.update(power_setpoint=0.0, dt=60.0)

        assert conv.storage.state.soc == soc_before
        assert conv.storage.state.power == 0.0
        assert conv.state.power == 0.0
        assert conv.state.loss == 0.0

    def test_multiple_updates(self):
        """Multiple updates should correctly update state."""
        conv = _make_converter(max_power=1000.0)

        # First update
        conv.update(power_setpoint=50.0, dt=1.0)
        assert conv.state.power_setpoint == 50.0
        assert conv.state.power == pytest.approx(50.0, abs=1e-6)

        # Second update
        conv.update(power_setpoint=-100.0, dt=1.0)
        assert conv.state.power_setpoint == -100.0
        assert conv.state.power == pytest.approx(-100.0, abs=1e-6)


# ===================================================================
# Loss calculation
# ===================================================================
class TestConverterLoss:
    def test_charge_loss_positive(self):
        """Charging should have positive loss."""
        conv = _make_converter(max_power=1000.0)

        power_ac = 1000.0
        conv.update(power_setpoint=power_ac, dt=1.0)

        # Loss = AC - DC, should be positive for charging
        loss = conv.state.loss
        power_dc = conv.storage.state.power
        assert power_dc == pytest.approx(power_ac * 0.95, abs=1e-6)
        assert loss == pytest.approx(power_ac * (1 - 0.95), abs=1e-6)
        assert loss == pytest.approx(power_ac - power_dc, abs=1e-6)

    def test_discharge_loss_positive(self):
        """Discharging should have positive loss (heat dissipation)."""
        conv = _make_converter(max_power=1000.0)

        power_ac = -1000.0
        conv.update(power_setpoint=power_ac, dt=1.0)

        # Loss = AC - DC = (-1000) - (-1053) = +53 W (heat dissipated)
        # Loss is always positive, representing energy lost as heat
        loss = conv.state.loss
        power_dc = conv.storage.state.power
        assert power_dc == pytest.approx(power_ac / 0.95, abs=1e-6)
        assert loss == pytest.approx(1000.0 * ((1 / 0.95) - 1), abs=1e-6)
        assert loss == pytest.approx(power_ac - power_dc, abs=1e-6)

    def test_higher_power_higher_loss_magnitude(self):
        """Higher power should result in higher loss magnitude."""
        conv1 = _make_converter(max_power=1000.0)
        conv2 = _make_converter(max_power=1000.0)

        conv1.update(power_setpoint=500.0, dt=1.0)
        conv2.update(power_setpoint=1000.0, dt=1.0)

        assert abs(conv2.state.loss) > abs(conv1.state.loss)


# ===================================================================
# Edge cases
# ===================================================================
class TestConverterEdgeCases:
    def test_very_small_power(self):
        """Very small power should be handled correctly."""
        conv = _make_converter(max_power=1000.0)

        conv.update(power_setpoint=0.001, dt=1.0)

        assert conv.state.power == pytest.approx(0.001, rel=1e-2)

    def test_max_power_exactly(self):
        """Requesting exactly max power should work."""
        conv = _make_converter(max_power=1000.0)

        conv.update(power_setpoint=1000.0, dt=1.0)

        assert conv.state.power == pytest.approx(1000.0)
