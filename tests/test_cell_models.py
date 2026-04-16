"""
Parameterized unit tests for battery cell models.

To add tests for a new cell model, append a ``CellModelSpec`` to the
``CELL_SPECS`` list.  All generic checks (OCV shape, Rint sign, thermal
properties, …) are run automatically for every entry.
"""

from dataclasses import dataclass

import pytest

from simses.battery.cell import CellType
from simses.battery.state import BatteryState
from simses.model.cell.samsung94Ah_nmc import Samsung94AhNMC
from simses.model.cell.sony_lfp import SonyLFP


# ---------------------------------------------------------------------------
# Cell model registry
# ---------------------------------------------------------------------------
@dataclass
class CellModelSpec:
    """Everything the test suite needs to know about a cell model."""

    name: str
    factory: type  # CellType subclass (no-arg constructor)

    # -- behavioural flags (for conditional tests) --
    rint_varies_with_soc: bool = False
    rint_varies_with_temperature: bool = False
    rint_differs_charge_discharge: bool = False

    # temperature range safe for Rint queries (e.g. interpolation bounds)
    rint_temp_low: float = 283.15
    rint_temp_high: float = 333.15


CELL_SPECS: list[CellModelSpec] = [
    CellModelSpec(
        name="Samsung94AhNMC",
        factory=Samsung94AhNMC,
    ),
    CellModelSpec(
        name="SonyLFP",
        factory=SonyLFP,
        rint_varies_with_soc=True,
        rint_varies_with_temperature=True,
        rint_differs_charge_discharge=True,
        rint_temp_low=283.15,
        rint_temp_high=333.15,
    ),
]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(params=CELL_SPECS, ids=lambda s: s.name)
def spec(request) -> CellModelSpec:
    return request.param


@pytest.fixture()
def cell(spec) -> CellType:
    return spec.factory()


def _state(soc: float = 0.5, T: float = 298.15, is_charge: bool = True) -> BatteryState:
    return BatteryState(
        v=0,
        i=0,
        T=T,
        power=0,
        power_setpoint=0,
        loss=0,
        heat=0,
        soc=soc,
        ocv=0,
        hys=0,
        entropy=0,
        rint=0,
        soh_Q=1.0,
        soh_R=1.0,
        is_charge=is_charge,
        i_max_charge=0,
        i_max_discharge=0,
    )


# ===================================================================
# OCV curve
# ===================================================================
class TestOCV:
    def test_monotonically_increasing(self, cell):
        """OCV must not decrease as SOC increases."""
        socs = [i / 100 for i in range(101)]
        ocvs = [cell.open_circuit_voltage(_state(soc=s)) for s in socs]
        for k in range(1, len(ocvs)):
            assert ocvs[k] >= ocvs[k - 1] - 1e-6, f"OCV decreased from SOC={socs[k - 1]} to SOC={socs[k]}"

    def test_within_voltage_window(self, cell):
        """OCV must stay within [min_voltage, max_voltage] for all SOC."""
        v_min = cell.electrical.min_voltage
        v_max = cell.electrical.max_voltage
        for soc_pct in range(0, 101, 10):
            soc = soc_pct / 100
            ocv = cell.open_circuit_voltage(_state(soc=soc))
            assert v_min <= ocv <= v_max, f"OCV={ocv:.4f} outside [{v_min}, {v_max}] at SOC={soc}"


# ===================================================================
# Internal resistance
# ===================================================================
class TestInternalResistance:
    def test_positive_across_states(self, cell, spec):
        """Rint must be positive for all relevant operating conditions."""
        # Determine SOC values to test
        if spec.rint_varies_with_soc:
            socs = [0.0, 0.5, 1.0]
        else:
            socs = [None]

        # Determine temperature values to test
        if spec.rint_varies_with_temperature:
            low = spec.rint_temp_low
            high = spec.rint_temp_high
            mid = (low + high) / 2
            temps = [low, mid, high]
        else:
            temps = [None]

        # Determine charge/discharge modes to test
        if spec.rint_differs_charge_discharge:
            modes = [True, False]
        else:
            modes = [None]

        # Test all combinations
        for soc in socs:
            for T in temps:
                for is_charge in modes:
                    state = _state(soc=soc, T=T, is_charge=is_charge)
                    rint = cell.internal_resistance(state)
                    assert rint > 0, f"Rint={rint} at SOC={soc}, T={T}, is_charge={is_charge}"


# ===================================================================
# Hysteresis voltage
# ===================================================================
class TestHysteresisVoltage:
    def test_returns_float(self, cell):
        assert isinstance(cell.hysteresis_voltage(_state()), float)

    def test_within_reasonable_range(self, cell):
        """Hysteresis voltage magnitude should be smaller than the full voltage window."""
        v_range = cell.electrical.max_voltage - cell.electrical.min_voltage
        for soc in [0.0, 0.25, 0.5, 0.75, 1.0]:
            hys = cell.hysteresis_voltage(_state(soc=soc))
            assert abs(hys) < v_range, f"Hysteresis={hys:.4f} exceeds voltage window at SOC={soc}"


# ===================================================================
# Entropic coefficient
# ===================================================================
class TestEntropicCoefficient:
    def test_returns_float(self, cell):
        assert isinstance(cell.entropic_coefficient(_state()), float)

    def test_reasonable_magnitude(self, cell):
        """Entropic coefficient for Li-ion cells is typically between -1 and +1 mV/K."""
        for soc in [0.0, 0.25, 0.5, 0.75, 1.0]:
            ec = cell.entropic_coefficient(_state(soc=soc))
            assert abs(ec) < 1e-2, f"Entropic coefficient={ec:.6f} V/K seems unreasonably large at SOC={soc}"


# ===================================================================
# Cell format
# ===================================================================
class TestCellFormat:
    def test_volume_positive(self, cell):
        assert cell.format.volume > 0

    def test_area_positive(self, cell):
        assert cell.format.area > 0
