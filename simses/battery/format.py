import math
from dataclasses import dataclass, field


@dataclass
class CellFormat:
    volume: float = field(init=False)  # in m³
    area: float = field(init=False)  # in m²


@dataclass
class PrismaticCell(CellFormat):
    height: float
    width: float
    length: float

    def __post_init__(self):
        h = self.height
        w = self.width
        l = self.length

        self.volume = h * w * l * 1e-9  # m³
        self.area = 2 * (l * h + l * w + w * h) * 1e-6  # m²


@dataclass
class RoundCell(CellFormat):
    diameter: float  # in mm
    length: float  # in mm

    def __post_init__(self):
        d = self.diameter
        l = self.length
        self.volume = math.pi * (d / 2) ** 2 * l * 1e-9  # m³
        self.area = (math.pi * d * l + math.pi * (d / 2) ** 2) * 1e-6  # m²


@dataclass
class RoundCell18650(RoundCell):
    diameter: float = 18  # mm
    length: float = 65  # mm


@dataclass
class RoundCell26650(RoundCell):
    diameter: float = 26  # mm
    length: float = 65  # mm
