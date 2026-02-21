"""Integration tests for the DegradationModel and Battery integration."""

from simses.battery.battery import Battery
from simses.battery.state import BatteryState
from simses.degradation.calendar import CalendarDegradation
from simses.degradation.cycle_detector import HalfCycle
from simses.degradation.cyclic import CyclicDegradation
from simses.degradation.degradation import DegradationModel

# Re-use test helpers from test_battery
from tests.test_battery import SimpleCell, _make_battery


# ---------------------------------------------------------------------------
# Mock degradation models
# ---------------------------------------------------------------------------
class MockCalendar(CalendarDegradation):
    """Calendar model that returns fixed deltas per call."""

    def __init__(self, dq: float = -1e-6, dr: float = 1e-6) -> None:
        self.dq = dq
        self.dr = dr
        self.call_count = 0

    def update(self, state: BatteryState, dt: float) -> tuple[float, float]:
        self.call_count += 1
        return self.dq, self.dr


class MockCyclic(CyclicDegradation):
    """Cyclic model that returns fixed deltas per call."""

    def __init__(self, dq: float = -1e-4, dr: float = 1e-4) -> None:
        self.dq = dq
        self.dr = dr
        self.call_count = 0

    def update(self, state: BatteryState, half_cycle: HalfCycle) -> tuple[float, float]:
        self.call_count += 1
        return self.dq, self.dr


# ===================================================================
# DegradationModel unit tests
# ===================================================================
class TestDegradationModel:
    def test_calendar_runs_every_step(self):
        """Calendar update is called every timestep."""
        cal = MockCalendar()
        cyc = MockCyclic()
        model = DegradationModel(calendar=cal, cyclic=cyc, initial_soc=0.5)

        state = BatteryState(
            v=3.6,
            i=0,
            T=298.15,
            power=0,
            power_setpoint=0,
            loss=0,
            soc=0.5,
            ocv=3.6,
            hys=0,
            is_charge=True,
            rint=0.001,
            soh_Q=1.0,
            soh_R=1.0,
            i_max_charge=0,
            i_max_discharge=0,
        )
        for _ in range(5):
            model.update(state, dt=60.0)

        assert cal.call_count == 5

    def test_cyclic_only_on_reversal(self):
        """Cyclic update is only called when a half-cycle completes."""
        cal = MockCalendar(dq=0.0, dr=0.0)
        cyc = MockCyclic()
        model = DegradationModel(calendar=cal, cyclic=cyc, initial_soc=0.5)

        state = BatteryState(
            v=3.6,
            i=0,
            T=298.15,
            power=0,
            power_setpoint=0,
            loss=0,
            soc=0.5,
            ocv=3.6,
            hys=0,
            is_charge=True,
            rint=0.001,
            soh_Q=1.0,
            soh_R=1.0,
            i_max_charge=0,
            i_max_discharge=0,
        )

        # Monotonic charge — no cycle
        state.soc = 0.6
        model.update(state, dt=60.0)
        state.soc = 0.7
        model.update(state, dt=60.0)
        assert cyc.call_count == 0

        # Reversal
        state.soc = 0.65
        model.update(state, dt=60.0)
        assert cyc.call_count == 1

    def test_soh_q_decreases(self):
        """soh_Q should decrease over time with calendar aging."""
        cal = MockCalendar(dq=-1e-4, dr=0.0)
        model = DegradationModel.calendar_only(calendar=cal, initial_soc=0.5)

        state = BatteryState(
            v=3.6,
            i=0,
            T=298.15,
            power=0,
            power_setpoint=0,
            loss=0,
            soc=0.5,
            ocv=3.6,
            hys=0,
            is_charge=True,
            rint=0.001,
            soh_Q=1.0,
            soh_R=1.0,
            i_max_charge=0,
            i_max_discharge=0,
        )
        for _ in range(10):
            model.update(state, dt=60.0)

        assert state.soh_Q < 1.0

    def test_soh_r_increases(self):
        """soh_R should increase over time with calendar aging."""
        cal = MockCalendar(dq=0.0, dr=1e-4)
        model = DegradationModel.calendar_only(calendar=cal, initial_soc=0.5)

        state = BatteryState(
            v=3.6,
            i=0,
            T=298.15,
            power=0,
            power_setpoint=0,
            loss=0,
            soc=0.5,
            ocv=3.6,
            hys=0,
            is_charge=True,
            rint=0.001,
            soh_Q=1.0,
            soh_R=1.0,
            i_max_charge=0,
            i_max_discharge=0,
        )
        for _ in range(10):
            model.update(state, dt=60.0)

        assert state.soh_R > 1.0

    def test_calendar_only_no_cyclic(self):
        """calendar_only should never call cyclic update."""
        cal = MockCalendar()
        model = DegradationModel.calendar_only(calendar=cal, initial_soc=0.5)

        state = BatteryState(
            v=3.6,
            i=0,
            T=298.15,
            power=0,
            power_setpoint=0,
            loss=0,
            soc=0.5,
            ocv=3.6,
            hys=0,
            is_charge=True,
            rint=0.001,
            soh_Q=1.0,
            soh_R=1.0,
            i_max_charge=0,
            i_max_discharge=0,
        )
        # Force a reversal
        state.soc = 0.6
        model.update(state, dt=60.0)
        state.soc = 0.55
        model.update(state, dt=60.0)
        # calendar_only uses _NoOpCyclic, so soh_Q change comes only from calendar
        assert cal.call_count == 2

    def test_cyclic_only_no_calendar(self):
        """cyclic_only should not apply calendar changes."""
        cyc = MockCyclic(dq=-1e-3, dr=1e-3)
        model = DegradationModel.cyclic_only(cyclic=cyc, initial_soc=0.5)

        state = BatteryState(
            v=3.6,
            i=0,
            T=298.15,
            power=0,
            power_setpoint=0,
            loss=0,
            soc=0.5,
            ocv=3.6,
            hys=0,
            is_charge=True,
            rint=0.001,
            soh_Q=1.0,
            soh_R=1.0,
            i_max_charge=0,
            i_max_discharge=0,
        )
        # No reversal — no cyclic change, no calendar change
        state.soc = 0.6
        model.update(state, dt=60.0)
        assert state.soh_Q == 1.0  # no calendar effect
        assert state.soh_R == 1.0


