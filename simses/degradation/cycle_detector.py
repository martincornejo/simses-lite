from dataclasses import dataclass


@dataclass(slots=True)
class HalfCycle:
    """Stress factors for a completed half-cycle.

    Attributes:
        depth_of_discharge: Absolute SOC swing of the half-cycle in p.u.
        mean_soc: Average SOC during the half-cycle in p.u.
        c_rate: Average C-rate during the half-cycle in 1/h.
        full_equivalent_cycles: FEC contribution (depth_of_discharge / 2).
    """

    depth_of_discharge: float
    mean_soc: float
    c_rate: float
    full_equivalent_cycles: float


class HalfCycleDetector:
    """Detects half-cycles by tracking SOC direction reversals.

    A half-cycle is completed when the SOC changes direction (from charging
    to discharging or vice versa). Rest periods (unchanged SOC) are ignored
    and do not trigger a cycle or contribute to elapsed time.

    Attributes:
        total_fec: Cumulative full equivalent cycles.
        last_cycle: The most recently completed HalfCycle, or None.
    """

    def __init__(self, initial_soc: float) -> None:
        self._start_soc: float = initial_soc
        self._prev_soc: float = initial_soc
        self._direction: int = 0  # +1 charging, -1 discharging, 0 unknown
        self._elapsed_time: float = 0.0  # seconds
        self._soc_sum: float = 0.0  # for mean SOC calculation
        self._soc_samples: int = 0
        self.total_fec: float = 0.0
        self.last_cycle: HalfCycle | None = None

    def update(self, soc: float, dt: float) -> bool:
        """Update the detector with a new SOC value.

        Args:
            soc: Current state of charge in p.u.
            dt: Timestep in seconds.

        Returns:
            True if a half-cycle was completed (direction reversal detected).
        """
        delta = soc - self._prev_soc

        # Rest period — no SOC change
        if delta == 0.0:
            return False

        new_direction = 1 if delta > 0 else -1

        if self._direction == 0:
            # First movement — establish direction
            self._direction = new_direction
            self._elapsed_time += dt
            self._soc_sum += (self._prev_soc + soc) / 2
            self._soc_samples += 1
            self._prev_soc = soc
            return False

        if new_direction == self._direction:
            # Same direction — accumulate
            self._elapsed_time += dt
            self._soc_sum += (self._prev_soc + soc) / 2
            self._soc_samples += 1
            self._prev_soc = soc
            return False

        # Direction reversal — complete the half-cycle up to prev_soc
        cycle = self._make_half_cycle()
        self.last_cycle = cycle
        self.total_fec += cycle.full_equivalent_cycles

        # Start new half-cycle from prev_soc
        self._start_soc = self._prev_soc
        self._direction = new_direction
        self._elapsed_time = dt
        self._soc_sum = (self._prev_soc + soc) / 2
        self._soc_samples = 1
        self._prev_soc = soc
        return True

    def _make_half_cycle(self) -> HalfCycle:
        """Build a HalfCycle from the accumulated data."""
        dod = abs(self._prev_soc - self._start_soc)
        mean_soc = self._soc_sum / self._soc_samples if self._soc_samples > 0 else self._start_soc
        elapsed_hours = self._elapsed_time / 3600.0
        c_rate = dod / elapsed_hours if elapsed_hours > 0 else 0.0
        fec = dod / 2.0
        return HalfCycle(
            depth_of_discharge=dod,
            mean_soc=mean_soc,
            c_rate=c_rate,
            full_equivalent_cycles=fec,
        )
