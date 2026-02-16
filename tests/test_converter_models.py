"""
Parameterized unit tests for converter loss models.

To add tests for a new converter loss model, append a ``ConverterModelSpec`` to
the ``CONVERTER_SPECS`` list. All generic checks (efficiency, bidirectionality,
losses, …) are run automatically for every entry.
"""

from dataclasses import dataclass

import pytest

from simses.model.converter.fix_efficiency import FixedEfficiency
from simses.model.converter.sinamics import SinamicsS120, SinamicsS120Fit


# ---------------------------------------------------------------------------
# Converter model registry
# ---------------------------------------------------------------------------
@dataclass
class ConverterModelSpec:
    """Everything the test suite needs to know about a converter loss model."""

    name: str
    factory: type  # Loss model class (no-arg constructor or with defaults)


CONVERTER_SPECS: list[ConverterModelSpec] = [
    ConverterModelSpec(
        name="FixedEfficiency_95",
        factory=lambda: FixedEfficiency(effc=0.95),
    ),
    ConverterModelSpec(
        name="FixedEfficiency_Asymmetric",
        factory=lambda: FixedEfficiency(effc=0.96, effd=0.94),
    ),
    ConverterModelSpec(
        name="SinamicsS120",
        factory=SinamicsS120,
    ),
    ConverterModelSpec(
        name="SinamicsS120Fit",
        factory=SinamicsS120Fit,
    ),
]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(params=CONVERTER_SPECS, ids=lambda s: s.name)
def spec(request) -> ConverterModelSpec:
    return request.param


@pytest.fixture()
def model(spec):
    """Create a loss model instance from the spec."""
    return spec.factory()


# ===================================================================
# Loss model generic tests (run for all models)
# ===================================================================
class TestLossModel:
    def test_zero_power(self, model):
        """Zero power should return zero for both conversions."""
        assert model.ac_to_dc(0.0) == pytest.approx(0.0, abs=1e-6)
        assert model.dc_to_ac(0.0) == pytest.approx(0.0, abs=1e-6)

    def test_charge_has_losses(self, model):
        """Charging (AC->DC) should have losses (DC < AC)."""
        power_ac = 0.5  # normalized power
        power_dc = model.ac_to_dc(power_ac)
        assert power_dc < power_ac
        assert power_dc > 0

    def test_discharge_has_losses(self, model):
        """Discharging (DC->AC) should have losses (AC output > DC input)."""
        power_ac = -0.5  # normalized power
        power_dc = model.ac_to_dc(power_ac)
        assert power_ac > power_dc
        assert power_ac < 0

    def test_bidirectional_consistency(self, model):
        """ac_to_dc and dc_to_ac should be (approximately) inverse operations."""
        powers_ac = [0.6, -0.6]  # test both charge and discharge
        for power_ac in powers_ac:
            power_dc = model.ac_to_dc(power_ac)
            power_ac_out = model.dc_to_ac(power_dc)
            assert power_ac_out == pytest.approx(power_ac, rel=1e-3), (
                f"AC->DC->AC did not return original AC power for input {power_ac}: got {power_ac_out} after conversion"
            )

    def test_monotonic_charge(self, model):
        """Higher AC input should give higher DC output."""
        powers_ac = [0.0, 0.2, 0.5, 0.8, 1.0]
        powers_dc = [model.ac_to_dc(p) for p in powers_ac]
        for i in range(len(powers_dc) - 1):
            assert powers_dc[i + 1] >= powers_dc[i], (
                f"DC output decreased from AC={powers_ac[i]} to AC={powers_ac[i + 1]} "
                f"(DC: {powers_dc[i]} -> {powers_dc[i + 1]})"
            )

    def test_monotonic_discharge(self, model):
        """Higher DC input should give higher AC output."""
        powers_ac = [-0.0, -0.2, -0.5, -0.8, -1.0]
        powers_dc = [model.ac_to_dc(p) for p in powers_ac]
        for i in range(len(powers_ac) - 1):
            assert powers_ac[i + 1] <= powers_ac[i], (
                f"AC output decreased from DC={powers_dc[i]} to DC={powers_dc[i + 1]} "
                f"(AC: {powers_ac[i]} -> {powers_ac[i + 1]})"
            )

    def test_efficiency_reasonable(self, model):
        """Efficiency should be between 0 and 1."""
        power_ac = 1.0
        power_dc = model.ac_to_dc(power_ac)
        efficiency = power_dc / power_ac
        assert 0 < efficiency < 1
