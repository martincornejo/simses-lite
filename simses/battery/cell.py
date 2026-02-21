from abc import ABC, abstractmethod

from simses.battery.format import CellFormat
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties
from simses.battery.state import BatteryState


class CellType(ABC):
    """
    Abstract base class defining the interface and common properties for different types of battery cells.
    Subclasses must implement methods for calculating open-circuit voltage and internal resistance.

    Attributes:
        electrical (ElectricalCellProperties): Electrical properties of the cell.
        thermal (ThermalCellProperties): Thermal properties of the cell.
        format (CellFormat): Physical format of the cell.
    Methods:
        open_circuit_voltage(state: BatteryState) -> float:
            Abstract method to compute the open-circuit voltage for a given battery state.
        hystheresis_voltage(state: BatteryState) -> float:
            Returns the hysteresis voltage for a given battery state. Default is 0.
        internal_resistance(state: BatteryState) -> float:
            Abstract method to compute the internal resistance (beginning of life) for a given battery state.
    """

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
    def open_circuit_voltage(self, state: BatteryState) -> float:
        """Compute the open-circuit voltage (in V) for a given battery state."""
        pass

    def hystheresis_voltage(self, state: BatteryState) -> float:
        """Compute the hysteresis voltage (in V) for a given battery state. Default is 0."""
        return 0

    @abstractmethod
    def internal_resistance(self, state: BatteryState) -> float:
        """Compute the beginning-of-life internal resistance (in Ohms) for a given battery state."""
        pass

