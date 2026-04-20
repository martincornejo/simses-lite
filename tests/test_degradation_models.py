"""
Parameterized unit tests for degradation models.

To add tests for a new degradation model pair, append a ``DegradationModelSpec``
to the ``DEGRADATION_SPECS`` list. All generic checks are run automatically.
"""

from dataclasses import dataclass

import pytest

from simses.battery.state import BatteryState
from simses.degradation.cycle_detector import HalfCycle
from simses.model.degradation.molicel_nmc_calendar import MolicelNMCCalendarDegradation
from simses.model.degradation.molicel_nmc_cyclic import MolicelNMCCyclicDegradation
from simses.model.degradation.sony_lfp_calendar import SonyLFPCalendarDegradation
from simses.model.degradation.sony_lfp_cyclic import SonyLFPCyclicDegradation


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def _make_state(soc: float = 0.5, T: float = 25.0) -> BatteryState:
    return BatteryState(
        v=3.6,
        i=0,
        T=T,
        power=0,
        power_setpoint=0,
        loss=0,
        heat=0,
        soc=soc,
        ocv=3.6,
        hys=0,
        entropy=0,
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
    CalendarModelSpec(name="MolicelNMCCalendar", factory=MolicelNMCCalendarDegradation),
    CalendarModelSpec(name="SonyLFPCalendar", factory=SonyLFPCalendarDegradation),
]


@dataclass
class CyclicModelSpec:
    name: str
    factory: type


