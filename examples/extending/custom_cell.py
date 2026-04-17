"""Toy LTO (lithium titanate) cell — a minimal :class:`CellType` implementation.

Demonstrates the smallest subclass of :class:`~simses.battery.cell.CellType`
that is still a valid simses cell: only the two required methods
``open_circuit_voltage`` and ``internal_resistance``, plus the three
property dataclasses passed to ``super().__init__``.

The approximate numbers are typical of a 40 Ah prismatic LTO cell — low
nominal voltage (≈ 2.3 V), moderate C-rate, constant internal
resistance. They are illustrative; not calibrated to any specific
commercial product.
"""

import pandas as pd

from simses.battery import Battery
from simses.battery.cell import CellType
from simses.battery.format import PrismaticCell
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties
from simses.battery.state import BatteryState


class ToyLTO(CellType):
    """Toy LTO cell: linear OCV(SOC), constant Rint."""

    def __init__(self) -> None:
        super().__init__(
            electrical=ElectricalCellProperties(
                nominal_capacity=40.0,      # Ah
                nominal_voltage=2.3,        # V
                max_voltage=2.8,            # V
                min_voltage=1.5,            # V
                max_charge_rate=4.0,        # 1/h
                max_discharge_rate=4.0,     # 1/h
            ),
            thermal=ThermalCellProperties(
                min_temperature=253.15,     # K  (−20 °C)
                max_temperature=333.15,     # K  (+60 °C)
                mass=1.0,                   # kg per cell
                specific_heat=1000.0,       # J/kgK
                convection_coefficient=10.0,  # W/m²K
            ),
            cell_format=PrismaticCell(height=120, width=20, length=100),  # mm
        )

    def open_circuit_voltage(self, state: BatteryState) -> float:
        """Linearly interpolated OCV between ``min_voltage`` and ``max_voltage``."""
        e = self.electrical
        return e.min_voltage + state.soc * (e.max_voltage - e.min_voltage)

    def internal_resistance(self, state: BatteryState) -> float:
        """Constant 1 mΩ, independent of SOC and temperature."""
        return 1e-3


def simulate(n_steps: int = 60, dt: float = 60.0) -> pd.DataFrame:
    """Discharge a 24s1p pack of toy LTO cells and return the logged state.

    Args:
        n_steps: Number of timesteps.
        dt: Seconds per step.

    Returns:
        DataFrame with per-step ``soc``, ``v``, ``i``, and ``power``.
    """
    battery = Battery(
        cell=ToyLTO(),
        circuit=(24, 1),                # 24 cells in series ≈ 55 V nominal
        initial_states={"start_soc": 0.7, "start_T": 298.15},
    )

    log: dict[str, list[float]] = {"soc": [], "v": [], "i": [], "power": []}
    for _ in range(n_steps):
        battery.step(-500.0, dt)        # discharge at 500 W
        log["soc"].append(battery.state.soc)
        log["v"].append(battery.state.v)
        log["i"].append(battery.state.i)
        log["power"].append(battery.state.power)

    return pd.DataFrame(log)


if __name__ == "__main__":
    df = simulate()
    print(df.tail())
