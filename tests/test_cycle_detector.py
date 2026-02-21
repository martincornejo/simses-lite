"""Unit tests for the HalfCycleDetector."""

import pytest

from simses.degradation.cycle_detector import HalfCycleDetector


class TestDirectionReversal:
    def test_no_cycle_on_monotonic_charge(self):
        """Monotonically increasing SOC should not trigger a cycle."""
        det = HalfCycleDetector(initial_soc=0.3)
        socs = [0.35, 0.40, 0.45, 0.50]
        for soc in socs:
            assert det.update(soc, dt=60.0) is False

    def test_no_cycle_on_monotonic_discharge(self):
        """Monotonically decreasing SOC should not trigger a cycle."""
        det = HalfCycleDetector(initial_soc=0.7)
        socs = [0.65, 0.60, 0.55, 0.50]
        for soc in socs:
            assert det.update(soc, dt=60.0) is False

    def test_cycle_on_charge_then_discharge(self):
        """Charging then discharging should trigger a cycle at reversal."""
        det = HalfCycleDetector(initial_soc=0.5)
        det.update(0.6, dt=60.0)  # charge
        det.update(0.7, dt=60.0)  # charge
        result = det.update(0.65, dt=60.0)  # discharge -> reversal
        assert result is True
        assert det.last_cycle is not None

    def test_cycle_on_discharge_then_charge(self):
        """Discharging then charging should trigger a cycle at reversal."""
        det = HalfCycleDetector(initial_soc=0.5)
        det.update(0.4, dt=60.0)  # discharge
        result = det.update(0.45, dt=60.0)  # charge -> reversal
        assert result is True

    def test_multiple_reversals(self):
        """Each reversal should produce a cycle."""
        det = HalfCycleDetector(initial_soc=0.5)
        det.update(0.6, dt=60.0)  # charge
        assert det.update(0.55, dt=60.0) is True  # reversal 1
        assert det.update(0.6, dt=60.0) is True  # reversal 2


class TestStressFactors:
    def test_dod_calculation(self):
        """DOD should be the absolute SOC swing."""
        det = HalfCycleDetector(initial_soc=0.3)
        det.update(0.5, dt=60.0)  # charge by 0.2
        det.update(0.45, dt=60.0)  # reversal
        assert det.last_cycle.depth_of_discharge == pytest.approx(0.2)

    def test_mean_soc(self):
        """Mean SOC should be the average over the half-cycle."""
        det = HalfCycleDetector(initial_soc=0.4)
        det.update(0.6, dt=60.0)  # midpoint avg = (0.4+0.6)/2 = 0.5
        det.update(0.55, dt=60.0)  # reversal
        assert det.last_cycle.mean_soc == pytest.approx(0.5)

    def test_c_rate_units(self):
        """C-rate should be DOD / elapsed_hours (1/h)."""
        det = HalfCycleDetector(initial_soc=0.5)
        # 0.2 DOD in 3600s = 1h -> c_rate = 0.2 / 1.0 = 0.2 1/h
        det.update(0.7, dt=3600.0)
        det.update(0.65, dt=60.0)  # reversal
        assert det.last_cycle.c_rate == pytest.approx(0.2)

    def test_fec_is_half_dod(self):
        """FEC contribution should be DOD / 2."""
        det = HalfCycleDetector(initial_soc=0.3)
        det.update(0.7, dt=60.0)  # DOD = 0.4
        det.update(0.65, dt=60.0)  # reversal
        assert det.last_cycle.full_equivalent_cycles == pytest.approx(0.2)


class TestFECAccumulation:
    def test_total_fec_accumulates(self):
        """total_fec should accumulate over multiple cycles."""
        det = HalfCycleDetector(initial_soc=0.5)
        det.update(0.7, dt=60.0)  # charge
        det.update(0.6, dt=60.0)  # reversal 1: DOD=0.2, FEC=0.1
        fec1 = det.total_fec
        assert fec1 == pytest.approx(0.1)

        det.update(0.5, dt=60.0)  # continue discharge (no reversal)
        det.update(0.55, dt=60.0)  # reversal 2: DOD=0.1, FEC=0.05
        assert det.total_fec > fec1
        assert det.total_fec == pytest.approx(fec1 + det.last_cycle.full_equivalent_cycles)

    def test_total_fec_zero_initially(self):
        det = HalfCycleDetector(initial_soc=0.5)
        assert det.total_fec == 0.0


class TestRestPeriods:
    def test_rest_does_not_trigger_cycle(self):
        """Unchanged SOC should not trigger a cycle."""
        det = HalfCycleDetector(initial_soc=0.5)
        det.update(0.6, dt=60.0)  # charge
        result = det.update(0.6, dt=60.0)  # rest
        assert result is False

    def test_rest_does_not_affect_elapsed_time(self):
        """Rest periods should not contribute to elapsed time / c_rate."""
        det = HalfCycleDetector(initial_soc=0.5)
        # Charge 0.2 in 3600s, then rest for 7200s, then reversal
        det.update(0.7, dt=3600.0)  # charge 0.2 in 1h
        det.update(0.7, dt=7200.0)  # rest (should not count)
        det.update(0.65, dt=60.0)  # reversal
        # C-rate should be based on 3600s, not 3600+7200
        assert det.last_cycle.c_rate == pytest.approx(0.2)

    def test_rest_between_movements_preserves_direction(self):
        """Rest periods between same-direction movements should not cause issues."""
        det = HalfCycleDetector(initial_soc=0.5)
        det.update(0.6, dt=60.0)  # charge
        det.update(0.6, dt=60.0)  # rest
        det.update(0.7, dt=60.0)  # charge continues
        assert det.update(0.65, dt=60.0) is True  # reversal
        assert det.last_cycle.depth_of_discharge == pytest.approx(0.2)
