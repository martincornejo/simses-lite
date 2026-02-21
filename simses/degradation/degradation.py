from simses.battery.state import BatteryState
from simses.degradation.calendar import CalendarDegradation
from simses.degradation.cycle_detector import HalfCycle, HalfCycleDetector
from simses.degradation.cyclic import CyclicDegradation


class _NoOpCalendar(CalendarDegradation):
    def update(self, state: BatteryState, dt: float) -> tuple[float, float]:
        return 0.0, 0.0


class _NoOpCyclic(CyclicDegradation):
    def update(self, state: BatteryState, half_cycle: HalfCycle) -> tuple[float, float]:
        return 0.0, 0.0


class DegradationModel:
    """Composes calendar and cyclic degradation with a half-cycle detector.

    This is the object that gets passed to ``Battery(degradation=...)``.
    It has an ``update(state, dt)`` method that Battery calls at the end
    of each timestep.
    """

    def __init__(
        self,
        calendar: CalendarDegradation,
        cyclic: CyclicDegradation,
        initial_soc: float,
    ) -> None:
        self.calendar = calendar
        self.cyclic = cyclic
        self.cycle_detector = HalfCycleDetector(initial_soc)

    @classmethod
    def calendar_only(cls, calendar: CalendarDegradation, initial_soc: float) -> "DegradationModel":
        """Create a model with only calendar aging (no cyclic component)."""
        return cls(calendar=calendar, cyclic=_NoOpCyclic(), initial_soc=initial_soc)

    @classmethod
    def cyclic_only(cls, cyclic: CyclicDegradation, initial_soc: float) -> "DegradationModel":
        """Create a model with only cyclic aging (no calendar component)."""
        return cls(calendar=_NoOpCalendar(), cyclic=cyclic, initial_soc=initial_soc)

    def update(self, state: BatteryState, dt: float) -> None:
        """Run one degradation timestep.

        1. Calendar aging is applied every timestep.
        2. The cycle detector checks for SOC direction reversals; when a
           half-cycle completes, cyclic aging is applied.
        """
        # Calendar aging
        dq_cal, dr_cal = self.calendar.update(state, dt)
        state.soh_Q += dq_cal
        state.soh_R += dr_cal

        # Cycle detection + cyclic aging
        if self.cycle_detector.update(state.soc, dt):
            half_cycle = self.cycle_detector.last_cycle
            dq_cyc, dr_cyc = self.cyclic.update(state, half_cycle)
            state.soh_Q += dq_cyc
            state.soh_R += dr_cyc