CYCLIC_SPECS = [
    CyclicModelSpec(name="MolicelNMCCyclic", factory=MolicelNMCCyclicDegradation),
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
    def test_capacity_loss_positive(self, cal_model):
        """Calendar aging should produce a positive capacity loss value."""
        state = _make_state()
        dq = cal_model.update_capacity(state, dt=3600.0, accumulated_qloss=0.0)
        assert dq > 0

    def test_delta_soh_r_positive(self, cal_model):
        """Calendar aging should increase resistance (delta_soh_R > 0)."""
        state = _make_state()
        dr = cal_model.update_resistance(state, dt=3600.0, accumulated_rinc=0.0)
        assert dr > 0

    def test_zero_dt_zero_change(self, cal_model):
        """Zero timestep should produce zero degradation."""
        state = _make_state()
        assert cal_model.update_capacity(state, dt=0.0, accumulated_qloss=0.0) == 0.0
        assert cal_model.update_resistance(state, dt=0.0, accumulated_rinc=0.0) == 0.0

    def test_longer_time_more_degradation(self, cal_model):
        """More time should produce more capacity loss."""
        state1 = _make_state()
        state2 = _make_state()
        model1 = type(cal_model)()
        model2 = type(cal_model)()
        dq1 = model1.update_capacity(state1, dt=3600.0, accumulated_qloss=0.0)
        dq2 = model2.update_capacity(state2, dt=36000.0, accumulated_qloss=0.0)
        assert dq2 > dq1  # more positive = more loss


# ===================================================================
# Cyclic model generic tests
# ===================================================================
class TestCyclicModel:
    def test_capacity_loss_positive(self, cyc_model):
        """Cyclic aging should produce a positive capacity loss value."""
        state = _make_state()
        hc = _make_half_cycle()
        dq = cyc_model.update_capacity(state, hc, accumulated_qloss=0.0)
        assert dq > 0

    def test_delta_soh_r_positive(self, cyc_model):
        """Cyclic aging should increase resistance (delta_soh_R > 0)."""
        state = _make_state()
        hc = _make_half_cycle()
        dr = cyc_model.update_resistance(state, hc, accumulated_rinc=0.0)
        assert dr > 0

    def test_zero_fec_zero_change(self, cyc_model):
        """Zero FEC should produce zero degradation."""
        state = _make_state()
        hc = HalfCycle(depth_of_discharge=0.0, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=0.0)
        assert cyc_model.update_capacity(state, hc, accumulated_qloss=0.0) == 0.0
        assert cyc_model.update_resistance(state, hc, accumulated_rinc=0.0) == 0.0


# ===================================================================
# Sony LFP calendar specific tests
# ===================================================================
class TestSonyLFPCalendar:
    def test_higher_temperature_more_aging(self):
        """Higher temperature should accelerate calendar aging."""
        model_cold = SonyLFPCalendarDegradation()
        model_hot = SonyLFPCalendarDegradation()
        state_cold = _make_state(T=5.0)  # 5 °C
        state_hot = _make_state(T=45.0)  # 45 °C
        dq_cold = model_cold.update_capacity(state_cold, dt=86400.0, accumulated_qloss=0.0)
        dq_hot = model_hot.update_capacity(state_hot, dt=86400.0, accumulated_qloss=0.0)
        assert dq_hot > dq_cold  # more positive = more degradation

    def test_higher_temperature_more_rinc(self):
        """Higher temperature should also increase resistance more."""
        model_cold = SonyLFPCalendarDegradation()
        model_hot = SonyLFPCalendarDegradation()
        state_cold = _make_state(T=5.0)
        state_hot = _make_state(T=45.0)
        dr_cold = model_cold.update_resistance(state_cold, dt=86400.0, accumulated_rinc=0.0)
        dr_hot = model_hot.update_resistance(state_hot, dt=86400.0, accumulated_rinc=0.0)
        assert dr_hot > dr_cold

    def test_sqrt_time_behavior(self):
        """Capacity loss should follow sqrt(t) — doubling time < 2x loss."""
        model1 = SonyLFPCalendarDegradation()
        model2 = SonyLFPCalendarDegradation()
        state1 = _make_state()
        state2 = _make_state()
        dq1 = model1.update_capacity(state1, dt=86400.0, accumulated_qloss=0.0)
        dq2 = model2.update_capacity(state2, dt=4 * 86400.0, accumulated_qloss=0.0)
        # sqrt(4) = 2, so 4x time should give ~2x loss
        ratio = dq2 / dq1
        assert ratio == pytest.approx(2.0, rel=0.01)

    def test_accumulated_loss_continuity(self):
        """Multiple small steps should produce similar total to one big step."""
        model = SonyLFPCalendarDegradation()
        state = _make_state()

        total_time = 86400.0  # 1 day
        dq_single = model.update_capacity(state, dt=total_time, accumulated_qloss=0.0)
        dr_single = model.update_resistance(state, dt=total_time, accumulated_rinc=0.0)

        n_steps = 100
        accumulated_qloss = 0.0
        accumulated_rinc = 0.0
        dq_total = 0.0
        dr_total = 0.0
        for _ in range(n_steps):
            dq = model.update_capacity(state, dt=total_time / n_steps, accumulated_qloss=accumulated_qloss)
            accumulated_qloss += dq
            dq_total += dq
            dr = model.update_resistance(state, dt=total_time / n_steps, accumulated_rinc=accumulated_rinc)
            accumulated_rinc += dr
            dr_total += dr

        assert dq_total == pytest.approx(dq_single, rel=0.02)
        assert dr_total == pytest.approx(dr_single, rel=0.02)


# ===================================================================
# Sony LFP cyclic specific tests
# ===================================================================
class TestSonyLFPCyclic:
    def test_higher_dod_more_aging(self):
        """Higher depth of discharge should cause more degradation."""
        model = SonyLFPCyclicDegradation()
        state = _make_state()
        hc_low = _make_half_cycle(dod=0.2)
        hc_high = _make_half_cycle(dod=0.8)
        dq_low = model.update_capacity(state, hc_low, accumulated_qloss=0.0)
        dq_high = model.update_capacity(state, hc_high, accumulated_qloss=0.0)
        assert dq_high > dq_low  # more positive = more loss

    def test_higher_crate_more_aging(self):
        """Higher C-rate should cause more degradation."""
        model = SonyLFPCyclicDegradation()
        state = _make_state()
        hc_low = _make_half_cycle(c_rate=0.2)
        hc_high = _make_half_cycle(c_rate=2.0)
        dq_low = model.update_capacity(state, hc_low, accumulated_qloss=0.0)
        dq_high = model.update_capacity(state, hc_high, accumulated_qloss=0.0)
        assert dq_high > dq_low

    def test_sqrt_fec_behavior(self):
        """Capacity loss should follow sqrt(FEC) — 4x FEC should give ~2x loss."""
        model = SonyLFPCyclicDegradation()
        state = _make_state()
        hc1 = HalfCycle(depth_of_discharge=0.5, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=0.25)
        hc2 = HalfCycle(depth_of_discharge=0.5, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=1.0)
        dq1 = model.update_capacity(state, hc1, accumulated_qloss=0.0)
        dq2 = model.update_capacity(state, hc2, accumulated_qloss=0.0)
        ratio = dq2 / dq1
        assert ratio == pytest.approx(2.0, rel=0.01)

    def test_accumulated_loss_continuity(self):
        """Multiple small cycles should produce similar total to one large cycle."""
        model = SonyLFPCyclicDegradation()
        state = _make_state()

        total_fec = 1.0
        hc_single = HalfCycle(depth_of_discharge=0.5, mean_soc=0.5, c_rate=0.5, full_equivalent_cycles=total_fec)
        dq_single = model.update_capacity(state, hc_single, accumulated_qloss=0.0)
        dr_single = model.update_resistance(state, hc_single, accumulated_rinc=0.0)

        n_steps = 100
        accumulated_qloss = 0.0
        accumulated_rinc = 0.0
        dq_total = 0.0
        dr_total = 0.0
        for _ in range(n_steps):
            hc = HalfCycle(
                depth_of_discharge=0.5,
                mean_soc=0.5,
                c_rate=0.5,
                full_equivalent_cycles=total_fec / n_steps,
            )
            dq = model.update_capacity(state, hc, accumulated_qloss=accumulated_qloss)
            accumulated_qloss += dq
            dq_total += dq
            dr = model.update_resistance(state, hc, accumulated_rinc=accumulated_rinc)
            accumulated_rinc += dr
            dr_total += dr

        assert dq_total == pytest.approx(dq_single, rel=0.02)
        assert dr_total == pytest.approx(dr_single, rel=0.02)
