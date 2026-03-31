from dataclasses import dataclass, field


@dataclass(slots=True)
class DegradationState:
    """Accumulated degradation components (all values in p.u., non-negative).

    This is the authoritative state for a :class:`DegradationModel`.  Calendar
    and cyclic sub-models are stateless — they receive the current accumulated
    value as an argument to their ``update`` method and return deltas, which the
    ``DegradationModel`` applies here.
    """

    qloss_cal: float = 0.0  # calendar capacity loss
    qloss_cyc: float = 0.0  # cyclic capacity loss
    rinc_cal: float = 0.0  # calendar resistance increase
    rinc_cyc: float = 0.0  # cyclic resistance increase
