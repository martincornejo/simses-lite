from simses.battery.state import BatteryState
from simses.degradation.calendar import CalendarDegradation
from simses.degradation.cycle_detector import HalfCycle, HalfCycleDetector
from simses.degradation.cyclic import CyclicDegradation
from simses.degradation.state import DegradationState


class _NoOpCalendar:
    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        return 0.0

    def update_resistance(self, state: BatteryState, dt: float) -> float:
        return 0.0


class _NoOpCyclic:
    def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float:
        return 0.0

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle) -> float:
        return 0.0


class DegradationModel:
    """Composes calendar and cyclic degradation with a half-cycle detector.

    This is the object that gets passed to ``Battery(degradation=...)``.
    It owns a :class:`~simses.degradation.state.DegradationState` that
    accumulates all capacity loss and resistance increase components.
    Sub-models are stateless and receive the current accumulated values on
    each call.
    """

    def __init__(
        self,
        calendar: CalendarDegradation,
        cyclic: CyclicDegradation,
        initial_soc: float,
        initial_state: DegradationState | None = None,
    ) -> None:
        self.calendar = calendar
        self.cyclic = cyclic
        self.cycle_detector = HalfCycleDetector(initial_soc)
        self.state = initial_state if initial_state is not None else DegradationState()

    @classmethod
    def calendar_only(
        cls,
        calendar: CalendarDegradation,
        initial_soc: float,
        initial_state: DegradationState | None = None,
    ) -> "DegradationModel":
        """Create a model with only calendar aging (no cyclic component)."""
        return cls(calendar=calendar, cyclic=_NoOpCyclic(), initial_soc=initial_soc, initial_state=initial_state)

    @classmethod
    def cyclic_only(
        cls,
        cyclic: CyclicDegradation,
        initial_soc: float,
        initial_state: DegradationState | None = None,
    ) -> "DegradationModel":
        """Create a model with only cyclic aging (no calendar component)."""
        return cls(calendar=_NoOpCalendar(), cyclic=cyclic, initial_soc=initial_soc, initial_state=initial_state)

    def update(self, state: BatteryState, dt: float) -> None:
        """Run one degradation timestep.

        1. Calendar aging is applied every timestep.
        2. The cycle detector checks for SOC direction reversals; when a
           half-cycle completes, cyclic aging is applied.
        """
        # Calendar aging
        dq_cal = self.calendar.update_capacity(state, dt, self.state.qloss_cal)
        dr_cal = self.calendar.update_resistance(state, dt)
        self.state.qloss_cal += dq_cal
        self.state.rinc_cal += dr_cal
        state.soh_Q -= dq_cal
        state.soh_R += dr_cal

        # Cycle detection + cyclic aging
        if self.cycle_detector.update(state.soc, dt):
            half_cycle = self.cycle_detector.last_cycle
            dq_cyc = self.cyclic.update_capacity(state, half_cycle, self.state.qloss_cyc)
            dr_cyc = self.cyclic.update_resistance(state, half_cycle)
            self.state.qloss_cyc += dq_cyc
            self.state.rinc_cyc += dr_cyc
            state.soh_Q -= dq_cyc
            state.soh_R += dr_cyc
