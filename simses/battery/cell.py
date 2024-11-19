from abc import ABC, abstractmethod

from simses.battery.format import CellFormat
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties


class CellType(ABC):
    def __init__(
        self,
        electrical: ElectricalCellProperties,
        thermal: ThermalCellProperties,
        cell_format: CellFormat,
    ) -> None:
        super().__init__()
        self.electrical = electrical
        self.thermal = thermal
        self.format = cell_format

    @abstractmethod
    def open_circuit_voltage(self, state) -> float:
        pass

    def hystheresis_voltage(self, state) -> float:
        return 0

    @abstractmethod
    def internal_resistance(self, state) -> float:
        "BOL internal resistance"
        pass

    # TODO: degradation model?
