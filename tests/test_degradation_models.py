"""
Parameterized unit tests for degradation models.

To add tests for a new degradation model pair, append a ``DegradationModelSpec``
to the ``DEGRADATION_SPECS`` list. All generic checks are run automatically.
"""

from dataclasses import dataclass

import pytest

from simses.battery.state import BatteryState
from simses.degradation.cycle_detector import HalfCycle
from simses.model.degradation.sony_lfp_calendar import SonyLFPCalendarDegradation
from simses.model.degradation.sony_lfp_cyclic import SonyLFPCyclicDegradation


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def _make_state(soc: float = 0.5, T: float = 298.15) -> BatteryState:
    return BatteryState(
        v=3.6,
        i=0,
        T=T,
        power=0,
        power_setpoint=0,
        loss=0,
        soc=soc,
        ocv=3.6,
        hys=0,
        is_charge=True,
        rint=0.001,
        soh_Q=1.0,
        soh_R=1.0,
        i_max_charge=0,
        i_max_discharge=0,
    )


def _make_half_cycle(dod: float = 0.5, mean_soc: float = 0.5, c_rate: float = 0.5) -> HalfCycle:
    return HalfCycle(
        depth_of_discharge=dod,
        mean_soc=mean_soc,
        c_rate=c_rate,
        full_equivalent_cycles=dod / 2.0,
    )


# ---------------------------------------------------------------------------
# Spec registry
# ---------------------------------------------------------------------------
@dataclass
class CalendarModelSpec:
    name: str
    factory: type


CALENDAR_SPECS = [
    CalendarModelSpec(name="SonyLFPCalendar", factory=SonyLFPCalendarDegradation),
]


@dataclass
class CyclicModelSpec:
    name: str
    factory: type