# ===================================================================
# Battery integration
# ===================================================================
class TestBatteryDegradationIntegration:
    def test_backward_compatible_no_degradation(self):
        """Battery without degradation should work exactly as before."""
        bat = _make_battery(soc=0.5)
        bat.update(power_setpoint=100.0, dt=60.0)
        assert bat.state.soh_Q == 1.0
        assert bat.state.soh_R == 1.0

    def test_soh_degrades_over_cycles(self):
        """With degradation, SoH should change after charge/discharge cycles."""
        cal = MockCalendar(dq=-1e-5, dr=1e-5)
        cyc = MockCyclic(dq=-1e-4, dr=1e-4)
        model = DegradationModel(calendar=cal, cyclic=cyc, initial_soc=0.5)

        bat = Battery(
            cell=SimpleCell(),
            circuit=(1, 1),
            initial_states={"start_soc": 0.5, "start_T": 298.15},
            degradation=model,
        )

        # Run several charge/discharge cycles
        for _ in range(50):
            bat.update(power_setpoint=200.0, dt=60.0)
        for _ in range(50):
            bat.update(power_setpoint=-200.0, dt=60.0)

        assert bat.state.soh_Q < 1.0
        assert bat.state.soh_R > 1.0

    def test_degradation_called_every_timestep(self):
        """The degradation model's update is called each Battery.update()."""
        cal = MockCalendar()
        model = DegradationModel.calendar_only(calendar=cal, initial_soc=0.5)

        bat = Battery(
            cell=SimpleCell(),
            circuit=(1, 1),
            initial_states={"start_soc": 0.5, "start_T": 298.15},
            degradation=model,
        )

        n_steps = 10
        for _ in range(n_steps):
            bat.update(power_setpoint=100.0, dt=60.0)

        assert cal.call_count == n_steps
