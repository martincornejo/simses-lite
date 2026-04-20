# Extending Cell Models

How to implement a new cell chemistry as a `CellType` subclass, drop it into a `Battery`, and plug it into the existing test harness.

!!! info "Who this is for"
    Researchers or engineers who want to simulate a cell not covered by the shipped `SonyLFP` / `Samsung94AhNMC`. If you just need to pick between the existing models, see [Choosing a Cell Model](cell-models.md) instead. For the architectural picture of how `CellType` and `Battery` interact, see [Battery concept](../concepts/battery.md#battery-and-celltype).

## The contract

A cell model subclasses [`CellType`][simses.battery.cell.CellType] and implements two required methods:

| Method | Returns | Purpose |
|---|---|---|
| `open_circuit_voltage(state) -> float` | OCV in V | Per-cell OCV as a function of the current `BatteryState` (SOC, T). |
| `internal_resistance(state) -> float` | Rint in Ω | Per-cell internal resistance at the current state. |

Three optional overrides add behaviour:

| Method | Default | When to override |
|---|---|---|
| `hysteresis_voltage(state) -> float` | `0.0` | LFP cells with measurable OCV hysteresis. |
| `entropic_coefficient(state) -> float` | `0.0` | When reversible entropic heating matters for thermal studies. |
| `default_degradation_model(initial_soc, initial_state=None) -> DegradationModel \| None` | `None` | To make `Battery(..., degradation=True)` "just work" for your cell. |

All methods receive (or return) **per-cell** values. `Battery` scales them to the pack level on its own — see [Series-parallel scaling](../concepts/battery.md#from-cell-to-pack).

## The three property dataclasses

`CellType.__init__` wires three dataclasses into the base class. Every subclass supplies one of each:

- [`ElectricalCellProperties`][simses.battery.properties.ElectricalCellProperties] — nominal capacity, nominal / min / max voltage, max C-rates (charge and discharge), optional self-discharge and coulomb efficiency, optional voltage-derating thresholds.
- [`ThermalCellProperties`][simses.battery.properties.ThermalCellProperties] — allowed temperature range, mass, specific heat, convection coefficient.
- [`CellFormat`][simses.battery.format.CellFormat] — [`PrismaticCell`][simses.battery.format.PrismaticCell], [`RoundCell`][simses.battery.format.RoundCell], or one of the shipped presets ([`RoundCell18650`][simses.battery.format.RoundCell18650], [`RoundCell26650`][simses.battery.format.RoundCell26650]).

These carry datasheet-level facts about the cell. `Battery` reads them (via `cell.electrical`, `cell.thermal`, `cell.format`) and scales them to the pack through the circuit tuple.

## Worked walkthrough: a toy LTO cell

[`examples/extending/custom_cell.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/custom_cell.py) implements a minimal LTO cell — linear OCV between `min_voltage` and `max_voltage`, constant Rint. The subclass body is under 30 lines:

```python
from simses.battery.cell import CellType
from simses.battery.format import PrismaticCell
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties
from simses.battery.state import BatteryState


class ToyLTO(CellType):
    def __init__(self) -> None:
        super().__init__(
            electrical=ElectricalCellProperties(
                nominal_capacity=40.0, nominal_voltage=2.3,
                max_voltage=2.8, min_voltage=1.5,
                max_charge_rate=4.0, max_discharge_rate=4.0,
            ),
            thermal=ThermalCellProperties(
                min_temperature=-20.0, max_temperature=60.0,
                mass=1.0, specific_heat=1000.0,
                convection_coefficient=10.0,
            ),
            cell_format=PrismaticCell(height=120, width=20, length=100),
        )

    def open_circuit_voltage(self, state: BatteryState) -> float:
        e = self.electrical
        return e.min_voltage + state.soc * (e.max_voltage - e.min_voltage)

    def internal_resistance(self, state: BatteryState) -> float:
        return 1e-3
```

Everything else (pack-level voltages, capacity scaling, hard-limit clamping, the ECM quadratic) is inherited from `Battery`. The cell file contributes the *datasheet* plus OCV and Rint functions; nothing more.

Use the new cell exactly like a shipped one:

```python
battery = Battery(
    cell=ToyLTO(),
    circuit=(24, 1),
    initial_states={"start_soc": 0.7, "start_T": 25.0},
)
```

## System-level scaling you get for free

When you pass your cell to `Battery(cell=ToyLTO(), circuit=(s, p), ...)`, the framework scales per-cell quantities to pack quantities at every `step()`:

| Per-cell quantity | System-level | Scaling |
|---|---|---|
| `open_circuit_voltage` | System OCV | × `s` |
| `hysteresis_voltage` | System hysteresis | × `s` |
| `internal_resistance` | System Rint | × `s/p × soh_R` |
| `entropic_coefficient` | System ∂V/∂T | × `s` |
| `electrical.nominal_capacity` | System capacity | × `p × soh_Q` |
| `electrical.max_charge_rate` | Max charge current | × cell nominal capacity × `p` |

Keep every method and every `ElectricalCellProperties` field in **per-cell** units. If you accidentally supply pack-level values, the shipped tests will catch the scaling errors — see [Testing](#testing-with-cellmodelspec) below.

## CSV-backed lookups for measured data

If your OCV or Rint curve comes from measurements rather than an analytical fit, mirror the `SonyLFP` pattern: load a CSV at `__init__`, stash the columns as Python lists, and use the helpers from `simses.interpolation`:

```python
import os
import pandas as pd

from simses.interpolation import interp1d_scalar, interp2d_scalar


class MyCell(CellType):
    def __init__(self):
        super().__init__(electrical=..., thermal=..., cell_format=...)

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        df_ocv = pd.read_csv(os.path.join(path, "my_cell_ocv.csv"))
        self._ocv_soc = df_ocv["SOC"].tolist()
        self._ocv_v = df_ocv["OCV"].tolist()

        df_rint = pd.read_csv(os.path.join(path, "my_cell_rint.csv"))
        self._rint_soc = df_rint["SOC"].tolist()
        self._rint_T = df_rint["Temp"].dropna().tolist()
        self._rint_mat = df_rint.iloc[:, 2:].values.tolist()

    def open_circuit_voltage(self, state):
        return interp1d_scalar(state.soc, self._ocv_soc, self._ocv_v)

    def internal_resistance(self, state):
        return interp2d_scalar(state.soc, state.T,
                               self._rint_soc, self._rint_T, self._rint_mat)
```

Storing the LUTs as plain Python lists lets `interp1d_scalar` use `bisect` on the raw sequence — faster than numpy for scalar-at-a-time lookups inside a hot loop. The shipped [`SonyLFP`][simses.model.cell.sony_lfp.SonyLFP] goes further with separate charge/discharge matrices in a 2-D lookup; use that as the full reference.

## Testing with `CellModelSpec`

`tests/test_cell_models.py` runs a parameterised generic suite — OCV monotonicity, OCV stays inside the voltage window, Rint positive, hysteresis/entropy within reasonable bounds, format geometry positive. Add your cell to the suite by appending a `CellModelSpec` entry:

```python
# tests/test_cell_models.py
CELL_SPECS: list[CellModelSpec] = [
    CellModelSpec(name="Samsung94AhNMC", factory=Samsung94AhNMC),
    CellModelSpec(
        name="SonyLFP",
        factory=SonyLFP,
        rint_varies_with_soc=True,
        rint_varies_with_temperature=True,
        rint_differs_charge_discharge=True,
    ),
    # --- your cell below ---
    CellModelSpec(
        name="ToyLTO",
        factory=ToyLTO,
        # rint_* flags default to False — set to True as needed for your Rint shape
    ),
]
```

The behavioural flags toggle which combinations the Rint positivity test walks — keep them `False` if your Rint is constant; set them `True` if Rint depends on SOC / temperature / direction. Run the suite with `pytest tests/test_cell_models.py -v`.

## Shipping a default degradation model

Override `default_degradation_model` as a `classmethod` if you want `Battery(..., degradation=True)` to work out of the box with your cell. Follow the [`SonyLFP`][simses.model.cell.sony_lfp.SonyLFP] pattern:

```python
from simses.degradation import DegradationModel


class MyCell(CellType):
    # ... __init__, open_circuit_voltage, internal_resistance ...

    @classmethod
    def default_degradation_model(
        cls,
        initial_soc: float,
        initial_state=None,
    ) -> DegradationModel:
        return DegradationModel(
            calendar=MyCellCalendarDegradation(),
            cyclic=MyCellCyclicDegradation(),
            initial_soc=initial_soc,
            initial_state=initial_state,
        )
```

See [Extending Degradation](extending-degradation.md) for writing the calendar and cyclic sub-models.

## See Also

- [Battery concept](../concepts/battery.md) — how `CellType` composes into `Battery` and the ECM quadratic it feeds into.
- [Choosing a Cell Model](cell-models.md) — the two shipped cells, for reference designs.
- [`examples/extending/custom_cell.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/custom_cell.py) — the full runnable walkthrough.
- [`CellType` API reference](../api/battery.md#cell-interface).