CYCLIC_SPECS = [
    CyclicModelSpec(name="SonyLFPCyclic", factory=SonyLFPCyclicDegradation),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(params=CALENDAR_SPECS, ids=lambda s: s.name)
def cal_spec(request) -> CalendarModelSpec:
    return request.param


@pytest.fixture()
def cal_model(cal_spec):
    return cal_spec.factory()


@pytest.fixture(params=CYCLIC_SPECS, ids=lambda s: s.name)
def cyc_spec(request) -> CyclicModelSpec:
    return request.param


@pytest.fixture()
def cyc_model(cyc_spec):
    return cyc_spec.factory()


# ===================================================================
# Calendar model generic tests
# ===================================================================
class TestCalendarModel:
    def test_delta_soh_q_negative(self, cal_model):
        """Calendar aging should reduce capacity (delta_soh_Q < 0)."""
        state = _make_state()
        dq, _ = cal_model.update(state, dt=3600.0)
        assert dq < 0

    def test_delta_soh_r_positive(self, cal_model):
        """Calendar aging should increase resistance (delta_soh_R > 0)."""
        state = _make_state()
        _, dr = cal_model.update(state, dt=3600.0)
        assert dr > 0

    def test_zero_dt_zero_change(self, cal_model):
        """Zero timestep should produce zero degradation."""
        state = _make_state()
        dq, dr = cal_model.update(state, dt=0.0)
        assert dq == 0.0
        assert dr == 0.0

    def test_longer_time_more_degradation(self, cal_model):
        """More time should produce more capacity loss."""
        state1 = _make_state()
        state2 = _make_state()
        model1 = type(cal_model)()
        model2 = type(cal_model)()
        dq1, _ = model1.update(state1, dt=3600.0)
        dq2, _ = model2.update(state2, dt=36000.0)
        assert dq2 < dq1  # more negative = more loss


# ===================================================================
# Cyclic model generic tests
# ===================================================================
class TestCyclicModel:
    def test_delta_soh_q_negative(self, cyc_model):
        """Cyclic aging should reduce capacity (delta_soh_Q < 0)."""
        state = _make_state()
        hc = _make_half_cycle()
        dq, _ = cyc_model.update(state, hc)
        assert dq < 0

    def test_delta_soh_r_positive(self, cyc_model):
        """Cyclic aging should increase resistance (delta_soh_R > 0)."""
        state = _make_state()
        hc = _make_half_cycle()
        _, dr = cyc_model.update(state, hc)
        assert dr > 0

    def test_zero_fec_zero_change(self, cyc_model):
        """Zero FEC should produce zero degradation."""
        state = _make_state()
        hc = HalfCycle(depth_of_discharge=0.0, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=0.0)
        dq, dr = cyc_model.update(state, hc)
        assert dq == 0.0
        assert dr == 0.0


# ===================================================================
# Sony LFP calendar specific tests
# ===================================================================
class TestSonyLFPCalendar:
    def test_higher_temperature_more_aging(self):
        """Higher temperature should accelerate calendar aging."""
        model_cold = SonyLFPCalendarDegradation()
        model_hot = SonyLFPCalendarDegradation()
        state_cold = _make_state(T=278.15)  # 5 C
        state_hot = _make_state(T=318.15)  # 45 C
        dq_cold, _ = model_cold.update(state_cold, dt=86400.0)
        dq_hot, _ = model_hot.update(state_hot, dt=86400.0)
        # More negative = more degradation
        assert dq_hot < dq_cold

    def test_higher_temperature_more_rinc(self):
        """Higher temperature should also increase resistance more."""
        model_cold = SonyLFPCalendarDegradation()
        model_hot = SonyLFPCalendarDegradation()
        state_cold = _make_state(T=278.15)
        state_hot = _make_state(T=318.15)
        _, dr_cold = model_cold.update(state_cold, dt=86400.0)
        _, dr_hot = model_hot.update(state_hot, dt=86400.0)
        assert dr_hot > dr_cold

    def test_sqrt_time_behavior(self):
        """Capacity loss should follow sqrt(t) — doubling time < 2x loss."""
        model1 = SonyLFPCalendarDegradation()
        model2 = SonyLFPCalendarDegradation()
        state1 = _make_state()
        state2 = _make_state()
        dq1, _ = model1.update(state1, dt=86400.0)
        dq2, _ = model2.update(state2, dt=4 * 86400.0)
        # sqrt(4) = 2, so 4x time should give ~2x loss
        ratio = dq2 / dq1
        assert ratio == pytest.approx(2.0, rel=0.01)

    def test_accumulated_loss_continuity(self):
        """Multiple small steps should produce similar total to one big step."""
        model_single = SonyLFPCalendarDegradation()
        model_multi = SonyLFPCalendarDegradation()

        state_s = _make_state()
        state_m = _make_state()

        total_time = 86400.0  # 1 day
        dq_single, dr_single = model_single.update(state_s, dt=total_time)

        n_steps = 100
        dq_total = 0.0
        dr_total = 0.0
        for _ in range(n_steps):
            dq, dr = model_multi.update(state_m, dt=total_time / n_steps)
            dq_total += dq
            dr_total += dr

        assert dq_total == pytest.approx(dq_single, rel=0.02)
        assert dr_total == pytest.approx(dr_single, rel=0.02)


# ===================================================================
# Sony LFP cyclic specific tests
# ===================================================================
class TestSonyLFPCyclic:
    def test_higher_dod_more_aging(self):
        """Higher depth of discharge should cause more degradation."""
        model_low = SonyLFPCyclicDegradation()
        model_high = SonyLFPCyclicDegradation()
        state = _make_state()
        hc_low = _make_half_cycle(dod=0.2)
        hc_high = _make_half_cycle(dod=0.8)
        dq_low, _ = model_low.update(state, hc_low)
        dq_high, _ = model_high.update(state, hc_high)
        assert dq_high < dq_low  # more negative = more loss

    def test_higher_crate_more_aging(self):
        """Higher C-rate should cause more degradation."""
        model_low = SonyLFPCyclicDegradation()
        model_high = SonyLFPCyclicDegradation()
        state = _make_state()
        hc_low = _make_half_cycle(c_rate=0.2)
        hc_high = _make_half_cycle(c_rate=2.0)
        dq_low, _ = model_low.update(state, hc_low)
        dq_high, _ = model_high.update(state, hc_high)
        assert dq_high < dq_low

    def test_sqrt_fec_behavior(self):
        """Capacity loss should follow sqrt(FEC) — 4x FEC should give ~2x loss."""
        model1 = SonyLFPCyclicDegradation()
        model2 = SonyLFPCyclicDegradation()
        state = _make_state()
        # Same stress factors, different FEC via DOD
        hc1 = HalfCycle(depth_of_discharge=0.5, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=0.25)
        hc2 = HalfCycle(depth_of_discharge=0.5, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=1.0)
        dq1, _ = model1.update(state, hc1)
        dq2, _ = model2.update(state, hc2)
        ratio = dq2 / dq1
        assert ratio == pytest.approx(2.0, rel=0.01)

    def test_accumulated_loss_continuity(self):
        """Multiple small cycles should produce similar total to one large cycle."""
        model_single = SonyLFPCyclicDegradation()
        model_multi = SonyLFPCyclicDegradation()
        state = _make_state()

        total_fec = 1.0
        hc_single = HalfCycle(depth_of_discharge=0.5, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=total_fec)
        dq_single, dr_single = model_single.update(state, hc_single)

        n_steps = 100
        dq_total = 0.0
        dr_total = 0.0
        for _ in range(n_steps):
            hc = HalfCycle(
                depth_of_discharge=0.5,
                mean_soc=0.5,
                c_rate=0.5,
                full_equivalent_cycles=total_fec / n_steps,
            )
            dq, dr = model_multi.update(state, hc)
            dq_total += dq
            dr_total += dr

        assert dq_total == pytest.approx(dq_single, rel=0.02)
        assert dr_total == pytest.approx(dr_single, rel=0.02)
